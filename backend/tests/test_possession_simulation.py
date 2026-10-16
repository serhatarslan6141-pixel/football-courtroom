from collections import Counter
import statistics

import pytest

from app.case_detection import detect_cases
from app.simulation import distance
from app.synthetic_match import EVENT_TYPES, calculate_match_state, generate_match


@pytest.fixture(params=[1, 2, 3, 9, 17, 42, 77, 101, 202, 303, (10001, True), (10002, True)])
def match(request):
    if isinstance(request.param, tuple):
        return generate_match(request.param[0], variety=request.param[1])
    return generate_match(request.param)


def test_spatial_and_temporal_continuity(match):
    previous_end = {"x": 50, "y": 50}
    previous_time = 0
    for event in match.events:
        data = event["metadata"]
        assert event["event_type"] in EVENT_TYPES
        assert data["start"] == previous_end
        assert event["start_timestamp"] == previous_time
        assert event["timestamp"] - event["start_timestamp"] == event["duration"]
        for point in (data["start"], data["end"]):
            assert all(0 <= point[axis] <= 100 for axis in ("x", "y"))
        if data.get("movement") == "reset":
            assert event["event_type"] in {"restart", "kickoff"}
            assert data["ball_in_play"] is False
        previous_end, previous_time = data["end"], event["timestamp"]
    assert previous_time == 5400
    assert sum(event["duration"] for event in match.events) == 5400
    assert [e["timestamp"] for e in match.events if e["event_type"] == "whistle"] == [
        2700,
        5400,
    ]


def test_only_active_players_and_legal_replacements_act(match):
    teams = {"home": match.home_team, "away": match.away_team}
    active = {
        side: {p.player_id for p in team.players if p.is_starter}
        for side, team in teams.items()
    }
    bench = {
        side: {p.player_id for p in team.players if not p.is_starter}
        for side, team in teams.items()
    }
    for event in match.events:
        data, side = event["metadata"], event["team_id"]
        if event["player_id"]:
            assert event["player_id"] in active[side]
        if data.get("recipient_id"):
            assert data["recipient_id"] in active[side]
            assert data["recipient_id"] != event["player_id"]
        if event["ball_player_id"]:
            assert event["ball_player_id"] in active[event["possession_team_id"]]
        if event["event_type"] == "substitution":
            assert data["player_out"] in active[side]
            assert data["player_in"] in bench[side]
            active[side].remove(data["player_out"])
            active[side].add(data["player_in"])
            bench[side].remove(data["player_in"])
        if event["event_type"] == "card" and data["card_type"] == "red":
            active[side].remove(event["player_id"])
    assert all(len(players) <= 11 for players in active.values())


def test_player_and_ball_ownership_continuity(match):
    owner = "home"
    carrier = None
    for event in match.events:
        data = event["metadata"]
        kind = event["event_type"]
        if kind in {"restart", "kickoff", "possession_change"}:
            assert data["previous_team"] == owner
            owner, carrier = data["new_team"], event["player_id"]
        if data["ball_in_play"]:
            assert event["possession_team_id"] == owner
            assert event["ball_player_id"] == carrier
        if kind in {"pass", "cross"}:
            assert event["player_id"] == carrier
            if data["outcome"] == "complete":
                carrier = data["recipient_id"]
        if kind in {"carry", "dribble", "shot", "ball_control", "miscontrol"}:
            assert event["player_id"] == carrier
        if data.get("player_role") == "GK" and kind != "substitution":
            progress = (
                data["start"]["x"]
                if data["attack_direction"] == 1
                else 100 - data["start"]["x"]
            )
            assert progress <= 20
            assert kind not in {"shot", "cross", "pressure_event"}


def test_shots_are_attacking_actions_with_recorded_goal_geometry(match):
    shots = [event for event in match.events if event["event_type"] == "shot"]
    assert shots
    for shot in shots:
        data = shot["metadata"]
        direction = data["attack_direction"]
        progress = data["start"]["x"] if direction == 1 else 100 - data["start"]["x"]
        assert progress >= 76
        assert 25 < data["start"]["y"] < 75
        assert data["target"]["x"] == (100 if direction == 1 else 0)
        if data["on_target"]:
            assert 44.6 <= data["target"]["y"] <= 55.4
        assert data["outcome"] in {"goal", "saved", "off_target"}
    for event in match.events:
        expected = (1 if event["team_id"] == "home" else -1) * (
            1 if event["period"] == 1 else -1
        )
        assert event["metadata"]["attack_direction"] == expected


def test_passes_are_mostly_short_and_stoppages_are_slower(match):
    passes = [e for e in match.events if e["event_type"] in {"pass", "cross"}]
    lengths = [distance(e["metadata"]["start"], e["metadata"]["end"]) for e in passes]
    assert sum(length < 32 for length in lengths) / len(lengths) > 0.8
    controls = [
        e["duration"] for e in match.events if e["event_type"] == "ball_control"
    ]
    stoppages = [
        e["duration"]
        for e in match.events
        if e["event_type"] == "stoppage" and e["duration"] > 0
    ]
    assert statistics.mean(stoppages) > statistics.mean(controls) * 4
    assert len({e["duration"] for e in passes}) > 1


def test_every_statistic_traces_to_completed_events(match):
    cutoff = 3107
    observed = [e for e in match.events if e["timestamp"] <= cutoff]
    state = calculate_match_state(match.events, through_timestamp=cutoff)
    for side in ("home", "away"):
        events = [e for e in observed if e["team_id"] == side]
        counts = Counter(e["event_type"] for e in events)
        assert state["pass_attempts"][side] == counts["pass"] + counts["cross"]
        assert state["pass_completions"][side] == sum(
            e["metadata"].get("outcome") == "complete"
            for e in events
            if e["event_type"] in {"pass", "cross"}
        )
        for key, kind in [
            ("score", "goal"),
            ("shots", "shot"),
            ("fouls", "foul"),
            ("tackles", "tackle"),
            ("interceptions", "interception"),
            ("pressure_events", "pressure_event"),
        ]:
            assert state[key][side] == counts[kind]
        assert state["shots_on_target"][side] == sum(
            e["metadata"]["on_target"] for e in events if e["event_type"] == "shot"
        )
        expected_time = sum(
            e["duration"] for e in observed if e["possession_team_id"] == side
        )
        assert state["possession_seconds"][side] == expected_time
        for key, card in [("yellow_cards", "yellow"), ("red_cards", "red")]:
            assert state[key][side] == sum(
                e["metadata"]["card_type"] == card
                for e in events
                if e["event_type"] == "card"
            )
    assert state["next_update_timestamp"] > cutoff


def test_passing_volume_without_threat_does_not_create_a_v2_case():
    match = generate_match(202)
    # A real sequence reduced to harmless control and backward passes must not
    # qualify just because many event rows exist in the post-trigger window.
    events = [
        e
        for e in match.events
        if e["event_type"] in {"pass", "ball_control", "possession_change"}
    ]
    for event in events:
        event["metadata"]["progressive"] = False
        event["metadata"]["start"] = {"x": 40, "y": 40}
        event["metadata"]["end"] = {"x": 39, "y": 40}
    assert detect_cases(events, through_timestamp=5400) == []
