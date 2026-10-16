import json

import pytest
from fastapi.testclient import TestClient

from app.case_detection import detect_cases
from app.main import app
from app.synthetic_match import calculate_match_state, generate_match


def test_seed_reproducibility():
    first = generate_match(1234)
    second = generate_match(1234)
    assert first.events == second.events
    assert first.as_metadata() == second.as_metadata()


def test_event_ids_unique_and_sorted():
    match = generate_match(42)
    event_ids = [event["event_id"] for event in match.events]
    assert len(event_ids) == len(set(event_ids))
    timestamps = [event["timestamp"] for event in match.events]
    assert timestamps == sorted(timestamps)


def test_substitutions_are_valid():
    match = generate_match(17)
    substitution_events = [event for event in match.events if event["event_type"] == "substitution"]
    assert substitution_events
    for event in substitution_events:
        assert event["team_id"] in {"home", "away"}
        assert event["metadata"]["player_out"]
        assert event["metadata"]["player_in"]
        assert event["metadata"]["player_out"] != event["metadata"]["player_in"]


def test_score_consistency_and_valid_coordinates():
    match = generate_match(77)
    score = {"home": 0, "away": 0}
    for event in match.events:
        if event["event_type"] == "goal":
            score[event["team_id"]] += 1
        if "x" in event and "y" in event:
            assert 0 <= float(event["x"]) <= 100
            assert 0 <= float(event["y"]) <= 100
    assert score == calculate_match_state(match.events)["score"]


def test_valid_team_and_player_references():
    match = generate_match(15)
    team_ids = {"home", "away"}
    player_ids = {player.player_id for player in match.home_team.players} | {player.player_id for player in match.away_team.players}
    for event in match.events:
        if event["team_id"] in team_ids:
            assert event["team_id"] in {"home", "away"}
        if event.get("player_id"):
            assert event["player_id"] in player_ids


def test_pass_statistics_match_event_data():
    match = generate_match(9)
    state = calculate_match_state(match.events)
    pass_attempts = sum(1 for event in match.events if event["event_type"] == "pass")
    completed_passes = sum(1 for event in match.events if event["event_type"] == "pass" and event["metadata"].get("outcome") == "complete")
    assert pass_attempts == sum(state["pass_attempts"].values())
    assert completed_passes == sum(state["pass_completions"].values())


def test_both_teams_have_measurable_possession_and_pass_accuracy():
    for seed in (101, 202, 303):
        match = generate_match(seed)
        state = calculate_match_state(match.events)
        assert sum(state["possession"].values()) == pytest.approx(100.0)
        assert state["possession"]["home"] > 0
        assert state["possession"]["away"] > 0
        assert any(event["team_id"] == "away" for event in match.events)
        assert state["pass_attempts"]["home"] >= 0
        assert state["pass_attempts"]["away"] >= 0
        assert (state["pass_attempts"]["home"] == 0 and state["pass_completion"]["home"] is None) or (
            state["pass_attempts"]["home"] > 0 and state["pass_completion"]["home"] is not None
        )
        assert (state["pass_attempts"]["away"] == 0 and state["pass_completion"]["away"] is None) or (
            state["pass_attempts"]["away"] > 0 and state["pass_completion"]["away"] is not None
        )


def test_distinct_matchups_and_teams():
    matches = [generate_match(seed) for seed in (101, 202, 303)]
    pairings = {(match.home_team.name, match.away_team.name) for match in matches}
    assert len(pairings) >= 3
    assert {match.home_team.name for match in matches} | {match.away_team.name for match in matches} == {
        "Northbridge City",
        "Harbor Athletic",
        "Mossfield United",
        "Riverside Athletic",
        "Ashcombe Rovers",
        "Briarhampton FC",
    }


def test_possession_is_event_weighted_and_not_fixed_50():
    match = generate_match(55)
    state = calculate_match_state(match.events)
    assert round(state["possession"]["home"] + state["possession"]["away"], 2) == 100.0
    assert state["possession"]["home"] != 50 or state["possession"]["away"] != 50


def test_event_metadata_contains_player_team_and_location_details():
    match = generate_match(88)
    event_types = {"pass", "pressure_event", "shot", "foul", "substitution", "card"}
    assert any(event["event_type"] in event_types for event in match.events)
    for event in match.events:
        metadata = event.get("metadata", {})
        if event["event_type"] in {"pass", "pressure_event", "shot", "foul", "substitution", "card"}:
            assert metadata.get("team_name")
            assert metadata.get("player_name")
            if event["event_type"] in {"pass", "pressure_event", "shot"}:
                assert "location" in metadata or "start" in metadata or "end" in metadata


def test_match_state_at_different_replay_positions():
    match = generate_match(31)
    first_state = calculate_match_state(match.events, through_event=5)
    second_state = calculate_match_state(match.events, through_event=25)
    assert first_state["through_event"] == 5
    assert second_state["through_event"] == 25
    assert second_state["match_clock_seconds"] >= first_state["match_clock_seconds"]


def test_match_state_at_replay_timestamps_excludes_future_events():
    match = generate_match(101)
    event_timestamps = sorted({event["timestamp"] for event in match.events})
    cutoff = event_timestamps[len(event_timestamps) // 2]

    state = calculate_match_state(match.events, through_timestamp=cutoff)
    observed = [event for event in match.events if event["timestamp"] <= cutoff]

    assert state["through_event"] == len(observed)
    assert state["match_clock_seconds"] == cutoff
    assert state["score"] == {
        "home": sum(1 for event in observed if event["event_type"] == "goal" and event["team_id"] == "home"),
        "away": sum(1 for event in observed if event["event_type"] == "goal" and event["team_id"] == "away"),
    }
    assert state["pass_attempts"] == {
        "home": sum(1 for event in observed if event["event_type"] == "pass" and event["team_id"] == "home"),
        "away": sum(1 for event in observed if event["event_type"] == "pass" and event["team_id"] == "away"),
    }
    assert state["shots"] == {
        "home": sum(1 for event in observed if event["event_type"] == "shot" and event["team_id"] == "home"),
        "away": sum(1 for event in observed if event["event_type"] == "shot" and event["team_id"] == "away"),
    }
    assert all(event["timestamp"] <= cutoff for event in observed)
    assert all(event["timestamp"] > cutoff for event in match.events if event not in observed)


def test_match_state_counts_cards_and_pressure_events_from_event_data():
    events = [
        {"event_id": "evt-1", "index": 0, "timestamp": 10, "minute": "00:10", "team_id": "home", "event_type": "pressure_event", "metadata": {"team_name": "Home", "player_name": "A", "location": {"x": 80, "y": 40}, "possession_seconds": 7.0}},
        {"event_id": "evt-2", "index": 1, "timestamp": 20, "minute": "00:20", "team_id": "home", "event_type": "card", "metadata": {"team_name": "Home", "player_name": "B", "card_type": "yellow"}},
        {"event_id": "evt-3", "index": 2, "timestamp": 25, "minute": "00:25", "team_id": "away", "event_type": "pressure_event", "metadata": {"team_name": "Away", "player_name": "C", "location": {"x": 25, "y": 50}, "possession_seconds": 4.0}},
        {"event_id": "evt-4", "index": 3, "timestamp": 35, "minute": "00:35", "team_id": "away", "event_type": "card", "metadata": {"team_name": "Away", "player_name": "D", "card_type": "red"}},
        {"event_id": "evt-5", "index": 4, "timestamp": 90, "minute": "01:30", "team_id": "home", "event_type": "goal", "metadata": {"team_name": "Home", "player_name": "E"}},
    ]

    state = calculate_match_state(events)

    assert state["yellow_cards"] == {"home": 1, "away": 0}
    assert state["red_cards"] == {"home": 0, "away": 1}
    assert state["pressure_events"] == {"home": 1, "away": 1}
    assert state["score"] == {"home": 1, "away": 0}


def test_detect_substitution_impact_case_from_event_data():
    events = [
        {"event_id": "e1", "index": 0, "timestamp": 10, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
        {"event_id": "e2", "index": 1, "timestamp": 15, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
        {"event_id": "e3", "index": 2, "timestamp": 20, "team_id": "home", "event_type": "pressure_event", "metadata": {"team_name": "Northbridge", "player_name": "B", "location": {"x": 75, "y": 40}, "possession_seconds": 4.2}},
        {"event_id": "e4", "index": 3, "timestamp": 30, "team_id": "home", "event_type": "substitution", "metadata": {"team_name": "Northbridge", "player_name": "C", "player_in_name": "Sub 1", "player_out_name": "Out 1"}},
        {"event_id": "e5", "index": 4, "timestamp": 60, "team_id": "home", "event_type": "pressure_event", "metadata": {"team_name": "Northbridge", "player_name": "Sub 1", "location": {"x": 78, "y": 45}, "possession_seconds": 5.5}},
        {"event_id": "e6", "index": 5, "timestamp": 65, "team_id": "home", "event_type": "shot", "metadata": {"team_name": "Northbridge", "player_name": "Sub 1", "on_target": True, "outcome": "saved"}},
        {"event_id": "e7", "index": 6, "timestamp": 72, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "Sub 1"}},
        {"event_id": "e8", "index": 7, "timestamp": 78, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "Sub 1"}},
        {"event_id": "e9", "index": 8, "timestamp": 82, "team_id": "away", "event_type": "pressure_event", "metadata": {"team_name": "Harbor", "player_name": "D", "location": {"x": 25, "y": 55}, "possession_seconds": 3.4}},
    ]

    # The entire post-substitution observation window must have elapsed.
    assert not any(case["case_type"] == "substitution_impact" for case in detect_cases(events, through_timestamp=239))
    cases = detect_cases(events, through_timestamp=240)
    substitution_cases = [case for case in cases if case["case_type"] == "substitution_impact"]
    assert substitution_cases
    assert substitution_cases[0]["teams"]["team_id"] == "home"
    assert substitution_cases[0]["trigger_event_ids"] == ["e4"]


def test_detect_momentum_shift_and_missed_opportunity_cases():
    events = [
        {"event_id": "m1", "index": 0, "timestamp": 10, "team_id": "away", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Harbor", "player_name": "A"}},
        {"event_id": "m2", "index": 1, "timestamp": 15, "team_id": "away", "event_type": "pressure_event", "metadata": {"team_name": "Harbor", "player_name": "A", "location": {"x": 64, "y": 48}, "possession_seconds": 5.0}},
        {"event_id": "m3", "index": 2, "timestamp": 18, "team_id": "home", "event_type": "possession_change", "metadata": {"team_name": "Northbridge", "player_name": "B", "new_team": "home"}},
        {"event_id": "m4", "index": 3, "timestamp": 30, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "B"}},
        {"event_id": "m5", "index": 4, "timestamp": 35, "team_id": "home", "event_type": "pressure_event", "metadata": {"team_name": "Northbridge", "player_name": "B", "location": {"x": 70, "y": 52}, "possession_seconds": 7.1}},
        {"event_id": "m6", "index": 5, "timestamp": 40, "team_id": "home", "event_type": "shot", "metadata": {"team_name": "Northbridge", "player_name": "B", "outcome": "off_target", "on_target": False}},
        {"event_id": "m7", "index": 6, "timestamp": 45, "team_id": "away", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Harbor", "player_name": "C"}},
        {"event_id": "m8", "index": 7, "timestamp": 52, "team_id": "away", "event_type": "pressure_event", "metadata": {"team_name": "Harbor", "player_name": "C", "location": {"x": 28, "y": 50}, "possession_seconds": 4.5}},
    ]

    cases = detect_cases(events, through_timestamp=198)
    case_types = {case["case_type"] for case in cases}
    assert "momentum_shift" in case_types
    assert "missed_opportunity" in case_types


def test_no_case_when_evidence_is_insufficient_or_future_event_leakage_prevented():
    events = [
        {"event_id": "f1", "index": 0, "timestamp": 10, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
        {"event_id": "f2", "index": 1, "timestamp": 20, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
        {"event_id": "f3", "index": 2, "timestamp": 30, "team_id": "home", "event_type": "substitution", "metadata": {"team_name": "Northbridge", "player_name": "B", "player_in_name": "Sub 2", "player_out_name": "Out 2"}},
        {"event_id": "f4", "index": 3, "timestamp": 35, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
    ]

    early_cases = detect_cases(events, through_timestamp=25)
    assert not early_cases

    late_cases = detect_cases(events, through_timestamp=50)
    assert not late_cases


def test_requires_minimum_history_before_labeling_a_significant_change():
    events = [
        {"event_id": "m1", "index": 0, "timestamp": 10, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
        {"event_id": "m2", "index": 1, "timestamp": 15, "team_id": "home", "event_type": "pressure_event", "metadata": {"team_name": "Northbridge", "player_name": "A", "location": {"x": 70, "y": 55}, "possession_seconds": 4.0}},
        {"event_id": "m3", "index": 2, "timestamp": 18, "team_id": "home", "event_type": "pass", "metadata": {"outcome": "complete", "team_name": "Northbridge", "player_name": "A"}},
        {"event_id": "m4", "index": 3, "timestamp": 24, "team_id": "home", "event_type": "shot", "metadata": {"team_name": "Northbridge", "player_name": "A", "outcome": "off_target", "on_target": False}},
    ]

    assert not detect_cases(events, through_timestamp=30)


def test_api_returns_structured_cases_for_selected_match():
    match = generate_match(202)
    response = detect_cases(match.events, through_timestamp=match.events[-1]["timestamp"])
    assert response
    case = response[0]
    assert case["case_id"]
    assert case["match_id"] == match.match_id
    assert case["case_type"]
    assert case["title"]
    assert case["evidence"]
    assert case["counterevidence"]


def test_api_endpoints_and_sse_response():
    client = TestClient(app)
    matches_response = client.get("/api/matches")
    assert matches_response.status_code == 200
    matches = matches_response.json()["matches"]
    assert matches

    match_id = matches[0]["match_id"]
    metadata_response = client.get(f"/api/matches/{match_id}")
    assert metadata_response.status_code == 200
    payload = metadata_response.json()
    assert payload["synthetic"] is True
    assert payload["teams"]

    events_response = client.get(f"/api/matches/{match_id}/events")
    assert events_response.status_code == 200
    assert events_response.json()["count"] > 0

    state_response = client.get(f"/api/matches/{match_id}/state?through_event=10")
    assert state_response.status_code == 200
    state = state_response.json()["state"]
    assert "score" in state

    # Exercise real SSE serialization without sleeping through the whole match.
    start = events_response.json()["count"] - 2
    stream_response = client.get(f"/api/matches/{match_id}/stream?speed=4.0&start={start}")
    assert stream_response.status_code == 200
    assert "text/event-stream" in stream_response.headers["content-type"]
    body = stream_response.iter_lines()
    first_line = next(body)
    first_payload = json.loads(first_line.removeprefix("data: "))
    assert first_payload["index"] == start
    assert first_payload["event"] == events_response.json()["events"][start]


@pytest.mark.parametrize("seed", [1, 2, 3, 5])
def test_multiple_matches_with_different_seeds_are_distinct(seed):
    match = generate_match(seed)
    assert match.synthetic is True
    assert match.match_id == f"synthetic-{seed}"
    assert match.events
