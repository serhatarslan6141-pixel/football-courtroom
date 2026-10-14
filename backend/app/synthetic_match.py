from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

PITCH_MIN = 0
PITCH_MAX = 100
EVENT_TYPES = {
    "kickoff",
    "pass",
    "cross",
    "tackle",
    "foul",
    "shot",
    "goal",
    "save",
    "possession_change",
    "pressure_event",
    "substitution",
    "card",
    "whistle",
}

TEAM_CONFIG = [
    {
        "team_id": "home",
        "name": "Northbridge City",
        "short_name": "NBC",
        "formation": "4-3-3",
        "primary_color": "#7c3aed",
        "secondary_color": "#fbbf24",
    },
    {
        "team_id": "away",
        "name": "Harbor Athletic",
        "short_name": "HBA",
        "formation": "4-2-3-1",
        "primary_color": "#34d399",
        "secondary_color": "#fbbf24",
    },
]

PLAYER_NAME_BANK = [
    "Ari Moss",
    "Noah Vale",
    "Theo Quinn",
    "Milo Ash",
    "Jude Rowe",
    "Rafi Stern",
    "Levi Hume",
    "Owen Pike",
    "Samir Lark",
    "Kian Wren",
    "Ezra Flint",
    "Nico Hart",
    "Adrian Hale",
    "Felix Wren",
    "Gideon Pike",
    "Dorian Vale",
    "Silas Thorn",
    "Tariq Noble",
    "Emil West",
    "Callum Dune",
    "Yusuf Morrow",
    "Bruno Slate",
    "Tomas Reed",
    "Mason Frost",
    "Eli Sloane",
    "Ivo Grant",
    "Jasper Cale",
    "Leandro Bloom",
    "Soren Vale",
    "Ethan Pruitt",
    "Dante Lune",
    "Aaron Flint",
    "Lucan Cress",
    "Alden Pike",
    "Hugo Rowan",
    "Milan Sloane",
    "Kellan Quill",
]


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    position: str
    squad_number: int


@dataclass(frozen=True)
class Team:
    team_id: str
    name: str
    short_name: str
    formation: str
    primary_color: str
    secondary_color: str
    players: List[Player]


@dataclass
class SyntheticMatch:
    match_id: str
    seed: int
    synthetic: bool
    created_at: str
    home_team: Team
    away_team: Team
    events: List[Dict[str, Any]] = field(default_factory=list)

    def as_metadata(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "seed": self.seed,
            "synthetic": self.synthetic,
            "created_at": self.created_at,
            "home_team": self.home_team.name,
            "away_team": self.away_team.name,
            "home_short_name": self.home_team.short_name,
            "away_short_name": self.away_team.short_name,
            "status": "live",
        }


def _clock_text(total_seconds: int) -> str:
    minute, second = divmod(total_seconds, 60)
    return f"{minute:02d}:{second:02d}"


def _pitch_xy(rng: random.Random, x_bias: float = 50.0, y_bias: float = 50.0) -> Dict[str, float]:
    x = max(PITCH_MIN, min(PITCH_MAX, rng.uniform(max(0, x_bias - 35), min(100, x_bias + 35))))
    y = max(PITCH_MIN, min(PITCH_MAX, rng.uniform(max(0, y_bias - 25), min(100, y_bias + 25))))
    return {"x": round(x, 2), "y": round(y, 2)}


def _make_team(team_config: Dict[str, Any], rng: random.Random, team_id_suffix: str) -> Team:
    player_names = list(PLAYER_NAME_BANK)
    rng.shuffle(player_names)
    formation = team_config["formation"]
    positions = {
        "4-3-3": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "AM", "RW", "ST", "LW"],
        "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "DM", "DM", "AM", "RW", "LW", "ST"],
    }.get(formation, ["GK", "RB", "CB", "CM", "LB", "CM", "AM", "RW", "ST", "LW", "CF"])
    players = [
        Player(
            player_id=f"{team_config['team_id']}-{idx:02d}",
            name=player_names[idx],
            position=positions[idx],
            squad_number=idx + 1,
        )
        for idx in range(11)
    ]
    return Team(
        team_id=f"{team_id_suffix}",
        name=team_config["name"],
        short_name=team_config["short_name"],
        formation=formation,
        primary_color=team_config["primary_color"],
        secondary_color=team_config["secondary_color"],
        players=players,
    )


def _append_event(
    events: List[Dict[str, Any]],
    *,
    match_id: str,
    team_id: str,
    event_type: str,
    timestamp: int,
    player_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    index: Optional[int] = None,
) -> None:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")
    if index is None:
        index = len(events)
    event: Dict[str, Any] = {
        "event_id": f"{match_id}-evt-{index:04d}",
        "index": index,
        "timestamp": timestamp,
        "minute": _clock_text(timestamp),
        "team_id": team_id,
        "event_type": event_type,
        "player_id": player_id,
        "synthetic": True,
    }
    if x is not None:
        event["x"] = round(float(x), 2)
    if y is not None:
        event["y"] = round(float(y), 2)
    if metadata:
        event["metadata"] = metadata
    events.append(event)


def _make_team_players(team: Team, rng: random.Random, home_bias: bool) -> Dict[str, Any]:
    return {
        "players": team.players,
        "eligible_players": [player.player_id for player in team.players],
        "bench": [],
        "home_bias": home_bias,
        "active": [player.player_id for player in team.players],
    }


def generate_match(seed: int, match_id: Optional[str] = None) -> SyntheticMatch:
    rng = random.Random(seed)
    home_config = TEAM_CONFIG[0]
    away_config = TEAM_CONFIG[1]
    home_team = _make_team(home_config, rng, "home")
    away_team = _make_team(away_config, rng, "away")
    match_identifier = match_id or f"synthetic-{seed}"
    now = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    events: List[Dict[str, Any]] = []
    home_score = 0
    away_score = 0
    current_possession = "home"
    home_pressure = 0
    away_pressure = 0
    home_subs = 0
    away_subs = 0

    kickoff_time = 0
    _append_event(
        events,
        match_id=match_identifier,
        team_id="home",
        event_type="kickoff",
        timestamp=kickoff_time,
        metadata={"synthetic": True, "starting_team": "home", "description": "Synthetic kickoff"},
        x=50.0,
        y=50.0,
    )

    for minute in range(0, 91, 2):
        if minute >= 90:
            break
        segment_start = minute * 60
        pressure_window = 3 if minute > 70 else 2
        for _ in range(rng.randint(1, 3)):
            team_id = current_possession
            player = rng.choice(home_team.players if team_id == "home" else away_team.players)
            x = 25.0 if team_id == "home" else 75.0
            y = rng.uniform(15, 85)
            pass_outcome = "complete" if rng.random() < 0.76 else "incomplete"
            pass_short = rng.random() < 0.7
            _append_event(
                events,
                match_id=match_identifier,
                team_id=team_id,
                event_type="pass",
                timestamp=segment_start + rng.randint(10, 45),
                player_id=player.player_id,
                metadata={
                    "outcome": pass_outcome,
                    "distance": round(rng.uniform(8, 38), 2),
                    "progressive": pass_short,
                    "synthetic": True,
                },
                x=x,
                y=y,
            )
            if rng.random() < 0.12:
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=team_id,
                    event_type="pressure_event",
                    timestamp=segment_start + rng.randint(15, 50),
                    player_id=player.player_id,
                    metadata={
                        "intensity": round(rng.uniform(1.0, 3.0), 2),
                        "source": "synthetic_tactical_pressure",
                        "synthetic": True,
                    },
                    x=x + (10 if team_id == "home" else -10),
                    y=y,
                )
                if team_id == "home":
                    home_pressure += 1
                else:
                    away_pressure += 1
            if rng.random() < 0.15:
                target_team = "away" if team_id == "home" else "home"
                tackled_player = rng.choice(home_team.players if target_team == "home" else away_team.players)
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=target_team,
                    event_type="tackle",
                    timestamp=segment_start + rng.randint(25, 55),
                    player_id=tackled_player.player_id,
                    metadata={"won": rng.random() < 0.58, "synthetic": True},
                    x=50.0,
                    y=50.0,
                )
            if rng.random() < 0.085:
                foul_team = team_id if rng.random() < 0.6 else ("away" if team_id == "home" else "home")
                foul_player = rng.choice(home_team.players if foul_team == "home" else away_team.players)
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=foul_team,
                    event_type="foul",
                    timestamp=segment_start + rng.randint(15, 60),
                    player_id=foul_player.player_id,
                    metadata={"severity": "soft", "synthetic": True},
                    x=50.0,
                    y=50.0,
                )
            if rng.random() < 0.08:
                card_team = foul_team if 'foul_team' in locals() else team_id
                card_player = rng.choice(home_team.players if card_team == "home" else away_team.players)
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=card_team,
                    event_type="card",
                    timestamp=segment_start + rng.randint(20, 70),
                    player_id=card_player.player_id,
                    metadata={"card_type": "yellow", "synthetic": True},
                    x=48.0,
                    y=52.0,
                )
            if rng.random() < 0.26 and (team_id == "home" and x < 75 or team_id == "away" and x > 25):
                attack_x = 88.0 if team_id == "home" else 12.0
                attack_y = rng.uniform(12, 88)
                shot_outcome = "goal" if rng.random() < 0.18 else ("saved" if rng.random() < 0.42 else "off_target")
                shot_player = rng.choice(home_team.players if team_id == "home" else away_team.players)
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=team_id,
                    event_type="shot",
                    timestamp=segment_start + rng.randint(30, 75),
                    player_id=shot_player.player_id,
                    metadata={
                        "outcome": shot_outcome,
                        "on_target": shot_outcome in {"goal", "saved"},
                        "synthetic": True,
                    },
                    x=attack_x,
                    y=attack_y,
                )
                if shot_outcome == "goal":
                    if team_id == "home":
                        home_score += 1
                    else:
                        away_score += 1
                    _append_event(
                        events,
                        match_id=match_identifier,
                        team_id=team_id,
                        event_type="goal",
                        timestamp=segment_start + rng.randint(35, 80),
                        player_id=shot_player.player_id,
                        metadata={
                            "assistant": rng.choice(["set-piece", "open-play", "counter-attack"]),
                            "score": f"{home_score}-{away_score}",
                            "synthetic": True,
                        },
                        x=attack_x,
                        y=attack_y,
                    )
            if rng.random() < 0.04:
                target_team = "away" if team_id == "home" else "home"
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=team_id,
                    event_type="possession_change",
                    timestamp=segment_start + rng.randint(20, 70),
                    metadata={
                        "previous_team": target_team,
                        "new_team": team_id,
                        "reason": "synthetic_pressing_shift",
                        "synthetic": True,
                    },
                    x=50.0,
                    y=50.0,
                )
                current_possession = team_id

        if minute in {18, 42, 68}:
            tactical_team = "home" if minute % 2 == 0 else "away"
            tactical_player = rng.choice(home_team.players if tactical_team == "home" else away_team.players)
            _append_event(
                events,
                match_id=match_identifier,
                team_id=tactical_team,
                event_type="pressure_event",
                timestamp=(minute * 60) + 50,
                player_id=tactical_player.player_id,
                metadata={
                    "intensity": 4.2,
                    "source": "synthetic_tactical_shift",
                    "synthetic": True,
                },
                x=50.0,
                y=50.0,
            )
            if tactical_team == "home":
                home_pressure += 1
            else:
                away_pressure += 1

        if minute in {52, 68, 78}:
            team_id = "home" if (minute // 2) % 2 == 0 else "away"
            if home_subs + away_subs < 8:
                players = home_team.players if team_id == "home" else away_team.players
                player_out = rng.choice(players)
                alternatives = [player for player in players if player.player_id != player_out.player_id]
                bench_player = rng.choice(alternatives) if alternatives else player_out
                if team_id == "home":
                    home_subs += 1
                else:
                    away_subs += 1
                _append_event(
                    events,
                    match_id=match_identifier,
                    team_id=team_id,
                    event_type="substitution",
                    timestamp=(minute * 60) + 54,
                    player_id=player_out.player_id,
                    metadata={
                        "player_out": player_out.player_id,
                        "player_in": bench_player.player_id,
                        "synthetic": True,
                    },
                    x=55.0,
                    y=48.0,
                )

    final_whistle = 90 * 60
    _append_event(
        events,
        match_id=match_identifier,
        team_id="home",
        event_type="whistle",
        timestamp=final_whistle,
        metadata={"reason": "full_time", "score": f"{home_score}-{away_score}", "synthetic": True},
        x=50.0,
        y=50.0,
    )

    events.sort(key=lambda item: (item["timestamp"], item["index"]))
    return SyntheticMatch(
        match_id=match_identifier,
        seed=seed,
        synthetic=True,
        created_at=now,
        home_team=home_team,
        away_team=away_team,
        events=events,
    )


DEFAULT_MATCH_SEEDS = [101, 202, 303]
MATCH_LIBRARY: Dict[str, SyntheticMatch] = {f"synthetic-{seed}": generate_match(seed) for seed in DEFAULT_MATCH_SEEDS}


def list_available_matches() -> List[Dict[str, Any]]:
    return [match.as_metadata() for match in MATCH_LIBRARY.values()]


def get_match(match_id: str) -> SyntheticMatch:
    if match_id not in MATCH_LIBRARY:
        seed = len(MATCH_LIBRARY) + 1
        match = generate_match(seed, match_id=match_id)
        MATCH_LIBRARY[match_id] = match
    return MATCH_LIBRARY[match_id]


def calculate_match_state(events: Sequence[Dict[str, Any]], through_event: Optional[int] = None) -> Dict[str, Any]:
    event_slice = list(events)
    if through_event is not None:
        event_slice = event_slice[: max(0, min(through_event, len(event_slice)))]

    if not event_slice:
        return {
            "score": {"home": 0, "away": 0},
            "match_clock": "00:00",
            "possession": {"home": 50, "away": 50},
            "pass_attempts": {"home": 0, "away": 0},
            "pass_completions": {"home": 0, "away": 0},
            "pass_completion": {"home": 0.0, "away": 0.0},
            "shots": {"home": 0, "away": 0},
            "shots_on_target": {"home": 0, "away": 0},
            "fouls": {"home": 0, "away": 0},
            "yellow_cards": {"home": 0, "away": 0},
            "red_cards": {"home": 0, "away": 0},
            "substitutions": {"home": 0, "away": 0},
            "pressure_events": {"home": 0, "away": 0},
            "recent_attacking_activity": {"home": 0, "away": 0},
            "through_event": 0,
            "synthetic": True,
        }

    score = {"home": 0, "away": 0}
    pass_attempts = {"home": 0, "away": 0}
    pass_completions = {"home": 0, "away": 0}
    shots = {"home": 0, "away": 0}
    shots_on_target = {"home": 0, "away": 0}
    fouls = {"home": 0, "away": 0}
    yellow_cards = {"home": 0, "away": 0}
    red_cards = {"home": 0, "away": 0}
    substitutions = {"home": 0, "away": 0}
    pressure_events = {"home": 0, "away": 0}
    recent_attacking_activity = {"home": 0, "away": 0}
    possession = {"home": 0, "away": 0}
    team_event_counts = {"home": 0, "away": 0}

    for event in event_slice:
        team_id = str(event.get("team_id", "home"))
        if team_id not in {"home", "away"}:
            continue
        team_event_counts[team_id] += 1
        if event.get("event_type") == "goal":
            score[team_id] += 1
            recent_attacking_activity[team_id] += 3
        elif event.get("event_type") == "pass":
            pass_attempts[team_id] += 1
            if event.get("metadata", {}).get("outcome") == "complete":
                pass_completions[team_id] += 1
            recent_attacking_activity[team_id] += 1
        elif event.get("event_type") == "shot":
            shots[team_id] += 1
            if event.get("metadata", {}).get("on_target"):
                shots_on_target[team_id] += 1
            recent_attacking_activity[team_id] += 2
        elif event.get("event_type") == "foul":
            fouls[team_id] += 1
        elif event.get("event_type") == "card":
            card_type = str(event.get("metadata", {}).get("card_type", "yellow")).lower()
            if card_type == "yellow":
                yellow_cards[team_id] += 1
            elif card_type == "red":
                red_cards[team_id] += 1
        elif event.get("event_type") == "substitution":
            substitutions[team_id] += 1
        elif event.get("event_type") == "pressure_event":
            pressure_events[team_id] += 1
            recent_attacking_activity[team_id] += 2
        elif event.get("event_type") == "possession_change":
            destination = str(event.get("metadata", {}).get("new_team", team_id))
            possession[destination] += 1

    total_pass_attempts = sum(pass_attempts.values())
    for side in ("home", "away"):
        current_completion = 0.0
        if pass_attempts[side] > 0:
            current_completion = round(pass_completions[side] / pass_attempts[side], 4)
        pass_attempts[side] = pass_attempts[side]
        pass_completions[side] = pass_completions[side]
        pass_completions[side] = pass_completions[side]
        if total_pass_attempts == 0:
            pass_attempts[side] = 0
            pass_completions[side] = 0
            pass_completion = 0.0
        else:
            pass_completion = current_completion

    clock_seconds = 0
    if event_slice:
        clock_seconds = max(event.get("timestamp", 0) for event in event_slice)

    possession_total = possession["home"] + possession["away"]
    possession_pct = {"home": 50, "away": 50}
    if possession_total > 0:
        possession_pct = {
            "home": round((possession["home"] / possession_total) * 100, 2),
            "away": round((possession["away"] / possession_total) * 100, 2),
        }

    output = {
        "score": score,
        "match_clock": _clock_text(clock_seconds),
        "match_clock_seconds": clock_seconds,
        "possession": possession_pct,
        "pass_attempts": pass_attempts,
        "pass_completions": pass_completions,
        "pass_completion": {
            "home": round(pass_completions["home"] / pass_attempts["home"], 4) if pass_attempts["home"] else 0.0,
            "away": round(pass_completions["away"] / pass_attempts["away"], 4) if pass_attempts["away"] else 0.0,
        },
        "shots": shots,
        "shots_on_target": shots_on_target,
        "fouls": fouls,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "substitutions": substitutions,
        "pressure_events": pressure_events,
        "recent_attacking_activity": recent_attacking_activity,
        "through_event": len(event_slice),
        "synthetic": True,
    }
    return output


def ensure_match_seed_valid(seed: int) -> int:
    if seed < 0:
        raise ValueError("Seed must be non-negative")
    return int(seed)
