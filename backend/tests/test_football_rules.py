"""Law predicates, controlled engine scenarios and generated-log invariants."""

import random
from collections import Counter

import pytest

from app.football_decisions import shooting_assessment
from app.football_rules import (
    boundary_decision,
    foul_restart,
    free_kick_position,
    offside_context,
    penalty_area,
    foul_card,
)
from app.simulation import PossessionSimulation, distance, xy
from app.synthetic_match import generate_match, calculate_match_state
from app.case_detection import detect_cases


@pytest.fixture
def sim():
    match = generate_match(202)
    return PossessionSimulation(
        "rules", match.home_team, match.away_team, random.Random(9), "balanced"
    )


@pytest.mark.parametrize("home_direction", [1, -1])
@pytest.mark.parametrize("line", [0, 100])
@pytest.mark.parametrize("last_touch", ["home", "away"])
def test_touchlines_award_opponents_at_crossing(home_direction, line, last_touch):
    result = boundary_decision(
        xy(38, 50),
        {"x": 38, "y": -0.3 if line == 0 else 100.3},
        last_touch,
        home_direction,
    )
    assert result == {
        "kind": "throw_in",
        "team": "away" if last_touch == "home" else "home",
        "location": xy(38, line),
        "boundary": "touchline",
    }


@pytest.mark.parametrize("home_direction", [1, -1])
@pytest.mark.parametrize("edge", [0, 100])
@pytest.mark.parametrize("defender_last", [True, False])
def test_goal_line_last_touch_decides_corner_or_goal_kick(
    home_direction, edge, defender_last
):
    defending = "home" if edge == (0 if home_direction == 1 else 100) else "away"
    attacking = "away" if defending == "home" else "home"
    last_touch = defending if defender_last else attacking
    result = boundary_decision(
        xy(50, 25),
        {"x": -0.2 if edge == 0 else 100.2, "y": 25},
        last_touch,
        home_direction,
    )
    assert result["kind"] == ("corner" if defender_last else "goal_kick")
    assert result["team"] == (attacking if defender_last else defending)
    assert result["location"] == (
        xy(edge, 0) if defender_last else xy(3 if edge == 0 else 97, 50)
    )


def test_entire_ball_must_cross_and_first_boundary_wins():
    for point in ({"x": 100, "y": 30}, {"x": 100.05, "y": 30}, {"x": 30, "y": -0.05}):
        assert boundary_decision(xy(50, 50), point, "home", 1) is None
    # Crosses the touchline before the goal line: must be a throw, not a corner.
    result = boundary_decision(xy(95, 2), {"x": 110, "y": -20}, "away", 1)
    assert result["kind"] == "throw_in"
    assert result["location"]["x"] < 100


def test_ground_ball_between_posts_is_goal_including_own_goal():
    for last_touch in ("home", "away"):
        result = boundary_decision(xy(95, 50), {"x": 100.2, "y": 50}, last_touch, 1)
        assert result["kind"] == "goal"
        assert result["team"] == "home"
    assert (
        boundary_decision(xy(95, 50), {"x": 100.2, "y": 50}, "home", 1, height_m=3)[
            "kind"
        ]
        == "goal_kick"
    )


@pytest.mark.parametrize("direction", [1, -1])
def test_penalty_requires_direct_foul_by_defending_team_in_own_box(direction):
    point = xy(10 if direction == 1 else 90, 50)
    assert penalty_area(point, direction)
    assert foul_restart("trip", point, direction) == "penalty"
    assert foul_restart("contact_tackle", point, direction) == "penalty"
    assert foul_restart("dangerous_play", point, direction) == "indirect_free_kick"
    assert (
        foul_restart("impeding_without_contact", point, direction)
        == "indirect_free_kick"
    )
    assert (
        foul_restart("trip", point, -direction) == "direct_free_kick"
    )  # opponent's box
    assert foul_restart("trip", xy(50, 50), direction) == "direct_free_kick"
    assert foul_restart("trip", xy(point["x"], 10), direction) == "direct_free_kick"
    assert foul_restart("trip", point, direction, ball_in_play=False) is None
    # Penalty-area lines belong to the area.
    edge = {
        "x": 16.5 / 105 * 100 if direction == 1 else 100 - 16.5 / 105 * 100,
        "y": 50 + 20.16 / 68 * 100,
    }
    assert penalty_area(edge, direction)
    with pytest.raises(ValueError):
        foul_restart("random_box_event", point, direction)


def test_attacking_indirect_in_goal_area_moves_to_parallel_line():
    point = free_kick_position(xy(98, 50), 1, indirect=True)
    assert point == xy(100 - 5.5 / 105 * 100, 50)
    assert free_kick_position(xy(2, 50), -1, indirect=True) == xy(5.5 / 105 * 100, 50)
    assert free_kick_position(xy(98, 50), 1) == xy(98, 50)


def snapshot(receiver_x=90):
    return [
        {
            "player_id": "receiver",
            "team_id": "home",
            "role": "ST",
            "x": receiver_x,
            "y": 50,
        },
        {"player_id": "keeper", "team_id": "away", "role": "GK", "x": 98, "y": 50},
        {"player_id": "defender", "team_id": "away", "role": "CB", "x": 85, "y": 40},
        {"player_id": "defender2", "team_id": "away", "role": "CB", "x": 70, "y": 60},
    ]


@pytest.mark.parametrize("direction", [1, -1])
def test_offside_needs_receiver_ball_second_last_opponent_and_half(direction):
    def context(receiver, ball=80, restart=None):
        players = snapshot(receiver)
        if direction == -1:
            players = [{**p, "x": 100 - p["x"]} for p in players]
        return offside_context(
            xy(ball if direction == 1 else 100 - ball, 50),
            "receiver",
            players,
            "home",
            direction,
            restart,
        )

    assert context(90)["offside_position"]
    assert not context(85)["offside_position"]  # level with second last
    assert not context(49, 40)["offside_position"]  # own half
    assert not context(90, 92)["offside_position"]  # behind ball
    assert not context(90, 90)["offside_position"]  # level with ball
    for kind in ("throw_in", "goal_kick", "corner"):
        assert context(90, restart=kind)["exempt"]
    assert not context(90, restart="indirect_free_kick")["exempt"]
    players = snapshot(80)
    players[1][
        "x"
    ] = 60  # GK comes out; use actual second-last opponent, not keeper assumption.
    assert offside_context(xy(65, 50), "receiver", players, "home", 1)[
        "offside_position"
    ]


def force_receiver(sim, offside=True):
    receiver = next(p for p in sim.active["home"] if p.position == "ST")
    sim.ball = xy(80, 50)
    sim.carrier = next(p for p in sim.active["home"] if p.position == "AM")
    # Anchor receiver at release; keep all other recipients too far away to be candidates.
    sim.anchor = lambda team, player: (
        xy(90, 50)
        if player == receiver
        else (
            xy(99, 50)
            if team == "away" and player.position == "GK"
            else xy(85, 40) if team == "away" else xy(10, 10)
        )
    )
    sim.rng.choices = lambda population, **kwargs: [
        next(c for c in population if c[0] == receiver)
    ]
    sim.rng.random = lambda: 0.5 if offside else 0.999  # complete vs intercepted
    return receiver


def test_offside_only_on_receiver_involvement_not_interception(sim):
    force_receiver(sim)
    # Stop after the award so the controlled random fixture only selects one pass.
    awards = []
    sim.restart = lambda *args: awards.append(args)
    sim.pass_ball()
    call = next(e for e in sim.events if e["event_type"] == "offside")
    assert call["metadata"]["offence_location"] == sim.ball
    assert call["metadata"]["offside_context"]["receiver_position"] == xy(90, 50)
    assert awards[0][:3] == ("away", sim.ball, "indirect_free_kick")
    assert sim.events[0]["metadata"]["outcome"] == "incomplete"
    sim.events.clear()
    force_receiver(sim, offside=False)
    sim.pass_ball()
    assert not any(e["event_type"] == "offside" for e in sim.events)
    assert any(e["event_type"] == "interception" for e in sim.events)


@pytest.mark.parametrize("kind", ["throw_in", "goal_kick", "corner"])
def test_direct_receipt_of_exempt_restart_is_not_offside(sim, kind):
    force_receiver(sim)
    sim.pass_ball(restart_type=kind)
    assert sim.events[0]["metadata"]["outcome"] == "complete"
    assert not any(e["event_type"] == "offside" for e in sim.events)


@pytest.mark.parametrize(
    "kind,location",
    [
        ("throw_in", xy(60, 0)),
        ("corner", xy(100, 100)),
        ("goal_kick", xy(3, 50)),
        ("direct_free_kick", xy(65, 42)),
        ("indirect_free_kick", xy(98, 50)),
        ("penalty", xy(90, 50)),
    ],
)
def test_restarts_record_award_location_eligible_taker_pause_and_first_touch(
    sim, kind, location
):
    sim.clock = 100
    sim.restart("home", location, kind, 25)
    setup = sim.events[0]
    assert setup["event_type"] == "restart"
    data = setup["metadata"]
    expected = (
        sim.from_attack("home", 100 - 11 / 105 * 100, 50)
        if kind == "penalty"
        else free_kick_position(location, 1, kind == "indirect_free_kick")
    )
    assert data["end"] == expected
    assert data["new_team"] == "home"
    assert setup["player_id"] in {p.player_id for p in sim.active["home"]}
    if kind == "goal_kick":
        assert data["player_role"] == "GK"
        assert data["end"]["x"] * 1.05 <= 5.5
    pause = sim.events[1]
    assert pause["start_timestamp"] == 100 and pause["timestamp"] == 125
    assert pause["metadata"]["start"] == pause["metadata"]["end"] == expected
    assert pause["metadata"]["ball_in_play"] is False
    first = next(
        e for e in sim.events if e["duration"] > 0 and e["metadata"]["ball_in_play"]
    )
    assert first["start_timestamp"] == 125
    assert first["metadata"]["start"] == expected
    assert first["possession_team_id"] == "home"
    assert first["event_type"] in (
        {"shot"} if kind == "penalty" else {"pass", "cross", "shot"}
    )
    if kind in {"throw_in", "goal_kick", "indirect_free_kick"}:
        assert first["event_type"] == "pass"
    for point in data["setup_positions"]:
        if point["player_id"] == setup["player_id"]:
            continue
        if kind == "penalty":
            if point["team_id"] == "away" and point["role"] == "GK":
                assert point["x"] == 100
            else:
                assert point["x"] < expected["x"]
                assert not penalty_area(point, -1)
                assert distance(point, expected) >= 9.15
        elif point["team_id"] == "away":
            assert distance(point, expected) >= (1.99 if kind == "throw_in" else 9.14)


def test_penalty_near_half_end_is_completed_before_whistle(sim):
    sim.clock = 2695
    sim.ball = xy(90, 50)
    sim.carrier = next(p for p in sim.active["home"] if p.position == "ST")
    sim.foul("trip", "careless")
    sim.run_half()
    shot = next(e for e in sim.events if e["event_type"] == "shot")
    assert shot["metadata"]["restart_type"] == "penalty"
    assert shot["timestamp"] > 2700
    assert sim.events[-1]["event_type"] == "whistle"
    assert sim.events[-1]["timestamp"] >= shot["timestamp"]
    assert not any(e["event_type"] == "kickoff" for e in sim.events)


def test_second_yellow_and_direct_red_remove_eligibility(sim):
    player = next(p for p in sim.active["away"] if p.position == "CB")
    sim.issue_card("away", player, "yellow", "reckless")
    assert player in sim.active["away"]
    sim.issue_card("away", player, "yellow", "reckless")
    assert player not in sim.active["away"] and player not in sim.bench["away"]
    assert [e["metadata"]["card_type"] for e in sim.events] == [
        "yellow",
        "yellow",
        "red",
    ]
    player2 = next(p for p in sim.active["away"] if p.position == "CB")
    sim.issue_card("away", player2, "red", "excessive_force")
    assert player2 not in sim.active["away"]
    assert sim.nearest("away", xy(90, 50)) not in [player, player2]
    assert not any(
        p["player_id"] in {player.player_id, player2.player_id} for p in sim.positions()
    )


@pytest.mark.parametrize(
    "foul,severity,restart,dogso,expected",
    [
        ("trip", "careless", "direct_free_kick", False, None),
        ("trip", "reckless", "penalty", False, "yellow"),
        ("contact_tackle", "excessive_force", "penalty", False, "red"),
        ("trip", "careless", "penalty", True, "yellow"),
        ("push", "careless", "penalty", True, "red"),
        ("holding", "careless", "penalty", True, "red"),
        ("trip", "careless", "direct_free_kick", True, "red"),
        ("dangerous_play", "careless", "indirect_free_kick", True, "red"),
    ],
)
def test_discipline_follows_severity_and_supported_dogso(
    foul, severity, restart, dogso, expected
):
    assert foul_card(foul, severity, restart, dogso)[0] == expected


def test_abandonment_below_seven_players(sim):
    for player in list(sim.active["away"])[1:6]:
        sim.issue_card("away", player, "red", "excessive_force")
    assert len(sim.active["away"]) == 6 and sim.abandoned
    sim.run_half()
    assert sim.events[-1]["metadata"]["reason"] == "abandoned"


def test_open_goal_shooting_beats_recycling_extreme_angles_and_pressure():
    open_chance = shooting_assessment(xy(92, 50), 1, "ST", [])
    assert open_chance["strong_opportunity"] and open_chance["probability"] >= 0.9
    assert (
        shooting_assessment(xy(8, 50), -1, "ST", [])["probability"]
        == open_chance["probability"]
    )
    for point in (xy(99, 26), xy(65, 50), xy(90, 5)):
        assert shooting_assessment(point, 1, "ST", [])["probability"] == 0
    assert shooting_assessment(xy(92, 50), 1, "GK", [])["probability"] == 0
    assert (
        shooting_assessment(xy(78, 50), 1, "CM", [])["probability"]
        < open_chance["probability"]
    )
    pressured = shooting_assessment(
        xy(92, 50), 1, "ST", [{"x": 93, "y": 50, "role": "CB"}]
    )
    assert pressured["pressure_count"] == 1 and pressured["blocked_lane"]
    assert pressured["probability"] < open_chance["probability"]


@pytest.mark.parametrize("seed", [101, 202, 303, 42])
def test_new_events_stats_and_evidence_remain_deterministic_and_synchronized(seed):
    match = generate_match(seed)
    assert match.events == generate_match(seed).events
    for cutoff in (400, 2700, match.events[-1]["timestamp"]):
        observed = [e for e in match.events if e["timestamp"] <= cutoff]
        state = calculate_match_state(match.events, through_timestamp=cutoff)
        for side in ("home", "away"):
            events = [e for e in observed if e["team_id"] == side]
            counts = Counter(e["event_type"] for e in events)
            for key, kind in (("score", "goal"), ("shots", "shot"), ("fouls", "foul")):
                assert state[key][side] == counts[kind]
            assert state["shots_on_target"][side] == sum(
                e["metadata"]["on_target"] for e in events if e["event_type"] == "shot"
            )
            for color in ("yellow", "red"):
                assert state[f"{color}_cards"][side] == sum(
                    e["metadata"].get("card_type") == color for e in events
                )
            assert state["possession_seconds"][side] == sum(
                e["duration"] for e in observed if e["possession_team_id"] == side
            )
        for case in detect_cases(match.events, through_timestamp=cutoff):
            assert case["available_timestamp"] <= cutoff
            assert case["case_type"] in {
                "substitution_impact",
                "momentum_shift",
                "missed_opportunity",
            }
    for event in match.events:
        if event["event_type"] == "pass":
            for player in event["metadata"]["release_positions"]:
                assert 0 <= player["x"] <= 100 and 0 <= player["y"] <= 100
        if event["event_type"] == "boundary":
            assert event["metadata"]["whole_ball_crossed"]


def test_dismissed_players_cannot_return_via_substitution_or_receipt(sim):
    sim.clock = 3500
    dismissed = next(p for p in sim.active["away"] if p.position == "CB")
    sim.issue_card("away", dismissed, "red", "excessive_force")
    sim.rng.random = lambda: 0.01
    sim.maybe_substitute()
    assert dismissed not in sim.active["away"] and dismissed not in sim.bench["away"]
    assert len(sim.active["away"]) == 10
    assert all(
        e["metadata"].get("player_in") != dismissed.player_id for e in sim.events
    )
    ids = {p["player_id"] for p in sim.positions()}
    assert dismissed.player_id not in ids


def test_a_clear_better_placed_teammate_is_considered_under_pressure(sim):
    sim.ball = xy(87, 50)
    sim.carrier = next(p for p in sim.active["home"] if p.position == "ST")
    teammate = next(p for p in sim.active["home"] if p.position == "AM")
    positions = [
        {
            "team_id": "home",
            "player_id": sim.carrier.player_id,
            "role": "ST",
            **sim.ball,
        },
        {
            "team_id": "home",
            "player_id": teammate.player_id,
            "role": "AM",
            "x": 96,
            "y": 40,
        },
        {"team_id": "away", "player_id": "blocker", "role": "CB", "x": 90, "y": 50},
    ]
    decision = sim.shooting_decision(positions)
    baseline = shooting_assessment(sim.ball, 1, "ST", positions[-1:], sim.phase())
    assert decision["better_placed_teammate"] == teammate.player_id
    assert decision["probability"] < baseline["probability"]
    sim.ball = xy(94, 50)
    positions = [p for p in positions if p["team_id"] == "home"]
    assert sim.shooting_decision(positions)["probability"] >= 0.9


def test_substitution_snapshot_at_restart_contains_exactly_the_active_players(sim):
    sim.clock = 3500
    sim.rng.random = lambda: 0.01
    # Avoid recursive extra restarts: we are inspecting setup, not the kick.
    sim.pass_ball = lambda **kwargs: None
    sim.restart("away", xy(60, 0), "throw_in", 25)
    setup = next(e for e in sim.events if e["event_type"] == "restart")
    positions = setup["metadata"]["setup_positions"]
    assert {p["player_id"] for p in positions} == {
        p.player_id for side in sim.active.values() for p in side
    }
    assert len(positions) == len({p["player_id"] for p in positions})
    assert all(
        e["timestamp"] <= setup["timestamp"]
        for e in sim.events
        if e["event_type"] == "substitution"
    )


@pytest.mark.parametrize(
    "foul_type",
    [
        "trip",
        "contact_tackle",
        "push",
        "holding",
        "dangerous_play",
        "impeding_without_contact",
    ],
)
def test_foul_incident_snapshot_supports_its_contact_and_restart(sim, foul_type):
    sim.ball = xy(90, 50)
    sim.restart = lambda *args: None
    sim.foul(foul_type, "careless")
    incident = next(e for e in sim.events if e["event_type"] == "foul")
    data = incident["metadata"]
    offender = next(
        p for p in data["player_positions"] if p["player_id"] == incident["player_id"]
    )
    if foul_type in {"dangerous_play", "impeding_without_contact"}:
        assert distance(offender, data["offence_location"]) > 0
        assert data["restart_type"] == "indirect_free_kick"
    else:
        assert xy(offender["x"], offender["y"]) == data["offence_location"]
        assert data["restart_type"] == "penalty"
    assert offender["team_id"] == "away"


def test_foul_cannot_be_attributed_to_an_attacking_or_ineligible_player(sim):
    with pytest.raises(ValueError, match="eligible opposing"):
        sim.foul("trip", "careless", offender=sim.carrier)
    with pytest.raises(ValueError, match="eligible opposing"):
        sim.foul("trip", "careless", offender=sim.bench["away"][1])


def test_a_failed_legal_throw_enters_the_field_before_interception(sim):
    sim.ball = xy(80, 0)
    sim.carrier = next(p for p in sim.active["home"] if p.position == "AM")
    sim.anchor = lambda team, player: xy(82, 10)
    sim.rng.uniform = lambda low, high: (low + high) / 2
    sim.rng.choices = lambda population, **kwargs: [population[0]]
    draws = iter(
        [0.5, 0.5, 0.999, 0]
    )  # normal pass, incomplete; no never-entered out decision
    sim.rng.random = lambda: next(draws)
    sim.pass_ball(restart_type="throw_in")
    event = sim.events[0]
    assert event["metadata"]["outcome"] == "incomplete"
    assert event["metadata"]["failure_reason"] is None
    assert 0 < event["metadata"]["end"]["y"] < 100
    assert any(e["event_type"] == "interception" for e in sim.events)
    assert not any(e["event_type"] == "boundary" for e in sim.events)
