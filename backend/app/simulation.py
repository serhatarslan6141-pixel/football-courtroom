"""A deterministic, deliberately simplified possession-based football simulator.

Coordinates are fixed stadium coordinates (0..100), not team-relative coordinates.
Events are timestamped on completion; start_timestamp/duration record their motion.
All movement, including ball relocation during dead play, is explicit in the log.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from .football_rules import (
    boundary_decision,
    foul_restart,
    free_kick_position,
    offside_context,
    foul_card,
    dogso_context,
)
from .football_decisions import shooting_assessment, lane_clearance


ROLE_ANCHORS = {
    "GK": (6, 50),
    "CB": (23, 50),
    "RB": (30, 80),
    "LB": (30, 20),
    "RWB": (42, 85),
    "LWB": (42, 15),
    "DM": (38, 50),
    "CM": (48, 50),
    "AM": (64, 50),
    "RM": (55, 83),
    "LM": (55, 17),
    "RW": (72, 84),
    "LW": (72, 16),
    "ST": (80, 50),
}


def xy(x: float, y: float) -> Dict[str, float]:
    return {"x": round(max(0, min(100, x)), 2), "y": round(max(0, min(100, y)), 2)}


def distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Distance in metres on the model's 105 x 68 metre pitch."""
    return math.hypot((a["x"] - b["x"]) * 1.05, (a["y"] - b["y"]) * 0.68)


def role_group(position: str) -> str:
    if position == "GK":
        return "keeper"
    if position in {"CB", "RB", "LB", "RWB", "LWB"}:
        return "defender"
    if position in {"DM", "CM", "AM"}:
        return "midfielder"
    return "forward"


class PossessionSimulation:
    def __init__(self, match_id, home, away, rng, style):
        self.match_id, self.rng, self.style = match_id, rng, style
        self.teams = {"home": home, "away": away}
        self.active = {
            side: list(team.players[:11]) for side, team in self.teams.items()
        }
        self.bench = {
            side: list(team.players[11:]) for side, team in self.teams.items()
        }
        self.slots = {}
        for team in self.teams.values():
            for player in team.players:
                same_role = [
                    p for p in team.players[:11] if p.position == player.position
                ]
                x, y = ROLE_ANCHORS[player.position]
                if len(same_role) > 1 and player in same_role:
                    y += (same_role.index(player) - (len(same_role) - 1) / 2) * 24
                self.slots[player.player_id] = (x, y)
        self.events: List[Dict[str, Any]] = []
        self.clock, self.period, self.period_end = 0, 1, 2700
        self.ball = xy(50, 50)
        self.owner = "home"
        self.carrier = self.nearest("home", self.ball, exclude_keeper=True)
        self.sequence = 1
        self.sequence_actions = 0
        self.tempo = rng.uniform(0.8, 1.2)
        self.score = {"home": 0, "away": 0}
        self.subs = {"home": 0, "away": 0}
        self.bookings = {}
        self.in_play = True
        self.last_touch_team = "home"
        self.abandoned = False

    def direction(self, team):
        return (1 if team == "home" else -1) * (1 if self.period == 1 else -1)

    def progress(self, team, location=None):
        x = (location or self.ball)["x"]
        return x if self.direction(team) == 1 else 100 - x

    def from_attack(self, team, progress, y):
        return xy(progress if self.direction(team) == 1 else 100 - progress, y)

    def anchor(self, team, player):
        base_x, base_y = self.slots[player.player_id]
        if player.position != "GK":
            base_x = max(12, min(94, base_x + (self.progress(team) - 50) * 0.48))
        return self.from_attack(
            team, base_x, base_y if self.direction(team) == 1 else 100 - base_y
        )

    def nearest(self, team, location, exclude_keeper=False):
        candidates = [
            p for p in self.active[team] if not exclude_keeper or p.position != "GK"
        ]
        # Goalkeepers participate only close to their own goal.
        if self.progress(team, location) > 18:
            candidates = [p for p in candidates if p.position != "GK"]
        return min(candidates, key=lambda p: distance(self.anchor(team, p), location))

    def positions(self):
        """Explicit synthetic point positions at this decision, never tracking data."""
        return [
            {
                "player_id": p.player_id,
                "team_id": team,
                "role": p.position,
                **(
                    dict(self.ball)
                    if team == self.owner and p == self.carrier
                    else self.anchor(team, p)
                ),
            }
            for team in ("home", "away")
            for p in self.active[team]
        ]

    def shooting_decision(self, positions=None):
        positions = positions or self.positions()
        opponents = [p for p in positions if p["team_id"] != self.owner]
        assessment = shooting_assessment(
            self.ball,
            self.direction(self.owner),
            self.carrier.position,
            opponents,
            self.phase(),
        )
        # Under pressure a clearly better-positioned teammate is a sensible cutback.
        # An unpressured open goal is never recycled just because a teammate exists.
        if assessment["pressure_count"] or assessment["blocked_lane"]:
            for player in positions:
                if (
                    player["team_id"] != self.owner
                    or player["player_id"] == self.carrier.player_id
                ):
                    continue
                other = shooting_assessment(
                    player,
                    self.direction(self.owner),
                    player["role"],
                    opponents,
                    self.phase(),
                )
                if (
                    other["probability"] > assessment["probability"] + 0.25
                    and lane_clearance(self.ball, player, opponents) > 1.3
                ):
                    assessment["probability"] *= 0.55
                    assessment["better_placed_teammate"] = player["player_id"]
                    break
        return assessment

    def resolve_boundary(self, exit_point, last_touch_team=None):
        last_touch_team = last_touch_team or self.last_touch_team
        decision = boundary_decision(
            self.ball, exit_point, last_touch_team, self.direction("home")
        )
        if not decision:
            return False
        self.emit(
            "boundary",
            last_touch_team,
            in_play=False,
            field_exit=exit_point,
            whole_ball_crossed=True,
            last_touch_team=last_touch_team,
            restart_type=decision["kind"],
            awarded_team=decision["team"],
            boundary=decision["boundary"],
            description=f"Ball out of play — {decision['kind'].replace('_', ' ')} to {self.teams[decision['team']].name}.",
        )
        if decision["kind"] == "goal":
            scoring = decision["team"]
            self.score[scoring] += 1
            self.emit(
                "goal",
                scoring,
                in_play=False,
                own_goal=last_touch_team != scoring,
                score=f"{self.score['home']}-{self.score['away']}",
                description=f"Goal for {self.teams[scoring].name}. The ball crosses between the posts and under the bar.",
            )
            conceding = "away" if scoring == "home" else "home"
            self.restart(conceding, xy(50, 50), "kickoff", self.rng.randint(42, 68))
        else:
            self.restart(
                decision["team"],
                decision["location"],
                decision["kind"],
                self.rng.randint(20, 35),
            )
        return True

    def phase(self):
        progress = self.progress(self.owner)
        if self.sequence_actions < 3 and progress > 35:
            return "transition"
        if progress < 35:
            return "defensive_buildup"
        if progress > 60 and (self.ball["y"] < 22 or self.ball["y"] > 78):
            return "wing_progression"
        return "final_third" if progress > 66 else "midfield_passing"

    def emit(
        self,
        event_type,
        team=None,
        player=None,
        duration=0,
        end=None,
        in_play=True,
        **metadata,
    ):
        team = team or self.owner
        start = dict(self.ball)
        end = dict(end or start)
        duration = max(0, min(int(duration), self.period_end - self.clock))
        start_ts = self.clock
        self.clock += duration
        self.ball = end
        metadata = {
            "team_id": team,
            "team_name": self.teams[team].name,
            "team_short_name": self.teams[team].short_name,
            "start": start,
            "end": end,
            "location": start,
            "attack_direction": self.direction(team),
            "phase": self.phase(),
            "possession_seconds": duration if in_play else 0,
            "ball_in_play": in_play,
            "synthetic": True,
            **metadata,
        }
        if player:
            metadata.update(
                player_name=player.name,
                player_id=player.player_id,
                player_role=player.position,
                squad_number=player.squad_number,
            )
        event = {
            "event_id": f"{self.match_id}-evt-{len(self.events):04d}",
            "index": len(self.events),
            "timestamp": self.clock,
            "start_timestamp": start_ts,
            "duration": duration,
            "minute": f"{self.clock // 60:02d}:{self.clock % 60:02d}",
            "event_type": event_type,
            "team_id": team,
            "player_id": player.player_id if player else None,
            "x": start["x"],
            "y": start["y"],
            "period": self.period,
            "possession_id": self.sequence,
            "possession_team_id": self.owner if in_play else None,
            "ball_player_id": self.carrier.player_id if in_play else None,
            "schema_version": 2,
            "synthetic": True,
            "metadata": metadata,
        }
        self.events.append(event)
        return event

    def change_owner(self, team, player, reason, related_event_id=None):
        previous = self.owner
        self.owner, self.carrier = team, player
        self.last_touch_team = team
        self.sequence += 1
        self.sequence_actions = 0
        self.tempo = self.rng.uniform(0.7, 1.4)
        self.emit(
            "possession_change",
            player=player,
            previous_team=previous,
            new_team=team,
            reason=reason,
            related_event_id=related_event_id,
            description=f"{player.name} takes possession for {self.teams[team].name} ({reason.replace('_', ' ')}).",
        )

    def regain(self, team, reason, related, event_type="recovery", player=None):
        player = player or self.nearest(team, self.ball)
        self.emit(
            event_type,
            team,
            player,
            won=True,
            previous_team=self.owner,
            new_team=team,
            related_event_id=related,
            description=f"{player.name} {'intercepts the ball' if event_type == 'interception' else 'collects the loose ball'}.",
        )
        self.change_owner(team, player, reason, related)

    def maybe_substitute(self):
        if self.clock < 3300:
            return
        for side in ("home", "away"):
            if self.subs[side] >= 5 or self.rng.random() > 0.12:
                continue
            pairs = [
                (out, incoming)
                for out in self.active[side]
                for incoming in self.bench[side]
                if out != self.carrier
                and out.position != "GK"
                and role_group(out.position) == role_group(incoming.position)
            ]
            if not pairs:
                continue
            out, incoming = self.rng.choice(pairs)
            self.emit(
                "substitution",
                side,
                out,
                in_play=False,
                player_out=out.player_id,
                player_out_name=out.name,
                player_in=incoming.player_id,
                player_in_name=incoming.name,
                description=f"{incoming.name} replaces {out.name} in the {out.position} role.",
            )
            self.slots[incoming.player_id] = self.slots[out.player_id]
            self.active[side][self.active[side].index(out)] = incoming
            self.bench[side].remove(incoming)
            self.subs[side] += 1

    def restart(self, team, location, kind, pause):
        """Award/setup first, pause at the restart spot, then record the first touch."""
        self.in_play = False
        self.maybe_substitute()
        if kind in {"direct_free_kick", "indirect_free_kick"}:
            location = free_kick_position(
                location, self.direction(team), kind == "indirect_free_kick"
            )
        if kind == "penalty":
            location = self.from_attack(team, 100 - 11 / 105 * 100, 50)
            # Law 14: a penalty must be completed even if the period has expired.
            if self.clock + pause + 1 > self.period_end:
                self.period_end = self.clock + pause + 1
        keeper = next((p for p in self.active[team] if p.position == "GK"), None)
        player = (
            keeper
            if kind == "goal_kick" and keeper
            else self.nearest(team, location, exclude_keeper=True)
        )
        previous = self.owner
        self.owner, self.carrier = team, player
        self.sequence += 1
        self.sequence_actions = 0
        self.tempo = self.rng.uniform(0.8, 1.25)
        setup = self.restart_positions(team, player, location, kind)
        self.emit(
            "kickoff" if kind == "kickoff" else "restart",
            team,
            player,
            end=location,
            in_play=False,
            movement="reset",
            restart_type=kind,
            restart_status="setup",
            previous_team=previous,
            new_team=team,
            setup_positions=setup,
            description=f"{kind.replace('_', ' ').capitalize()} — {self.teams[team].name}. {player.name} prepares the restart.",
        )
        self.emit(
            "stoppage",
            team,
            player,
            duration=pause,
            in_play=False,
            reason=kind,
            restart_type=kind,
            restart_status="setup",
            description=f"{player.name} prepares a {kind.replace('_', ' ')} for {self.teams[team].name}.",
        )
        if self.clock >= self.period_end or self.abandoned:
            return
        self.emit(
            "restart_taken",
            team,
            player,
            in_play=False,
            restart_type=kind,
            description=f"{player.name} takes the {kind.replace('_', ' ')}.",
        )
        self.in_play = True
        self.last_touch_team = team
        if kind == "penalty":
            self.shoot(restart_type=kind)
        elif (
            kind == "direct_free_kick"
            and self.rng.random() < self.shooting_decision()["probability"]
        ):
            self.shoot(restart_type=kind)
        else:
            # First touch must reach a different player: never let a taker dribble
            # his own throw-in/free kick/kickoff, or shoot directly from an IFK.
            self.pass_ball(cross=kind == "corner", restart_type=kind)

    def restart_positions(self, team, taker, location, kind):
        """Legal setup point positions (not interpolated tracking)."""
        positions = self.positions()
        for point in positions:
            if point["player_id"] == taker.player_id:
                point.update(location)
                continue
            own = point["team_id"] == team
            if kind == "penalty":
                if not own and point["role"] == "GK":
                    point.update(self.from_attack(team, 100, 50))
                else:
                    # Behind ball, outside area and penalty arc, inside field.
                    point.update(
                        self.from_attack(
                            team, min(self.progress(team, point), 72), point["y"]
                        )
                    )
            elif kind == "kickoff":
                point["x"] = (
                    min(point["x"], 49)
                    if self.direction(point["team_id"]) == 1
                    else max(point["x"], 51)
                )
                if not own and distance(point, location) < 9.15:
                    point["x"] = 40 if self.direction(point["team_id"]) == 1 else 60
            elif not own:
                if kind == "goal_kick":
                    # Opponents outside the defending penalty area.
                    point.update(
                        self.from_attack(
                            team, max(18, self.progress(team, point)), point["y"]
                        )
                    )
                required = 2.02 if kind == "throw_in" else 9.17
                if distance(point, location) < required:
                    # Move into the field away from the spot; preserve lane where possible.
                    dx, dy = (50 - location["x"]) * 1.05, (50 - location["y"]) * 0.68
                    norm = math.hypot(dx, dy) or 1
                    point.update(
                        xy(
                            location["x"] + dx / norm * required / 1.05,
                            location["y"] + dy / norm * required / 0.68,
                        )
                    )
        return positions

    def pass_ball(self, cross=False, restart_type=None):
        start = self.ball
        self.last_touch_team = self.owner
        release_positions = self.positions()
        if restart_type and self.events:
            # Setup snapshots are the positions at the first touch, including
            # restart-distance restrictions, not unconstrained tactical anchors.
            setup_event = next(
                (
                    e
                    for e in reversed(self.events)
                    if e["metadata"].get("setup_positions")
                ),
                None,
            )
            if setup_event:
                active_ids = {
                    p.player_id for side in self.active.values() for p in side
                }
                release_positions = [
                    p
                    for p in setup_event["metadata"]["setup_positions"]
                    if p["player_id"] in active_ids
                ]
                known = {p["player_id"] for p in release_positions}
                release_positions += [
                    p for p in self.positions() if p["player_id"] not in known
                ]
        opponents = [p for p in release_positions if p["team_id"] != self.owner]
        progress = self.progress(self.owner)
        through = not cross and progress > 45 and self.rng.random() < 0.1
        long_ball = not cross and not through and self.rng.random() < 0.085
        candidates = []
        for recipient in self.active[self.owner]:
            if recipient == self.carrier:
                continue
            if recipient.position == "GK" and progress > 36:
                continue
            if (
                through
                and role_group(recipient.position) != "forward"
                and recipient.position != "AM"
            ):
                continue
            if (
                self.carrier.position == "GK"
                and role_group(recipient.position) != "defender"
            ):
                continue
            target = next(
                (
                    xy(p["x"], p["y"])
                    for p in release_positions
                    if p["player_id"] == recipient.player_id
                ),
                self.anchor(self.owner, recipient),
            )
            if cross:
                if role_group(recipient.position) not in {"forward", "midfielder"}:
                    continue
                target = self.from_attack(
                    self.owner, self.rng.uniform(84, 94), self.rng.uniform(35, 65)
                )
            else:
                target = xy(
                    target["x"] + self.rng.uniform(-4, 4),
                    target["y"] + self.rng.uniform(-5, 5),
                )
                if through:
                    target = self.from_attack(
                        self.owner,
                        min(94, self.progress(self.owner, target) + 8),
                        target["y"],
                    )
            length = distance(start, target)
            if length < 3 or length > (55 if long_ball or cross else 32):
                continue
            forward = self.progress(self.owner, target) - progress
            if through and forward < 8:
                continue
            weight = math.exp(-length / (35 if long_ball else 16)) * (
                1.9 if forward > 2 else 0.75
            )
            clearance = lane_clearance(start, target, opponents)
            weight *= 0.3 if clearance < 1.3 else 1.0
            receiver_context = offside_context(
                start,
                recipient.player_id,
                release_positions,
                self.owner,
                self.direction(self.owner),
                restart_type,
            )
            if receiver_context.get("offside_position") and not receiver_context.get(
                "exempt"
            ):
                weight *= 0.04
            if long_ball:
                weight *= 3 if length > 30 else 0.1
            candidates.append((recipient, target, length, weight))
        if not candidates and restart_type:
            # A legal short restart remains possible even if tactical anchors
            # leave no normal candidate; record the receiver's actual arrival.
            recipient = next(
                p
                for p in self.active[self.owner]
                if p != self.carrier and p.position != "GK"
            )
            target = self.from_attack(
                self.owner,
                max(2, min(96, progress + (5 if progress < 90 else -5))),
                max(4, min(96, start["y"])),
            )
            candidates.append((recipient, target, distance(start, target), 1))
        if not candidates:
            self.carry()
            return
        recipient, target, length, _ = self.rng.choices(
            candidates, weights=[c[3] for c in candidates]
        )[0]
        context = offside_context(
            start,
            recipient.player_id,
            release_positions,
            self.owner,
            self.direction(self.owner),
            restart_type,
        )
        complete = self.rng.random() < max(
            0.5, 0.96 - length * 0.004 - (0.17 if cross else 0.07 if through else 0)
        )
        out = (
            not complete
            # This model generates legal throws that enter the field. A throw
            # which never enters would require a retake, not an opponent's throw.
            and restart_type != "throw_in"
            and (target["y"] < 30 or target["y"] > 70)
            and self.rng.random() < 0.24
        )
        called_offside = (
            complete and context.get("offside_position") and not context.get("exempt")
        )
        if called_offside:
            complete = False
        intended = target
        if out:
            target = xy(target["x"], 0 if target["y"] < 50 else 100)
            length = distance(start, target)
        kind = (
            "cross"
            if cross
            else (
                "through_ball"
                if through
                else (
                    "long_ball" if length > 32 else "short" if length < 15 else "medium"
                )
            )
        )
        event = self.emit(
            "cross" if cross else "pass",
            player=self.carrier,
            duration=max(1, round(length / self.rng.uniform(9, 16))),
            end=target,
            recipient_id=recipient.player_id,
            recipient_name=recipient.name,
            outcome="complete" if complete else "incomplete",
            pass_kind=kind,
            intended_end=intended,
            failure_reason=(
                "offside" if called_offside else "out_of_play" if out else None
            ),
            release_positions=release_positions,
            offside_context=context,
            pass_context=(
                "switch_of_play"
                if abs(target["y"] - start["y"]) > 35
                else (
                    "defensive_distribution"
                    if self.carrier.position == "GK"
                    else (
                        "forward_progression"
                        if self.progress(self.owner, target) > progress
                        else "recycle_possession"
                    )
                )
            ),
            distance=round(length, 1),
            progressive=self.progress(self.owner, target) - progress >= 8,
            restart_type=restart_type,
            description=f"{self.carrier.name} {'finds' if complete else 'cannot find'} {recipient.name} with a {kind.replace('_', ' ')} pass.",
        )
        if complete:
            self.carrier = recipient
        else:
            other = "away" if self.owner == "home" else "home"
            if called_offside:
                self.emit(
                    "offside",
                    self.owner,
                    recipient,
                    in_play=False,
                    related_event_id=event["event_id"],
                    offside_context=context,
                    offence_location=dict(self.ball),
                    release_positions=release_positions,
                    description=f"Offside — {recipient.name} touches the pass after starting beyond the ball and second-last opponent.",
                )
                self.restart(
                    other, self.ball, "indirect_free_kick", self.rng.randint(18, 30)
                )
            elif out:
                self.resolve_boundary(
                    {"x": self.ball["x"], "y": -0.3 if self.ball["y"] == 0 else 100.3},
                    self.owner,
                )
            else:
                self.regain(
                    other, "intercepted_pass", event["event_id"], "interception"
                )

    def carry(self):
        self.last_touch_team = self.owner
        progress = self.progress(self.owner)
        if self.carrier.position == "GK":
            target = self.from_attack(
                self.owner, min(14, progress + self.rng.uniform(1, 3)), self.ball["y"]
            )
        else:
            advance = (
                self.rng.uniform(3, 10) if progress < 88 else self.rng.uniform(-4, 3)
            )
            # Wide players keep their lane; central players can carry into a channel.
            dy = self.rng.uniform(-9, 9)
            target = self.from_attack(
                self.owner,
                min(96, progress + advance),
                max(3, min(97, self.ball["y"] + dy)),
            )
        length = distance(self.ball, target)
        self.emit(
            "dribble" if self.rng.random() < 0.2 else "carry",
            player=self.carrier,
            duration=max(2, round(length / self.rng.uniform(2.5, 4.5))),
            end=target,
            progressive=self.progress(self.owner, target) - progress >= 5,
            description=f"{self.carrier.name} carries the ball into space.",
        )

    def challenge(self):
        other = "away" if self.owner == "home" else "home"
        defender = self.nearest(other, self.ball, exclude_keeper=True)
        old = self.carrier
        won = self.rng.random() < 0.6
        event = self.emit(
            "tackle",
            other,
            defender,
            duration=1,
            won=won,
            opponent_id=old.player_id,
            opponent_name=old.name,
            description=f"{defender.name} {'wins the ball from' if won else 'challenges'} {old.name}.",
        )
        if won:
            self.change_owner(other, defender, "tackle", event["event_id"])

    def issue_card(self, team, player, card, reason):
        if card == "yellow":
            self.bookings[player.player_id] = self.bookings.get(player.player_id, 0) + 1
        self.emit(
            "card",
            team,
            player,
            in_play=False,
            card_type=card,
            reason=reason,
            description=f"{player.name} receives a {card} card ({reason.replace('_', ' ')}).",
        )
        if card == "yellow" and self.bookings[player.player_id] == 2:
            self.issue_card(team, player, "red", "second_yellow")
        elif card == "red":
            self.active[team].remove(player)
            if len(self.active[team]) < 7:
                self.abandoned = True
            # No replacements for dismissals. If ever needed, an outfield
            # player would have to become keeper; keep GK fouls out of this model.

    def foul(self, foul_type=None, severity=None, offender=None):
        other = "away" if self.owner == "home" else "home"
        defender = offender or self.nearest(other, self.ball, exclude_keeper=True)
        if defender not in self.active[other]:
            raise ValueError("The offender must be an eligible opposing player")
        foul_type = (
            foul_type
            or self.rng.choices(
                [
                    "trip",
                    "contact_tackle",
                    "push",
                    "holding",
                    "dangerous_play",
                    "impeding_without_contact",
                ],
                weights=[35, 35, 10, 5, 10, 5],
            )[0]
        )
        # Physical severity determines sanctions; cards are not an independent coin toss.
        severity = severity or (
            self.rng.choices(
                ["careless", "reckless", "excessive_force"], weights=[76, 23, 1]
            )[0]
            if foul_type in {"trip", "contact_tackle", "push"}
            else "careless"
        )
        kind = foul_restart(foul_type, self.ball, self.direction(other), self.in_play)
        if kind is None:
            return
        foul_positions = self.positions()
        # The offence snapshot describes the incident, not a distant role anchor.
        # These are discrete simulated points, not a reconstructed approach run.
        for point in foul_positions:
            if point["player_id"] == defender.player_id:
                point.update(
                    self.ball
                    if foul_type not in {"dangerous_play", "impeding_without_contact"}
                    else xy(
                        self.ball["x"],
                        self.ball["y"] + (-3 if self.ball["y"] > 50 else 3),
                    )
                )
        opponents = [p for p in foul_positions if p["team_id"] == other]
        last_move = next(
            (
                e
                for e in reversed(self.events)
                if e["event_type"] in {"pass", "cross", "carry", "dribble"}
            ),
            None,
        )
        moving = bool(
            last_move
            and last_move["possession_id"] == self.sequence
            and self.progress(self.owner, last_move["metadata"]["end"])
            > self.progress(self.owner, last_move["metadata"]["start"])
        )
        dogso = dogso_context(
            self.ball, self.direction(self.owner), defender.player_id, opponents, moving
        )
        promising = moving and self.progress(self.owner) > 55 and foul_type == "holding"
        self.emit(
            "foul",
            other,
            defender,
            duration=1,
            dogso_context=dogso,
            stops_promising_attack=promising,
            player_positions=foul_positions,
            foul_type=foul_type,
            severity=severity,
            restart_type=kind,
            opponent_id=self.carrier.player_id,
            opponent_name=self.carrier.name,
            offence_location=dict(self.ball),
            description=f"{defender.name}: {foul_type.replace('_', ' ')} on {self.carrier.name}. {kind.replace('_', ' ').capitalize()}.",
        )
        self.in_play = False
        card, reason = foul_card(foul_type, severity, kind, dogso["obvious"], promising)
        if card:
            self.issue_card(other, defender, card, reason)
        if not self.abandoned:
            self.restart(self.owner, self.ball, kind, self.rng.randint(25, 45))

    def clear(self):
        self.last_touch_team = self.owner
        target = self.from_attack(
            self.owner,
            min(78, self.progress(self.owner) + self.rng.uniform(28, 48)),
            self.rng.uniform(15, 85),
        )
        event = self.emit(
            "clearance",
            player=self.carrier,
            duration=3,
            end=target,
            description=f"{self.carrier.name} clears the ball upfield.",
        )
        next_team = (
            self.owner
            if self.rng.random() < 0.3
            else ("away" if self.owner == "home" else "home")
        )
        self.regain(next_team, "clearance_recovery", event["event_id"])

    def shoot(self, restart_type=None):
        assessment = self.shooting_decision()
        quality = (
            "good"
            if assessment["strong_opportunity"] or restart_type == "penalty"
            else "speculative"
        )
        self.last_touch_team = self.owner
        on_target = self.rng.random() < (
            0.88 if restart_type == "penalty" else 0.52 if quality == "good" else 0.30
        )
        goal = on_target and self.rng.random() < (
            0.85 if restart_type == "penalty" else 0.33 if quality == "good" else 0.18
        )
        outcome = "goal" if goal else "saved" if on_target else "off_target"
        target_y = (
            self.rng.uniform(45, 55)
            if on_target
            else self.rng.choice([self.rng.uniform(36, 43), self.rng.uniform(57, 64)])
        )
        target = self.from_attack(self.owner, 100, target_y)
        end = (
            self.from_attack(self.owner, 97, target_y) if outcome == "saved" else target
        )
        player = self.carrier
        attacking, defending = self.owner, "away" if self.owner == "home" else "home"
        event = self.emit(
            "shot",
            player=player,
            duration=1,
            end=end,
            target=target,
            outcome=outcome,
            on_target=on_target,
            whole_ball_crossed=outcome != "saved",
            field_exit=(
                {"x": 100.2 if self.direction(attacking) == 1 else -0.2, "y": target_y}
                if outcome != "saved"
                else None
            ),
            shot_quality=quality,
            decision_context=assessment,
            shot_distance_m=round(distance(self.ball, target), 1),
            restart_type=restart_type,
            description=f"{player.name} shoots {'and scores' if goal else 'but the goalkeeper saves' if on_target else 'wide of goal'}.",
        )
        if goal:
            self.score[attacking] += 1
            self.emit(
                "goal",
                player=player,
                related_event_id=event["event_id"],
                whole_ball_crossed=True,
                field_exit=event["metadata"]["field_exit"],
                score=f"{self.score['home']}-{self.score['away']}",
                description=f"{player.name} scores for {self.teams[attacking].name}.",
            )
            if self.clock < self.period_end:
                self.restart(defending, xy(50, 50), "kickoff", self.rng.randint(42, 68))
        elif on_target:
            keeper = next(p for p in self.active[defending] if p.position == "GK")
            parried = self.clock < self.period_end and self.rng.random() < 0.22
            self.emit(
                "save",
                defending,
                keeper,
                related_event_id=event["event_id"],
                outcome="parried" if parried else "held",
                description=f"{keeper.name} {'turns the shot behind for a corner' if parried else 'holds the shot'}.",
            )
            if parried and self.clock < self.period_end:
                # The keeper's recorded deflection actually reaches the goal line;
                # the last touch and whole-ball crossing justify the corner.
                wide_y = self.rng.choice(
                    [self.rng.uniform(36, 43), self.rng.uniform(57, 64)]
                )
                end = self.from_attack(attacking, 100, wide_y)
                self.emit(
                    "deflection",
                    defending,
                    keeper,
                    duration=1,
                    end=end,
                    related_event_id=event["event_id"],
                    description=f"{keeper.name} deflects the ball over the goal line.",
                )
                self.last_touch_team = defending
                self.resolve_boundary(
                    {
                        "x": 100.2 if self.direction(attacking) == 1 else -0.2,
                        "y": wide_y,
                    },
                    defending,
                )
            else:
                self.change_owner(
                    defending, keeper, "goalkeeper_save", event["event_id"]
                )
        elif self.clock < self.period_end:
            self.resolve_boundary(
                {"x": 100.2 if self.direction(attacking) == 1 else -0.2, "y": target_y},
                attacking,
            )

    def run_half(self):
        while self.clock < self.period_end - 6 and not self.abandoned:
            progress = self.progress(self.owner)
            # Touch/control time varies with the possession's tempo, rather than a metronome.
            self.emit(
                "ball_control",
                player=self.carrier,
                duration=max(1, round(self.rng.triangular(1, 4, 1.5) / self.tempo)),
                description=f"{self.carrier.name} controls the ball.",
            )
            if self.clock >= self.period_end - 4:
                break
            self.sequence_actions += 1
            chance = self.rng.random()
            if chance < 0.022:
                self.foul()
                continue
            if chance < 0.062:
                self.challenge()
                continue
            if self.rng.random() < (0.18 if self.style == "pressing" else 0.12):
                other = "away" if self.owner == "home" else "home"
                defender = self.nearest(other, self.ball, exclude_keeper=True)
                self.emit(
                    "pressure_event",
                    other,
                    defender,
                    duration=1,
                    intensity=self.rng.uniform(1, 3),
                    description=f"{defender.name} presses {self.carrier.name} on the ball.",
                )
            if self.rng.random() < self.shooting_decision()["probability"]:
                self.shoot()
            elif (
                progress < 24
                and self.carrier.position != "GK"
                and self.rng.random() < 0.09
            ):
                self.clear()
            elif (
                progress > 68
                and (self.ball["y"] < 22 or self.ball["y"] > 78)
                and self.rng.random() < 0.32
            ):
                self.pass_ball(cross=True)
            elif self.rng.random() < 0.28:
                self.carry()
            else:
                self.pass_ball()
            # Miscontrol near a touchline leads to an actual throw-in, not a midfield reset.
            if (
                (self.ball["y"] < 18 or self.ball["y"] > 82)
                and self.rng.random() < 0.12
                and self.clock < self.period_end - 3
            ):
                line = xy(self.ball["x"], 0 if self.ball["y"] < 50 else 100)
                self.emit(
                    "miscontrol",
                    player=self.carrier,
                    duration=max(1, round(distance(self.ball, line) / 8)),
                    end=line,
                    outcome="out",
                    description=f"{self.carrier.name} loses the ball over the touchline.",
                )
                self.last_touch_team = self.owner
                self.resolve_boundary(
                    {"x": line["x"], "y": -0.3 if line["y"] == 0 else 100.3}, self.owner
                )
        if self.clock < self.period_end and not self.abandoned:
            self.emit(
                "ball_control" if self.in_play else "stoppage",
                player=self.carrier,
                duration=self.period_end - self.clock,
                in_play=self.in_play,
                description=f"{self.carrier.name} holds the ball as the half ends.",
            )
        self.emit(
            "whistle",
            in_play=False,
            reason=(
                "abandoned"
                if self.abandoned
                else "half_time" if self.period == 1 else "full_time"
            ),
            score=f"{self.score['home']}-{self.score['away']}",
            description=(
                "Match abandoned: fewer than seven players."
                if self.abandoned
                else (
                    "Half time."
                    if self.period == 1
                    else "The referee blows for full time."
                )
            ),
        )

    def run(self):
        self.restart("home", xy(50, 50), "kickoff", 0)
        self.run_half()
        if not self.abandoned:
            # Extra time required to complete a penalty does not shorten half two.
            self.period, self.period_end = 2, self.clock + 2700
            self.restart("away", xy(50, 50), "kickoff", 0)
            self.run_half()
        return self.events


def simulate_match(match_id, home, away, rng, style):
    return PossessionSimulation(match_id, home, away, rng, style).run()
