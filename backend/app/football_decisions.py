"""Deterministic, tunable football decisions; no model calls or hidden randomness."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionTuning:
    pressure_metres: float = 4.0
    lane_metres: float = 1.3
    maximum_shot_metres: float = 28.0
    minimum_angle_radians: float = 0.11
    open_chance_probability: float = 0.92
    close_chance_probability: float = 0.98


TUNING = DecisionTuning()


def metres(point):
    return point["x"] * 1.05, point["y"] * 0.68


def lane_clearance(start, end, opponents):
    ax, ay = metres(start)
    bx, by = metres(end)
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    clearances = []
    for player in opponents:
        px, py = metres(player)
        fraction = ((px - ax) * dx + (py - ay) * dy) / max(0.001, length2)
        if 0.05 < fraction < 0.95:
            clearances.append(
                math.hypot(px - ax - fraction * dx, py - ay - fraction * dy)
            )
    return min(clearances, default=100.0)


def shooting_assessment(
    ball, direction, role, opponents, phase="final_third", tuning=TUNING
):
    bx, by = metres(ball)
    gx = 105 if direction == 1 else 0
    dx, dy = abs(gx - bx), 34 - by
    distance = math.hypot(dx, dy)
    angle = math.atan2(7.32 * dx, dx * dx + (30.34 - by) * (37.66 - by))
    pressure = sum(
        math.dist((bx, by), metres(p)) < tuning.pressure_metres for p in opponents
    )
    outfield = [p for p in opponents if p.get("role") != "GK"]
    blocked = (
        lane_clearance(ball, {"x": 100 if direction == 1 else 0, "y": 50}, outfield)
        < tuning.lane_metres
    )
    progress = ball["x"] if direction == 1 else 100 - ball["x"]
    eligible = (
        role != "GK"
        and progress >= 76
        and 25 < ball["y"] < 75
        and distance <= tuning.maximum_shot_metres
        and angle >= tuning.minimum_angle_radians
    )
    if not eligible:
        probability = 0.0
    elif distance < 9 and angle > 0.5:
        probability = tuning.close_chance_probability
    elif distance < 16 and angle > 0.4:
        probability = tuning.open_chance_probability
    else:
        probability = min(0.38, 0.04 + 0.25 * angle + max(0, 22 - distance) * 0.006)
    if pressure:
        probability *= 0.78
    if blocked:
        probability *= 0.65
    if role in {"ST", "AM", "RW", "LW"}:
        probability = min(0.99, probability * 1.03)
    if phase == "transition":
        probability = min(0.99, probability * 1.02)
    return {
        "eligible": eligible,
        "probability": round(probability, 4),
        "distance_m": round(distance, 2),
        "angle_radians": round(angle, 4),
        "pressure_count": pressure,
        "blocked_lane": blocked,
        "strong_opportunity": eligible and distance < 16 and angle > 0.4,
    }
