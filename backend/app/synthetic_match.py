from __future__ import annotations

import math
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

PLAYER_NAME_BANK = [player["name"] for team in TEAM_CONFIG for player in team["players"]]


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
    return Team(
        team_id=team_id_suffix,
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
    match_pairings = [
        (0, 1, "balanced"),
        (2, 3, "pressing"),
        (4, 5, "counter"),
    ]
    home_index, away_index, style = match_pairings[seed % len(match_pairings)]
    home_config = TEAM_CONFIG[home_index]
    away_config = TEAM_CONFIG[away_index]
    home_team = _make_team(home_config, rng, "home")
    away_team = _make_team(away_config, rng, "away")
    match_identifier = match_id or f"synthetic-{seed}"
    now = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    events: List[Dict[str, Any]] = []
    home_score = 0
    away_score = 0
    current_possession = "home" if seed % 2 == 0 else "away"
    event_index = 0

    def add_event(team_id: str, event_type: str, timestamp: int, *, player: Optional[Player] = None, x: Optional[float] = None, y: Optional[float] = None, **metadata: Any) -> None:
        nonlocal event_index
        team = home_team if team_id == "home" else away_team
        event_meta: Dict[str, Any] = {
            "team_id": team_id,
            "team_name": team.name,
            "team_short_name": team.short_name,
            "synthetic": True,
        }
        if player is not None:
            event_meta["player_id"] = player.player_id
            event_meta["player_name"] = player.name
        event_meta.update(metadata)
        _append_event(
            events,
            match_id=match_identifier,
            team_id=team_id,
            event_type=event_type,
            timestamp=timestamp,
            player_id=getattr(player, "player_id", None),
            metadata=event_meta,
            x=x,
            y=y,
            index=event_index,
        )
        event_index += 1

    add_event("home", "kickoff", 0, x=50.0, y=50.0, starting_team="home", description=f"{home_team.name} kick off the synthetic match.")
    style_config = {
        "balanced": {"pass_rate": 0.78, "pressure_rate": 0.18, "shot_rate": 0.14, "foul_rate": 0.08},
        "pressing": {"pass_rate": 0.74, "pressure_rate": 0.23, "shot_rate": 0.17, "foul_rate": 0.09},
        "counter": {"pass_rate": 0.7, "pressure_rate": 0.12, "shot_rate": 0.2, "foul_rate": 0.1},
        "possession": {"pass_rate": 0.82, "pressure_rate": 0.15, "shot_rate": 0.12, "foul_rate": 0.07},
    }.get(style, {"pass_rate": 0.78, "pressure_rate": 0.18, "shot_rate": 0.14, "foul_rate": 0.08})

    for minute in range(0, 90, 2):
        segment_start = minute * 60
        for _ in range(rng.randint(2, 4)):
            team_id = current_possession
            attacking_team = home_team if team_id == "home" else away_team
            defending_team = away_team if team_id == "home" else home_team
            player = rng.choice(attacking_team.players)
            recipient = rng.choice(attacking_team.players)
            while recipient.player_id == player.player_id:
                recipient = rng.choice(attacking_team.players)

            start_x = 24.0 if team_id == "home" else 76.0
            start_y = rng.uniform(12, 88)
            end_x = 68.0 if team_id == "home" else 32.0
            end_y = rng.uniform(18, 82)
            outcome = "complete" if rng.random() < style_config["pass_rate"] else "incomplete"
            distance = round(math.hypot(end_x - start_x, end_y - start_y), 2)
            possession_seconds = round(rng.uniform(7.0, 18.0), 1)
            event_time = segment_start + rng.randint(10, 55)
            add_event(
                team_id,
                "pass",
                event_time,
                player=player,
                x=start_x,
                y=start_y,
                recipient_id=recipient.player_id,
                recipient_name=recipient.name,
                outcome=outcome,
                distance=distance,
                progressive=rng.random() < 0.55,
                possession_seconds=possession_seconds,
                start={"x": round(start_x, 2), "y": round(start_y, 2)},
                end={"x": round(end_x, 2), "y": round(end_y, 2)},
                description=f"{player.name} {'completes' if outcome == 'complete' else 'attempts'} a pass to {recipient.name}.",
            )

            if rng.random() < style_config["pressure_rate"]:
                pressure_x = start_x + (12 if team_id == "home" else -12)
                pressure_y = rng.uniform(20, 80)
                pressure_player = rng.choice(attacking_team.players)
                add_event(
                    team_id,
                    "pressure_event",
                    event_time + 3,
                    player=pressure_player,
                    x=pressure_x,
                    y=pressure_y,
                    intensity=round(rng.uniform(1.5, 3.5), 2),
                    location={"x": round(pressure_x, 2), "y": round(pressure_y, 2)},
                    source="pressing_sequence",
                    possession_seconds=round(rng.uniform(2.0, 5.0), 1),
                    description=f"{pressure_player.name} applies pressure near the opposition penalty area.",
                )

            if rng.random() < 0.12:
                tackle_player = rng.choice(defending_team.players)
                add_event(
                    team_id,
                    "tackle",
                    event_time + 5,
                    player=tackle_player,
                    x=50.0,
                    y=50.0,
                    won=rng.random() < 0.55,
                    involved_player_id=player.player_id,
                    involved_player_name=player.name,
                    description=f"{tackle_player.name} challenges {player.name}.",
                )

            if rng.random() < style_config["foul_rate"]:
                foul_player = rng.choice(attacking_team.players)
                opponent = rng.choice(defending_team.players)
                severity = rng.choice(["soft", "standard"])
                add_event(
                    team_id,
                    "foul",
                    event_time + 6,
                    player=foul_player,
                    x=50.0,
                    y=50.0,
                    opponent_id=opponent.player_id,
                    opponent_name=opponent.name,
                    severity=severity,
                    participants=[foul_player.player_id, opponent.player_id],
                    description=f"{foul_player.name} commits a {severity} foul on {opponent.name}.",
                )

            if rng.random() < style_config["shot_rate"]:
                shot_player = rng.choice(attacking_team.players)
                shot_x = 88.0 if team_id == "home" else 12.0
                shot_y = rng.uniform(18, 82)
                shot_outcome = "goal" if rng.random() < 0.18 else ("saved" if rng.random() < 0.45 else "off_target")
                shot_time = event_time + 12
                add_event(
                    team_id,
                    "shot",
                    shot_time,
                    player=shot_player,
                    x=shot_x,
                    y=shot_y,
                    outcome=shot_outcome,
                    on_target=shot_outcome in {"goal", "saved"},
                    location={"x": round(shot_x, 2), "y": round(shot_y, 2)},
                    description=f"{shot_player.name} shoots from {'inside the box' if (shot_x > 75 or shot_x < 25) else 'the edge of the box'}, {'forcing a save' if shot_outcome == 'saved' else ('finding the net' if shot_outcome == 'goal' else 'missing the target')}.",
                )
                if shot_outcome == "goal":
                    if team_id == "home":
                        home_score += 1
                    else:
                        away_score += 1
                    add_event(
                        team_id,
                        "goal",
                        shot_time + 1,
                        player=shot_player,
                        x=shot_x,
                        y=shot_y,
                        score=f"{home_score}-{away_score}",
                        assist_player_id=player.player_id,
                        assist_player_name=player.name,
                        description=f"{shot_player.name} scores for {attacking_team.name}.",
                    )

            if rng.random() < 0.06:
                current_possession = team_id
                add_event(
                    team_id,
                    "possession_change",
                    event_time + 8,
                    previous_team="away" if team_id == "home" else "home",
                    new_team=team_id,
                    reason="pressing_shift",
                    possession_seconds=round(rng.uniform(3.0, 9.0), 1),
                    description=f"{attacking_team.name} win possession after a transition.",
                )

        if minute in {18, 42, 68}:
            tactical_team = "home" if minute % 2 == 0 else "away"
            tactical_team_obj = home_team if tactical_team == "home" else away_team
            tactical_player = rng.choice(tactical_team_obj.players)
            add_event(
                tactical_team,
                "pressure_event",
                (minute * 60) + 50,
                player=tactical_player,
                x=50.0,
                y=50.0,
                intensity=round(rng.uniform(3.0, 4.5), 2),
                location={"x": 50.0, "y": 50.0},
                possession_seconds=round(rng.uniform(2.0, 4.0), 1),
                description=f"{tactical_player.name} presses aggressively in a key central channel.",
            )

        if minute in {34, 58, 76}:
            team_id = "home" if minute % 2 == 0 else "away"
            team_obj = home_team if team_id == "home" else away_team
            player_out = rng.choice(team_obj.players)
            alternative_players = [player for player in team_obj.players if player.player_id != player_out.player_id]
            player_in = rng.choice(alternative_players) if alternative_players else player_out
            add_event(
                team_id,
                "substitution",
                (minute * 60) + 54,
                player=player_out,
                player_in=player_in.player_id,
                player_in_name=player_in.name,
                player_out=player_out.player_id,
                player_out_name=player_out.name,
                description=f"{player_in.name} comes on for {player_out.name}.",
            )

    add_event("home", "whistle", 90 * 60, score=f"{home_score}-{away_score}", reason="full_time", description="The referee brings the synthetic match to a close.")
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
            "match_clock_seconds": 0,
            "possession": {"home": 50.0, "away": 50.0},
            "possession_method": "event-proxy",
            "pass_attempts": {"home": 0, "away": 0},
            "pass_completions": {"home": 0, "away": 0},
            "pass_completion": {"home": None, "away": None},
            "shots": {"home": 0, "away": 0},
            "shots_on_target": {"home": 0, "away": 0},
            "fouls": {"home": 0, "away": 0},
            "yellow_cards": {"home": 0, "away": 0},
            "red_cards": {"home": 0, "away": 0},
            "substitutions": {"home": 0, "away": 0},
            "pressure_events": {"home": 0, "away": 0},
            "attacking_third_entries": {"home": 0, "away": 0},
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
    attacking_third_entries = {"home": 0, "away": 0}
    possession_seconds = {"home": 0.0, "away": 0.0}
    possession_proxy = {"home": 0, "away": 0}
    clock_seconds = 0

    for event in event_slice:
        team_id = str(event.get("team_id", "home"))
        if team_id not in {"home", "away"}:
            continue
        if event.get("timestamp") is not None:
            clock_seconds = max(clock_seconds, int(event["timestamp"]))

        if event.get("event_type") == "goal":
            score[team_id] += 1
            recent_attacking_activity[team_id] += 3
        elif event.get("event_type") == "pass":
            pass_attempts[team_id] += 1
            metadata = event.get("metadata", {}) or {}
            if metadata.get("outcome") == "complete":
                pass_completions[team_id] += 1
            recent_attacking_activity[team_id] += 1
            possession_seconds[team_id] += float(metadata.get("possession_seconds", 0.0) or 0.0)
            possession_proxy[team_id] += 1
            if metadata.get("end") and metadata.get("start"):
                end_x = float((metadata.get("end") or {}).get("x", 0.0) or 0.0)
                if (team_id == "home" and end_x > 60) or (team_id == "away" and end_x < 40):
                    attacking_third_entries[team_id] += 1
        elif event.get("event_type") == "shot":
            shots[team_id] += 1
            metadata = event.get("metadata", {}) or {}
            if metadata.get("on_target"):
                shots_on_target[team_id] += 1
            recent_attacking_activity[team_id] += 2
            possession_seconds[team_id] += float(metadata.get("possession_seconds", 0.0) or 0.0)
        elif event.get("event_type") == "foul":
            fouls[team_id] += 1
        elif event.get("event_type") == "card":
            card_type = str((event.get("metadata", {}) or {}).get("card_type", "yellow")).lower()
            if card_type == "yellow":
                yellow_cards[team_id] += 1
            elif card_type == "red":
                red_cards[team_id] += 1
        elif event.get("event_type") == "substitution":
            substitutions[team_id] += 1
        elif event.get("event_type") == "pressure_event":
            pressure_events[team_id] += 1
            recent_attacking_activity[team_id] += 2
            metadata = event.get("metadata", {}) or {}
            possession_seconds[team_id] += float(metadata.get("possession_seconds", 0.0) or 0.0)
            location = metadata.get("location") or {}
            location_x = float(location.get("x", 50.0) or 50.0)
            if (team_id == "home" and location_x > 66) or (team_id == "away" and location_x < 34):
                attacking_third_entries[team_id] += 1
        elif event.get("event_type") == "possession_change":
            destination = str((event.get("metadata", {}) or {}).get("new_team", team_id))
            possession_proxy[destination] += 1

    possession = {"home": 0.0, "away": 0.0}
    possession_method = "event-proxy"
    if sum(possession_seconds.values()) > 0:
        possession = possession_seconds
        possession_method = "event-weighted"
    else:
        total_proxy = sum(possession_proxy.values())
        if total_proxy > 0:
            possession = {"home": float(possession_proxy["home"]), "away": float(possession_proxy["away"])}
            possession_method = "event-proxy"
        else:
            possession = {"home": 50.0, "away": 50.0}

    total_possession = sum(possession.values())
    if total_possession > 0:
        possession_pct = {
            "home": round((possession["home"] / total_possession) * 100.0, 2),
            "away": round((possession["away"] / total_possession) * 100.0, 2),
        }
    else:
        possession_pct = {"home": 50.0, "away": 50.0}

    pass_completion = {
        "home": round(pass_completions["home"] / pass_attempts["home"], 4) if pass_attempts["home"] else None,
        "away": round(pass_completions["away"] / pass_attempts["away"], 4) if pass_attempts["away"] else None,
    }

    output = {
        "score": score,
        "match_clock": _clock_text(clock_seconds),
        "match_clock_seconds": clock_seconds,
        "possession": possession_pct,
        "possession_method": possession_method,
        "pass_attempts": pass_attempts,
        "pass_completions": pass_completions,
        "pass_completion": pass_completion,
        "shots": shots,
        "shots_on_target": shots_on_target,
        "fouls": fouls,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "substitutions": substitutions,
        "pressure_events": pressure_events,
        "attacking_third_entries": attacking_third_entries,
        "recent_attacking_activity": recent_attacking_activity,
        "through_event": len(event_slice),
        "synthetic": True,
    }
    return output


def ensure_match_seed_valid(seed: int) -> int:
    if seed < 0:
        raise ValueError("Seed must be non-negative")
    return int(seed)
