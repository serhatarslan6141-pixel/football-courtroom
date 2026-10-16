import pytest
from fastapi.testclient import TestClient

from app.case_detection import detect_cases
from app.main import app
from app.synthetic_match import generate_match, select_replay_events


@pytest.mark.parametrize("seed", [101, 202, 303])
def test_cases_wait_for_complete_windows_and_keep_their_identity(seed):
    match = generate_match(seed)
    final_cases = detect_cases(match.events)
    assert final_cases
    for case in final_cases:
        available = max(window["end"] for window in case["relevant_windows"])
        assert case["available_timestamp"] == available
        assert available > case["detection_timestamp"]
        before = detect_cases(match.events, through_timestamp=available - 1)
        assert case["case_id"] not in {item["case_id"] for item in before}
        at_boundary = detect_cases(match.events, through_timestamp=available)
        observed_case = next(item for item in at_boundary if item["case_id"] == case["case_id"])
        assert observed_case == case
        visible_ids = {event["event_id"] for event in match.events if event["timestamp"] <= available}
        assert set(case["trigger_event_ids"]) <= visible_ids
        for evidence in case["evidence"]:
            assert set(evidence["event_ids"]) <= visible_ids


def test_event_count_means_chronological_count_for_both_endpoints():
    match = generate_match(202)
    assert any(a["index"] > b["index"] for a, b in zip(match.events, match.events[1:]))
    client = TestClient(app)
    for count in (0, 1, 40, 150, len(match.events)):
        selected = select_replay_events(match.events, through_event=count)
        assert selected == match.events[:count]
        state = client.get(f"/api/matches/synthetic-202/state?through_event={count}").json()["state"]
        cases = client.get(f"/api/matches/synthetic-202/cases?through_event={count}").json()["cases"]
        assert state["through_event"] == count
        assert cases == detect_cases(selected)
        assert all(case["available_timestamp"] <= state["match_clock_seconds"] for case in cases)


def test_timestamp_boundary_includes_all_events_in_the_same_second():
    events = [
        {"event_id": "late", "index": 0, "timestamp": 20, "team_id": "home", "event_type": "goal"},
        {"event_id": "first", "index": 9, "timestamp": 10, "team_id": "away", "event_type": "pass"},
        {"event_id": "second", "index": 10, "timestamp": 10, "team_id": "home", "event_type": "goal"},
    ]
    assert [event["event_id"] for event in select_replay_events(events, through_timestamp=10)] == ["first", "second"]
    assert select_replay_events(events, through_event=0) == []
    assert [event["event_id"] for event in select_replay_events(events, through_event=1, through_timestamp=20)] == ["first"]


def test_missed_chance_cannot_claim_absent_follow_up_before_window_ends():
    match = generate_match(202)
    case = next(item for item in detect_cases(match.events) if item["case_type"] == "missed_opportunity")
    trigger = case["detection_timestamp"]
    assert case["available_timestamp"] == trigger + 90
    assert case["case_id"] not in {
        item["case_id"] for item in detect_cases(match.events, through_timestamp=trigger)
    }
    # A timestamp cannot override the more restrictive event-count boundary.
    count = sum(event["timestamp"] <= trigger for event in match.events)
    assert case["case_id"] not in {
        item["case_id"] for item in detect_cases(match.events, through_event=count, through_timestamp=5400)
    }
