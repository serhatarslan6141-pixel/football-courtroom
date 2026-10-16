from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

PITCH_MIN = 0
PITCH_MAX = 100
EVENT_TYPES = {
    "ball_control",
    "carry",
    "dribble",
    "interception",
    "recovery",
    "clearance",
    "restart",
    "restart_taken",
    "boundary",
    "offside",
    "deflection",
    "stoppage",
    "miscontrol",
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
        "team_id": "northbridge-city",
        "name": "Northbridge City",
        "short_name": "NBC",
        "formation": "4-3-3",
        "primary_color": "#7c3aed",
        "secondary_color": "#fbbf24",
        "players": [
            {"name": "Daniel Foster", "position": "GK", "squad_number": 1},
            {"name": "Marcus Reed", "position": "RB", "squad_number": 2},
            {"name": "James Carter", "position": "CB", "squad_number": 5},
            {"name": "Ethan Vale", "position": "CB", "squad_number": 6},
            {"name": "Theo Hart", "position": "LB", "squad_number": 3},
            {"name": "Isaac Quinn", "position": "CM", "squad_number": 8},
            {"name": "Owen Price", "position": "CM", "squad_number": 10},
            {"name": "Samuel Brier", "position": "AM", "squad_number": 7},
            {"name": "Leo Sparrow", "position": "RW", "squad_number": 11},
            {"name": "Gabriel Moss", "position": "ST", "squad_number": 9},
            {"name": "Noah Vale", "position": "LW", "squad_number": 14},
        ],
    },
    {
        "team_id": "harbor-athletic",
        "name": "Harbor Athletic",
        "short_name": "HBA",
        "formation": "4-2-3-1",
        "primary_color": "#34d399",
        "secondary_color": "#fbbf24",
        "players": [
            {"name": "Liam Rook", "position": "GK", "squad_number": 1},
            {"name": "Rowan Dune", "position": "RB", "squad_number": 2},
            {"name": "Adrian Pike", "position": "CB", "squad_number": 4},
            {"name": "Eamon Flint", "position": "CB", "squad_number": 5},
            {"name": "Noah Cale", "position": "LB", "squad_number": 3},
            {"name": "Cole Mercer", "position": "DM", "squad_number": 6},
            {"name": "Leo Arden", "position": "DM", "squad_number": 8},
            {"name": "Hugo Benton", "position": "AM", "squad_number": 10},
            {"name": "Felix Sloane", "position": "RW", "squad_number": 7},
            {"name": "Jonah Vale", "position": "ST", "squad_number": 9},
            {"name": "Aiden Voss", "position": "LW", "squad_number": 11},
        ],
    },
    {
        "team_id": "mossfield-united",
        "name": "Mossfield United",
        "short_name": "MSF",
        "formation": "4-3-3",
        "primary_color": "#f97316",
        "secondary_color": "#dbeafe",
        "players": [
            {"name": "Julian North", "position": "GK", "squad_number": 1},
            {"name": "Tomas Mercer", "position": "RB", "squad_number": 2},
            {"name": "Seth Hargreaves", "position": "CB", "squad_number": 4},
            {"name": "Aaron Lock", "position": "CB", "squad_number": 5},
            {"name": "Kellan Wren", "position": "LB", "squad_number": 3},
            {"name": "Nico Birch", "position": "CM", "squad_number": 6},
            {"name": "Hayden Cole", "position": "CM", "squad_number": 8},
            {"name": "Theo Ashford", "position": "AM", "squad_number": 10},
            {"name": "Joel Finch", "position": "RW", "squad_number": 7},
            {"name": "Mackenzie Hale", "position": "ST", "squad_number": 9},
            {"name": "Lucas Flynn", "position": "LW", "squad_number": 11},
        ],
    },
    {
        "team_id": "riverside-athletic",
        "name": "Riverside Athletic",
        "short_name": "RIV",
        "formation": "4-2-3-1",
        "primary_color": "#2563eb",
        "secondary_color": "#fef3c7",
        "players": [
            {"name": "Ben Ash", "position": "GK", "squad_number": 1},
            {"name": "Oliver Fen", "position": "RB", "squad_number": 2},
            {"name": "Kade Wren", "position": "CB", "squad_number": 4},
            {"name": "Adrian Holt", "position": "CB", "squad_number": 5},
            {"name": "Luca Pruitt", "position": "LB", "squad_number": 3},
            {"name": "Miles Cress", "position": "DM", "squad_number": 6},
            {"name": "Elliot Rowan", "position": "DM", "squad_number": 8},
            {"name": "Sam Grant", "position": "AM", "squad_number": 10},
            {"name": "Theo Merrick", "position": "RW", "squad_number": 7},
            {"name": "Aiden Voss", "position": "ST", "squad_number": 9},
            {"name": "Rory Fenwick", "position": "LW", "squad_number": 11},
        ],
    },
    {
        "team_id": "ashcombe-rovers",
        "name": "Ashcombe Rovers",
        "short_name": "ASH",
        "formation": "4-4-2",
        "primary_color": "#ef4444",
        "secondary_color": "#f5f5f5",
        "players": [
            {"name": "Lucas Baird", "position": "GK", "squad_number": 1},
            {"name": "Daniel Quinn", "position": "RB", "squad_number": 2},
            {"name": "Ethan Brooks", "position": "CB", "squad_number": 4},
            {"name": "Tom Avery", "position": "CB", "squad_number": 5},
            {"name": "Nathan Sloane", "position": "LB", "squad_number": 3},
            {"name": "Max Rowe", "position": "RM", "squad_number": 7},
            {"name": "Ben Mercer", "position": "CM", "squad_number": 6},
            {"name": "Ryan Fenn", "position": "CM", "squad_number": 8},
            {"name": "Peter Kestrel", "position": "LM", "squad_number": 11},
            {"name": "Luca Maren", "position": "ST", "squad_number": 9},
            {"name": "Owen Greaves", "position": "ST", "squad_number": 10},
        ],
    },
    {
        "team_id": "briarhampton-fc",
        "name": "Briarhampton FC",
        "short_name": "BRI",
        "formation": "3-4-3",
        "primary_color": "#22c55e",
        "secondary_color": "#0f172a",
        "players": [
            {"name": "Charlie Hale", "position": "GK", "squad_number": 1},
            {"name": "Dylan Squire", "position": "CB", "squad_number": 4},
            {"name": "Harvey Kestrel", "position": "CB", "squad_number": 5},
            {"name": "Adrian Vale", "position": "CB", "squad_number": 6},
            {"name": "Marcus Brine", "position": "RWB", "squad_number": 2},
            {"name": "Elias Dune", "position": "CM", "squad_number": 8},
            {"name": "Jacob Pike", "position": "CM", "squad_number": 10},
            {"name": "Ryan Flint", "position": "LWB", "squad_number": 3},
            {"name": "Tom Colson", "position": "RW", "squad_number": 7},
            {"name": "Ethan Blake", "position": "ST", "squad_number": 9},
            {"name": "Lee Rowe", "position": "LW", "squad_number": 11},
        ],
    },
]

PLAYER_NAME_BANK = [
    player["name"] for team in TEAM_CONFIG for player in team["players"]
]


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    position: str
    squad_number: int
    is_starter: bool = True


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


def _make_team(
    team_config: Dict[str, Any], rng: random.Random, team_id_suffix: str
) -> Team:
    formation = team_config["formation"]
    player_rows = team_config["players"]
    if len(player_rows) != 11:
        raise ValueError(f"Roster for {team_config['name']} must contain 11 players")

    players = [
        Player(
            player_id=f"{team_id_suffix}-{row['squad_number']:02d}",
            name=row["name"],
            position=row["position"],
            squad_number=row["squad_number"],
        )
        for row in player_rows
    ]
    # A real bench, separate from the starting XI. Substitutes inherit the vacated slot.
    reserve_roles = ["GK", "CB", "RB", "CM", "AM", "LW", "ST"]
    first_names = [
        "Ellis",
        "Jude",
        "Finley",
        "Oscar",
        "Callum",
        "Reuben",
        "Riley",
        "Alex",
    ]
    surnames = [
        "Hawke",
        "Marlow",
        "Shaw",
        "West",
        "Bramble",
        "Ellery",
        "Keene",
        "Hurst",
    ]
    reserve_names = rng.sample(
        [f"{first} {last}" for first in first_names for last in surnames],
        len(reserve_roles),
    )
    for index, role in enumerate(reserve_roles):
        number = 20 + index
        players.append(
            Player(
                player_id=f"{team_id_suffix}-{number:02d}",
                name=reserve_names[index],
                position=role,
                squad_number=number,
                is_starter=False,
            )
        )
    return Team(
        team_id=team_id_suffix,
        name=team_config["name"],
        short_name=team_config["short_name"],
        formation=formation,
        primary_color=team_config["primary_color"],
        secondary_color=team_config["secondary_color"],
        players=players,
    )


def _normalize_team_key(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"home", "away"}:
            return normalized
        if normalized in {"0", "1"}:
            return "home" if normalized == "0" else "away"
        return None
    if isinstance(value, (int, float)) and value in (0, 1):
        return "home" if int(value) == 0 else "away"
    return None


def generate_match(seed: int, match_id: Optional[str] = None) -> SyntheticMatch:
    from .simulation import simulate_match

    rng = random.Random(seed)
    pairings = [(0, 1, "balanced"), (2, 3, "pressing"), (4, 5, "counter")]
    home_index, away_index, style = pairings[seed % len(pairings)]
    home = _make_team(TEAM_CONFIG[home_index], rng, "home")
    away = _make_team(TEAM_CONFIG[away_index], rng, "away")
    identifier = match_id or f"synthetic-{seed}"
    return SyntheticMatch(
        match_id=identifier,
        seed=seed,
        synthetic=True,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        home_team=home,
        away_team=away,
        events=simulate_match(identifier, home, away, rng, style),
    )


DEFAULT_MATCH_SEEDS = [101, 202, 303]
MATCH_LIBRARY: Dict[str, SyntheticMatch] = {
    f"synthetic-{seed}": generate_match(seed) for seed in DEFAULT_MATCH_SEEDS
}


def list_available_matches() -> List[Dict[str, Any]]:
    return [match.as_metadata() for match in MATCH_LIBRARY.values()]


def get_match(match_id: str) -> SyntheticMatch:
    if match_id not in MATCH_LIBRARY:
        seed = len(MATCH_LIBRARY) + 1
        match = generate_match(seed, match_id=match_id)
        MATCH_LIBRARY[match_id] = match
    return MATCH_LIBRARY[match_id]


def select_replay_events(
    events: Sequence[Dict[str, Any]],
    through_event: Optional[int] = None,
    through_timestamp: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Use a chronological event count, then an inclusive timestamp boundary.

    Event.index records generation order and is not a replay position.
    """
    ordered_events = sorted(
        list(events),
        key=lambda item: (
            int(item.get("timestamp", 0) or 0),
            int(item.get("index", 0) or 0),
        ),
    )

    if through_event is not None:
        ordered_events = ordered_events[
            : max(0, min(int(through_event), len(ordered_events)))
        ]

    if through_timestamp is not None:
        cutoff = int(through_timestamp)
        ordered_events = [
            event
            for event in ordered_events
            if int(event.get("timestamp", 0) or 0) <= cutoff
        ]

    return ordered_events


CASE_OBSERVATION_SECONDS = {
    "substitution": 210,
    "goal": 180,
    "possession_change": 180,
    "shot": 90,
}


def next_replay_update(events, cutoff):
    """A snapshot is valid up to the next completion or possible evidence boundary.

    This signals a cache interval, not the existence of a future case.
    """
    boundaries = [event["timestamp"] for event in events if event["timestamp"] > cutoff]
    boundaries.extend(
        event["timestamp"] + CASE_OBSERVATION_SECONDS[event["event_type"]]
        for event in events
        if event["timestamp"] <= cutoff
        and event["event_type"] in CASE_OBSERVATION_SECONDS
        and event["timestamp"] + CASE_OBSERVATION_SECONDS[event["event_type"]] > cutoff
    )
    return min(boundaries) if boundaries else None


def calculate_match_state(
    events: Sequence[Dict[str, Any]],
    through_event: Optional[int] = None,
    through_timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    event_slice = select_replay_events(events, through_event, through_timestamp)
    counters = (
        "score",
        "pass_attempts",
        "pass_completions",
        "shots",
        "shots_on_target",
        "fouls",
        "yellow_cards",
        "red_cards",
        "substitutions",
        "pressure_events",
        "attacking_third_entries",
        "recent_attacking_activity",
        "tackles",
        "tackles_won",
        "interceptions",
        "recoveries",
        "clearances",
        "carries",
        "crosses",
    )
    state = {key: {"home": 0, "away": 0} for key in counters}
    possession_seconds = {"home": 0.0, "away": 0.0}
    proxy = {"home": 0, "away": 0}
    clock = max((event["timestamp"] for event in event_slice), default=0)
    cutoff = through_timestamp if through_timestamp is not None else clock
    for event in event_slice:
        metadata = event.get("metadata") or {}
        team = _normalize_team_key(event.get("team_id")) or _normalize_team_key(
            metadata.get("team_id")
        )
        if team is None:
            continue
        kind = event.get("event_type")
        owner = _normalize_team_key(event.get("possession_team_id"))
        if event.get("schema_version") != 2:
            owner = team
        if owner:
            possession_seconds[owner] += float(metadata.get("possession_seconds") or 0)
        if kind in {"pass", "cross"}:
            state["pass_attempts"][team] += 1
            state["pass_completions"][team] += int(
                metadata.get("outcome") == "complete"
            )
            proxy[team] += 1
        if kind == "goal":
            state["score"][team] += 1
        if kind == "shot":
            state["shots"][team] += 1
            state["shots_on_target"][team] += int(bool(metadata.get("on_target")))
        key = {
            "foul": "fouls",
            "substitution": "substitutions",
            "pressure_event": "pressure_events",
            "interception": "interceptions",
            "recovery": "recoveries",
            "clearance": "clearances",
            "carry": "carries",
            "dribble": "carries",
            "cross": "crosses",
            "tackle": "tackles",
        }.get(kind)
        if key:
            state[key][team] += 1
        if kind == "tackle":
            state["tackles_won"][team] += int(bool(metadata.get("won")))
        if kind == "card":
            key = "red_cards" if metadata.get("card_type") == "red" else "yellow_cards"
            state[key][team] += 1
        direction = metadata.get("attack_direction", 1 if team == "home" else -1)
        start, end = metadata.get("start"), metadata.get("end")
        if start and end and kind in {"pass", "cross", "carry", "dribble"}:
            before = start["x"] if direction == 1 else 100 - start["x"]
            after = end["x"] if direction == 1 else 100 - end["x"]
            successful = (
                kind not in {"pass", "cross"} or metadata.get("outcome") == "complete"
            )
            if before < 66.67 <= after and successful:
                state["attacking_third_entries"][team] += 1
        if event["timestamp"] >= cutoff - 300:
            state["recent_attacking_activity"][team] += (
                3
                if kind == "goal"
                else (
                    2
                    if kind == "shot"
                    else (
                        1
                        if kind in {"pass", "cross", "carry", "dribble"}
                        and metadata.get("progressive")
                        else 0
                    )
                )
            )
        if kind == "possession_change":
            destination = _normalize_team_key(metadata.get("new_team"))
            if destination:
                proxy[destination] += 1
    total = sum(possession_seconds.values())
    method = (
        "recorded-in-play-duration"
        if any(e.get("schema_version") == 2 for e in event_slice)
        else "event-weighted"
    )
    if not total:
        method = "event-proxy"
        possession_seconds = proxy
        total = sum(proxy.values())
    state.update(
        {
            "match_clock": _clock_text(clock),
            "match_clock_seconds": clock,
            "possession": {
                side: (
                    round(possession_seconds[side] / total * 100, 2) if total else 50.0
                )
                for side in ("home", "away")
            },
            "possession_seconds": possession_seconds,
            "possession_method": method,
            "pass_completion": {
                side: (
                    round(
                        state["pass_completions"][side] / state["pass_attempts"][side],
                        4,
                    )
                    if state["pass_attempts"][side]
                    else None
                )
                for side in ("home", "away")
            },
            "through_event": len(event_slice),
            "through_timestamp": through_timestamp,
            "next_update_timestamp": next_replay_update(events, cutoff),
            "synthetic": True,
        }
    )
    return state


def ensure_match_seed_valid(seed: int) -> int:
    if seed < 0:
        raise ValueError("Seed must be non-negative")
    return int(seed)
