import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import synthetic_match as matches
from app.case_detection import detect_cases
from app.main import app


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.setattr(
        matches,
        "MATCH_LIBRARY",
        {
            key: value
            for key, value in matches.MATCH_LIBRARY.items()
            if key.startswith("synthetic-")
        },
    )
    monkeypatch.setattr(matches, "_PENDING_SEEDS", set())
    return TestClient(app)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@pytest.mark.parametrize(
    "seed,score,event_hash",
    [
        (
            101,
            {"home": 0, "away": 2},
            "8af0f8c361717154260e37ea591cf786d9034fecc08497f32e44e8c0d08b7e55",
        ),
        (
            202,
            {"home": 2, "away": 1},
            "a196708e429ccc63e61f8fe6be71561ec6e8cb1a75ce35453f30ecd22d77ddce",
        ),
        (
            303,
            {"home": 4, "away": 1},
            "4a50016617b522b34f42a98f24c9cb78f0c0daa95e2863ab00af711f1e0a58f8",
        ),
    ],
)
def test_demo_logs_and_outcomes_are_unchanged(seed, score, event_hash):
    match = matches.generate_match(seed)
    assert digest(match.events) == event_hash
    assert matches.calculate_match_state(match.events)["score"] == score
    assert match.generation_mode == "demo"


def test_varied_setup_and_entire_match_are_seed_reproducible():
    first = matches.generate_match(10001, variety=True)
    replay = matches.generate_match(10001, variety=True)
    other = matches.generate_match(10002, variety=True)
    assert asdict(first) == asdict(replay)
    assert detect_cases(first.events) == detect_cases(replay.events)
    # Compare actual football actions and outcomes, not just differently prefixed IDs.
    actions = lambda match: [
        (
            e["timestamp"],
            e["event_type"],
            e["team_id"],
            e["player_id"],
            e["metadata"].get("start"),
            e["metadata"].get("end"),
            e["metadata"].get("outcome"),
        )
        for e in match.events
    ]
    assert actions(first) != actions(other)
    a = matches.calculate_match_state(first.events)
    b = matches.calculate_match_state(other.events)
    assert a["score"] != b["score"]
    assert a["shots"] != b["shots"]
    assert (first.home_team.name, first.away_team.name) != (
        other.home_team.name,
        other.away_team.name,
    )


def test_create_list_revisit_and_reproduce_with_saved_seed(catalog, monkeypatch):
    seeds = iter([10001, 10002])
    monkeypatch.setattr(matches.secrets, "randbits", lambda _: next(seeds))
    first = catalog.post("/api/matches")
    second = catalog.post("/api/matches")
    assert first.status_code == second.status_code == 201
    a, b = first.json(), second.json()
    assert a["match_id"] != b["match_id"] and a["seed"] != b["seed"]
    assert a["generation_mode"] == "varied-v1" and a["teams"]
    assert (
        not {"score", "events", "cases"} & a.keys()
    )  # Creation must not spoil results.
    listed = catalog.get("/api/matches").json()
    assert listed["count"] == 5
    assert {m["match_id"] for m in listed["matches"]} == {
        "synthetic-101",
        "synthetic-202",
        "synthetic-303",
        a["match_id"],
        b["match_id"],
    }
    identifier = a["match_id"]
    log = catalog.get(f"/api/matches/{identifier}/events").json()["events"]
    assert (
        log
        == matches.generate_match(a["seed"], match_id=identifier, variety=True).events
    )
    # A second browser/client session sees the identical stored server-session match.
    with TestClient(app) as another_client:
        assert (
            another_client.get(f"/api/matches/{identifier}/events").json()["events"]
            == log
        )
        assert (
            another_client.get(f"/api/matches/{identifier}").json()["seed"] == a["seed"]
        )
    assert catalog.get(f"/api/matches/{identifier}/events").json()["events"] == log


def test_generated_cases_keep_identity_and_full_window_eligibility(
    catalog, monkeypatch
):
    monkeypatch.setattr(matches.secrets, "randbits", lambda _: 10003)
    item = catalog.post("/api/matches").json()
    identifier = item["match_id"]
    log = catalog.get(f"/api/matches/{identifier}/events").json()["events"]
    cases = catalog.get(f"/api/matches/{identifier}/cases").json()["cases"]
    assert cases
    ids = {event["event_id"] for event in log}
    for case in cases:
        assert case["match_id"] == identifier
        assert case["case_id"].startswith(identifier)
        assert set(case["trigger_event_ids"]) <= ids
        available = case["available_timestamp"]
        before = catalog.get(
            f"/api/matches/{identifier}/cases?through_timestamp={available-1}"
        ).json()["cases"]
        at = catalog.get(
            f"/api/matches/{identifier}/cases?through_timestamp={available}"
        ).json()["cases"]
        assert case["case_id"] not in {c["case_id"] for c in before}
        assert case in at
        observed = {e["event_id"] for e in log if e["timestamp"] <= available}
        assert all(set(fact["event_ids"]) <= observed for fact in case["evidence"])


def test_unknown_match_reads_do_not_generate_or_replace_expired_matches(catalog):
    before = catalog.get("/api/matches").json()
    for suffix in ("", "/events", "/state", "/cases", "/stream"):
        assert catalog.get(f"/api/matches/generated-expired{suffix}").status_code == 404
    assert catalog.get("/api/matches").json() == before


def test_creation_retries_seed_collisions_and_concurrent_creations_are_unique(
    catalog, monkeypatch
):
    seeds = iter([101, 10001, 10001, 10002])
    monkeypatch.setattr(matches.secrets, "randbits", lambda _: next(seeds))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda _: matches.create_generated_match(), range(2))
        )
    assert {m.seed for m in results} == {10001, 10002}
    assert len(matches.list_available_matches()) == 5
    assert not matches._PENDING_SEEDS


def test_failed_generation_does_not_publish_a_partial_match(catalog, monkeypatch):
    monkeypatch.setattr(matches.secrets, "randbits", lambda _: 10001)

    def fail(*args, **kwargs):
        raise RuntimeError("generation failed")

    monkeypatch.setattr(matches, "generate_match", fail)
    with pytest.raises(RuntimeError):
        matches.create_generated_match()
    assert len(matches.list_available_matches()) == 3
    assert not matches._PENDING_SEEDS


def test_server_restart_restores_only_demos(catalog, monkeypatch):
    monkeypatch.setattr(matches.secrets, "randbits", lambda _: 10001)
    item = catalog.post("/api/matches").json()
    backend = str(Path(__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": backend}
    script = 'import json; from app.synthetic_match import list_available_matches; print(json.dumps([m["match_id"] for m in list_available_matches()]))'
    fresh_ids = json.loads(
        subprocess.check_output([sys.executable, "-c", script], env=env)
    )
    assert fresh_ids == ["synthetic-101", "synthetic-202", "synthetic-303"]
    assert item["match_id"] not in fresh_ids
    assert matches.get_match(item["match_id"]).seed == item["seed"]


def test_variety_rotates_only_eligible_outfield_roles_and_uses_supported_tactics():
    generated = [
        matches.generate_match(seed, variety=True) for seed in (10001, 10002, 10003)
    ]
    assert {m.style for m in generated} == {"balanced", "pressing"}
    rotations = 0
    for match in generated:
        assert match.home_team.name != match.away_team.name
        for team in (match.home_team, match.away_team):
            baseline = next(
                config for config in matches.TEAM_CONFIG if config["name"] == team.name
            )
            starters, bench = team.players[:11], team.players[11:]
            assert len(starters) == 11 and len(bench) == 7
            assert all(player.is_starter for player in starters)
            assert not any(player.is_starter for player in bench)
            assert len({player.player_id for player in team.players}) == 18
            assert len({player.squad_number for player in team.players}) == 18
            assert {row["name"] for row in baseline["players"]} <= {
                p.name for p in team.players
            }
            assert sorted(p.position for p in starters) == sorted(
                row["position"] for row in baseline["players"]
            )
            assert (
                next(p for p in starters if p.position == "GK").name
                == baseline["players"][0]["name"]
            )
            rotations += sum(p.squad_number >= 20 for p in starters)
    assert rotations > 0
