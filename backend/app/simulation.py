"""A deterministic, deliberately simplified possession-based football simulator.

Coordinates are fixed stadium coordinates (0..100), not team-relative coordinates.
Events are timestamped on completion; start_timestamp/duration record their motion.
All movement, including ball relocation during dead play, is explicit in the log.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List


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
        self.emit(
            "stoppage",
            duration=pause,
            in_play=False,
            reason=kind,
            description=f"Play is stopped for {kind.replace('_', ' ')}.",
        )
        self.maybe_substitute()
        if self.clock >= self.period_end:
            return
        self.carrier = (
            next(p for p in self.active[team] if p.position == "GK")
            if kind == "goal_kick"
            else self.nearest(team, location, exclude_keeper=True)
        )
        previous = self.owner
        self.owner = team
        self.sequence += 1
        self.sequence_actions = 0
        self.tempo = self.rng.uniform(0.8, 1.25)
        self.emit(
            "kickoff" if kind == "kickoff" else "restart",
            team,
            self.carrier,
            end=location,
            in_play=False,
            movement="reset",
            restart_type=kind,
            previous_team=previous,
            new_team=team,
            description=f"{self.teams[team].name} restart with a {kind.replace('_', ' ')}.",
        )
        if kind == "corner":
            self.pass_ball(cross=True, restart_type=kind)
        elif (
            kind == "free_kick"
            and self.progress(team) > 78
            and 28 < self.ball["y"] < 72
            and self.rng.random() < 0.3
        ):
            self.shoot(restart_type=kind)

    def pass_ball(self, cross=False, restart_type=None):
        start = self.ball
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
            target = self.anchor(self.owner, recipient)
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
            if long_ball:
                weight *= 3 if length > 30 else 0.1
            candidates.append((recipient, target, length, weight))
        if not candidates:
            self.carry()
            return
        recipient, target, length, _ = self.rng.choices(
            candidates, weights=[c[3] for c in candidates]
        )[0]
        complete = self.rng.random() < max(
            0.5, 0.96 - length * 0.004 - (0.17 if cross else 0.07 if through else 0)
        )
        out = (
            not complete
            and (target["y"] < 30 or target["y"] > 70)
            and self.rng.random() < 0.24
        )
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
            failure_reason="out_of_play" if out else None,
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
            if out:
                self.restart(other, self.ball, "throw_in", self.rng.randint(20, 35))
            else:
                self.regain(
                    other, "intercepted_pass", event["event_id"], "interception"
                )

    def carry(self):
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

    def foul(self):
        other = "away" if self.owner == "home" else "home"
        defender = self.nearest(other, self.ball, exclude_keeper=True)
        self.emit(
            "foul",
            other,
            defender,
            duration=1,
            opponent_id=self.carrier.player_id,
            opponent_name=self.carrier.name,
            description=f"{defender.name} fouls {self.carrier.name}.",
        )
        if self.rng.random() < 0.22:
            self.bookings[defender.player_id] = (
                self.bookings.get(defender.player_id, 0) + 1
            )
            self.emit(
                "card",
                other,
                defender,
                card_type="yellow",
                description=f"{defender.name} receives a yellow card.",
            )
            if self.bookings[defender.player_id] == 2:
                self.emit(
                    "card",
                    other,
                    defender,
                    card_type="red",
                    reason="second_yellow",
                    description=f"{defender.name} is sent off for a second yellow.",
                )
                self.active[other].remove(defender)
        self.restart(self.owner, self.ball, "free_kick", self.rng.randint(25, 45))

    def clear(self):
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
        progress = self.progress(self.owner)
        quality = (
            "good" if progress > 84 and abs(self.ball["y"] - 50) < 18 else "speculative"
        )
        on_target = self.rng.random() < (0.44 if quality == "good" else 0.30)
        goal = on_target and self.rng.random() < (0.33 if quality == "good" else 0.18)
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
            shot_quality=quality,
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
                score=f"{self.score['home']}-{self.score['away']}",
                description=f"{player.name} scores for {self.teams[attacking].name}.",
            )
            self.restart(defending, xy(50, 50), "kickoff", self.rng.randint(42, 68))
        elif on_target:
            keeper = next(p for p in self.active[defending] if p.position == "GK")
            parried = self.rng.random() < 0.22
            self.emit(
                "save",
                defending,
                keeper,
                related_event_id=event["event_id"],
                outcome="parried" if parried else "held",
                description=f"{keeper.name} {'turns the shot behind for a corner' if parried else 'holds the shot'}.",
            )
            if parried:
                self.restart(
                    attacking,
                    self.from_attack(attacking, 100, self.rng.choice([0, 100])),
                    "corner",
                    self.rng.randint(25, 45),
                )
            else:
                self.change_owner(
                    defending, keeper, "goalkeeper_save", event["event_id"]
                )
        else:
            self.restart(
                defending,
                self.from_attack(defending, 6, 50),
                "goal_kick",
                self.rng.randint(25, 45),
            )

    def run_half(self):
        while self.clock < self.period_end - 6:
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
            if (
                self.carrier.position != "GK"
                and progress >= 76
                and 25 < self.ball["y"] < 75
                and self.rng.random() < 0.13
            ):
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
                other = "away" if self.owner == "home" else "home"
                self.restart(other, line, "throw_in", self.rng.randint(20, 35))
        if self.clock < self.period_end:
            self.emit(
                "ball_control",
                player=self.carrier,
                duration=self.period_end - self.clock,
                description=f"{self.carrier.name} holds the ball as the half ends.",
            )
        self.emit(
            "whistle",
            in_play=False,
            reason="half_time" if self.period == 1 else "full_time",
            score=f"{self.score['home']}-{self.score['away']}",
            description=(
                "Half time." if self.period == 1 else "The referee blows for full time."
            ),
        )

    def run(self):
        self.emit(
            "kickoff",
            player=self.carrier,
            in_play=False,
            end=xy(50, 50),
            movement="reset",
            restart_type="kickoff",
            previous_team="home",
            new_team="home",
            description=f"{self.teams['home'].name} kick off.",
        )
        self.run_half()
        self.period, self.period_end = 2, 5400
        self.restart("away", xy(50, 50), "kickoff", 0)
        self.run_half()
        return self.events


def simulate_match(match_id, home, away, rng, style):
    return PossessionSimulation(match_id, home, away, rng, style).run()
