"""Small, pure IFAB rule predicates for the supported point-player model.

Distances use a 105 x 68 m pitch. Player points stand for playable body parts;
height, interfering with opponents, rebounds and deliberate-play resets are not
simulated. Offside here means the intended receiver actually touches the pass.
"""

LENGTH, WIDTH = 105.0, 68.0
BALL_RADIUS = 0.11
DIRECT_FOULS = {"trip", "push", "holding", "contact_tackle"}
INDIRECT_FOULS = {"dangerous_play", "impeding_without_contact"}
OFFSIDE_EXEMPT_RESTARTS = {"throw_in", "goal_kick", "corner"}


def progress(point, direction):
    return point["x"] if direction == 1 else 100 - point["x"]


def penalty_area(point, defending_direction):
    return (
        progress(point, defending_direction) * LENGTH / 100 <= 16.5 + 1e-8
        and abs(point["y"] - 50) * WIDTH / 100 <= 20.16 + 1e-8
    )


def foul_restart(foul_type, point, defending_direction, ball_in_play=True):
    if foul_type not in DIRECT_FOULS | INDIRECT_FOULS:
        raise ValueError(f"Unsupported foul: {foul_type}")
    if not ball_in_play:
        return None
    if foul_type in INDIRECT_FOULS:
        return "indirect_free_kick"
    return "penalty" if penalty_area(point, defending_direction) else "direct_free_kick"


def free_kick_position(point, team_direction, indirect=False):
    """Law 13 goal-area exceptions; all other free kicks use the offence point."""
    point = dict(point)
    attacking_progress = progress(point, team_direction)
    inside_goal_area = abs(point["y"] - 50) * WIDTH / 100 <= 9.16
    if inside_goal_area and indirect and attacking_progress >= 100 - 5.5 / LENGTH * 100:
        point["x"] = (
            (100 - 5.5 / LENGTH * 100) if team_direction == 1 else 5.5 / LENGTH * 100
        )
    # A defending free kick inside its own goal area may stay at the offence spot.
    return {axis: round(value, 2) for axis, value in point.items()}


def boundary_decision(start, exit_point, last_touch_team, home_direction, height_m=0):
    """First boundary wholly crossed, including ball radius (a line touch is in).

    Public event geometry projects the exit to the field edge; exit_point keeps
    the unprojected centre proving the whole ball crossed. All generated exits
    are ground balls; callers can explicitly provide height for a ball over goal.
    """
    crossings = []
    for axis, metres in (("x", LENGTH), ("y", WIDTH)):
        radius = BALL_RADIUS / metres * 100
        delta = exit_point[axis] - start[axis]
        if not delta:
            continue
        for edge, threshold in ((0, -radius), (100, 100 + radius)):
            if (edge == 0 and exit_point[axis] < threshold) or (
                edge == 100 and exit_point[axis] > threshold
            ):
                fraction = (threshold - start[axis]) / delta
                if 0 <= fraction <= 1:
                    crossings.append((fraction, axis, edge))
    if not crossings:
        return None
    fraction, axis, edge = min(crossings)
    point = {
        key: max(0, min(100, start[key] + (exit_point[key] - start[key]) * fraction))
        for key in ("x", "y")
    }
    point[axis] = edge
    point = {key: round(value, 2) for key, value in point.items()}
    other = "away" if last_touch_team == "home" else "home"
    if axis == "y":
        return {
            "kind": "throw_in",
            "team": other,
            "location": point,
            "boundary": "touchline",
        }
    defending = "home" if edge == (0 if home_direction == 1 else 100) else "away"
    if (
        abs(point["y"] - 50) * WIDTH / 100 < 3.66 - BALL_RADIUS
        and height_m < 2.44 - BALL_RADIUS
    ):
        return {
            "kind": "goal",
            "team": "away" if defending == "home" else "home",
            "location": point,
            "boundary": "goal_line",
        }
    corner = last_touch_team == defending
    awarded = other if corner else defending
    location = (
        {"x": edge, "y": 0 if point["y"] < 50 else 100}
        if corner
        else {"x": 3 if edge == 0 else 97, "y": 50}
    )
    return {
        "kind": "corner" if corner else "goal_kick",
        "team": awarded,
        "location": location,
        "boundary": "goal_line",
    }


def offside_context(
    ball, receiver_id, positions, attacking_team, direction, restart_type=None
):
    defenders = [p for p in positions if p["team_id"] != attacking_team]
    receiver = next(p for p in positions if p["player_id"] == receiver_id)
    # The match is abandoned before fewer than seven players; this guard also
    # makes the helper safe for incomplete external snapshots.
    if len(defenders) < 2:
        return {"offside_position": False, "supported": False}
    second_last = sorted((progress(p, direction) for p in defenders), reverse=True)[1]
    receiver_progress, ball_progress = progress(receiver, direction), progress(
        ball, direction
    )
    in_position = (
        receiver_progress > 50
        and receiver_progress > max(ball_progress, second_last) + 1e-8
    )
    return {
        "supported": True,
        "offside_position": in_position,
        "exempt": restart_type in OFFSIDE_EXEMPT_RESTARTS,
        "receiver_id": receiver_id,
        "receiver_position": {k: receiver[k] for k in ("x", "y")},
        "ball_position": dict(ball),
        "second_last_defender_progress": round(second_last, 4),
        "offside_line_x": second_last if direction == 1 else 100 - second_last,
        "attack_direction": direction,
    }


def disciplinary_card(severity):
    if severity not in {"careless", "reckless", "excessive_force"}:
        raise ValueError("Unsupported severity")
    return {"careless": None, "reckless": "yellow", "excessive_force": "red"}[severity]


def dogso_context(ball, direction, offender_id, opponents, moving_towards_goal):
    """Conservative DOGSO subset: controlled ball, goalward motion, short central
    approach and no covering outfielder. Other tactical offences are not inferred.
    """
    distance_to_goal = (100 - progress(ball, direction)) * LENGTH / 100
    covering = [
        p
        for p in opponents
        if p["player_id"] != offender_id
        and p.get("role") != "GK"
        and progress(p, direction) >= progress(ball, direction)
        and abs(p["y"] - ball["y"]) * WIDTH / 100 <= 12
    ]
    obvious = (
        moving_towards_goal
        and 0 < distance_to_goal < 25
        and abs(ball["y"] - 50) * WIDTH / 100 < 12
        and not covering
    )
    return {
        "obvious": bool(obvious),
        "moving_towards_goal": bool(moving_towards_goal),
        "controlled_ball": True,
        "distance_to_goal_m": round(distance_to_goal, 2),
        "covering_outfield_ids": [p["player_id"] for p in covering],
    }


def foul_card(
    foul_type, severity, restart_type, dogso=False, stops_promising_attack=False
):
    physical = disciplinary_card(severity)
    if physical == "red":
        return "red", "excessive_force"
    attempts_ball = foul_type in {"trip", "contact_tackle"}
    if dogso:
        return (
            ("yellow", "dogso_penalty_attempt_to_play_ball")
            if restart_type == "penalty" and attempts_ball
            else ("red", "dogso")
        )
    if physical:
        return physical, severity
    if stops_promising_attack and not (restart_type == "penalty" and attempts_ball):
        return "yellow", "stopping_promising_attack"
    return None, None
