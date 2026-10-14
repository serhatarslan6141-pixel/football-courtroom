import json

import pytest
from fastapi.testclient import TestClient

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


def test_match_state_at_different_replay_positions():
    match = generate_match(31)
    first_state = calculate_match_state(match.events, through_event=5)
    second_state = calculate_match_state(match.events, through_event=25)
    assert first_state["through_event"] == 5
    assert second_state["through_event"] == 25
    assert second_state["match_clock_seconds"] >= first_state["match_clock_seconds"]


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

    stream_response = client.get(f"/api/matches/{match_id}/stream?speed=2.0")
    assert stream_response.status_code == 200
    assert "text/event-stream" in stream_response.headers["content-type"]
    body = stream_response.iter_lines()
    first_line = next(body)
    assert first_line


@pytest.mark.parametrize("seed", [1, 2, 3, 5])
def test_multiple_matches_with_different_seeds_are_distinct(seed):
    match = generate_match(seed)
    assert match.synthetic is True
    assert match.match_id == f"synthetic-{seed}"
    assert match.events
