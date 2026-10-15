from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .synthetic_match import _normalize_team_key

CASE_TYPES = (
    "substitution_impact",
    "momentum_shift",
    "missed_opportunity",
)


def _sorted_events(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        list(events),
        key=lambda event: (
            int((event.get("timestamp") or 0)),
            int((event.get("index") or 0)),
        ),
    )


def _infer_match_id(events: Sequence[Dict[str, Any]], fallback: str = "synthetic-match") -> str:
    for event in events:
        match_id = event.get("match_id")
        if match_id:
            return str(match_id)

        metadata = event.get("metadata") or {}
        match_id = metadata.get("match_id")
        if match_id:
            return str(match_id)

        event_id = event.get("event_id")
        if isinstance(event_id, str):
            prefix, sep, _suffix = event_id.partition("-evt-")
            if sep and prefix:
                return prefix
    return fallback


def _team_for(event: Dict[str, Any]) -> Optional[str]:
    explicit = event.get("team_id")
    if explicit is not None:
        normalized = _normalize_team_key(explicit)
        if normalized is not None:
            return normalized
    metadata = event.get("metadata") or {}
    return _normalize_team_key(metadata.get("team_id"))


def _player_names(event: Dict[str, Any]) -> List[str]:
    metadata = event.get("metadata") or {}
    names = []
    for key in ("player_name", "recipient_name", "player_in_name", "player_out_name"):
        value = metadata.get(key)
        if value and value not in names:
            names.append(str(value))
    return names


def _window_events(events: Sequence[Dict[str, Any]], team_id: str, start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    result = []
    for event in events:
        if _team_for(event) != team_id:
            continue
        ts = int(event.get("timestamp") or 0)
        if start_ts <= ts <= end_ts:
            result.append(event)
    return result


def _window_summary(events: Sequence[Dict[str, Any]], team_id: str, start_ts: int, end_ts: int) -> Dict[str, Any]:
    window_events = _window_events(events, team_id, start_ts, end_ts)
    pass_attempts = 0
    pass_completions = 0
    shots = 0
    shots_on_target = 0
    pressure_events = 0
    goals = 0
    fouls = 0
    possession_seconds = 0.0
    attack_score = 0
    event_ids = []

    for event in window_events:
        event_type = event.get("event_type")
        metadata = event.get("metadata") or {}
        event_ids.append(event.get("event_id"))
        if event_type == "pass":
            pass_attempts += 1
            if str(metadata.get("outcome") or "").lower() == "complete":
                pass_completions += 1
            attack_score += 1
        elif event_type == "shot":
            shots += 1
            attack_score += 2
            if bool(metadata.get("on_target")):
                shots_on_target += 1
        elif event_type == "pressure_event":
            pressure_events += 1
            attack_score += 2
            possession_seconds += float(metadata.get("possession_seconds", 0.0) or 0.0)
        elif event_type == "goal":
            goals += 1
            attack_score += 3
        elif event_type == "foul":
            fouls += 1
        elif event_type == "turnover":
            attack_score -= 1

        possession_seconds += float(metadata.get("possession_seconds", 0.0) or 0.0)

    pass_completion = None if pass_attempts == 0 else round(pass_completions / pass_attempts, 4)
    return {
        "team_id": team_id,
        "event_count": len(window_events),
        "event_ids": [event_id for event_id in event_ids if event_id],
        "pass_attempts": pass_attempts,
        "pass_completions": pass_completions,
        "pass_completion": pass_completion,
        "shots": shots,
        "shots_on_target": shots_on_target,
        "pressure_events": pressure_events,
        "goals": goals,
        "fouls": fouls,
        "possession_seconds": possession_seconds,
        "attacking_activity": attack_score,
    }


def _confidence_from_delta(delta: float, sample_size: int) -> str:
    if delta >= 0.5 and sample_size >= 6:
        return "high"
    if delta >= 0.3 and sample_size >= 4:
        return "medium"
    return "low"


def _case_id(match_id: str, case_type: str, timestamp: int, team_id: str, index: int) -> str:
    return f"{match_id}-{case_type}-{team_id}-{timestamp}-{index}"


def _has_meaningful_window(pre_stats: Dict[str, Any], post_stats: Dict[str, Any], *, min_pre_events: int = 3, min_post_events: int = 3, min_total_actions: int = 6) -> bool:
    if pre_stats["event_count"] < min_pre_events or post_stats["event_count"] < min_post_events:
        return False
    action_total = (
        pre_stats["pass_attempts"]
        + pre_stats["pressure_events"]
        + pre_stats["shots"]
        + post_stats["pass_attempts"]
        + post_stats["pressure_events"]
        + post_stats["shots"]
    )
    return action_total >= min_total_actions


def _summarize_players(events: Sequence[Dict[str, Any]]) -> List[str]:
    names = []
    for event in events:
        for name in _player_names(event):
            if name not in names:
                names.append(name)
    return names


def _summarize_event_players(events: Sequence[Dict[str, Any]], event_ids: Sequence[str]) -> List[str]:
    event_lookup = {}
    for event in events:
        event_id = event.get("event_id")
        if event_id is not None:
            event_lookup[str(event_id)] = event

    names: List[str] = []
    seen: set[str] = set()
    for event_id in event_ids:
        event = event_lookup.get(str(event_id))
        if event is None:
            continue
        for name in _player_names(event):
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _build_case(
    *,
    match_id: str,
    case_type: str,
    title: str,
    team_id: str,
    timestamp: int,
    trigger_event_ids: List[str],
    evidence: List[Dict[str, Any]],
    counterevidence: List[str],
    relevant_windows: List[Dict[str, Any]],
    limitations: List[str],
    confidence: str,
    order: int,
    players: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "case_id": _case_id(match_id, case_type, timestamp, team_id, order),
        "match_id": match_id,
        "case_type": case_type,
        "title": title,
        "detection_timestamp": timestamp,
        "teams": {
            "team_id": team_id,
            "team_name": None,
        },
        "players": players or [],
        "trigger_event_ids": trigger_event_ids,
        "evidence": evidence,
        "counterevidence": counterevidence,
        "relevant_windows": relevant_windows,
        "confidence": confidence,
        "limitations": limitations,
        "synthetic": True,
    }


def _detect_substitution_impact(events: Sequence[Dict[str, Any]], *, match_id: str) -> List[Dict[str, Any]]:
    ordered = _sorted_events(events)
    cases: List[Dict[str, Any]] = []
    last_seen: Dict[str, int] = {}
    order = 0

    for event in ordered:
        if event.get("event_type") != "substitution":
            continue
        team_id = _team_for(event)
        if team_id is None:
            continue
        ts = int(event.get("timestamp") or 0)
        if last_seen.get(team_id, -999999) + 240 > ts:
            continue
        last_seen[team_id] = ts

        pre_start = max(0, ts - 180)
        post_end = ts + 210
        pre_stats = _window_summary(ordered, team_id, pre_start, ts)
        post_stats = _window_summary(ordered, team_id, ts, post_end)

        if pre_stats["event_count"] < 3 or post_stats["event_count"] < 4:
            continue
        if not _has_meaningful_window(pre_stats, post_stats, min_pre_events=3, min_post_events=4, min_total_actions=7):
            continue

        attack_delta = post_stats["attacking_activity"] - pre_stats["attacking_activity"]
        pressure_delta = post_stats["pressure_events"] - pre_stats["pressure_events"]
        pass_delta = 0.0
        if pre_stats["pass_attempts"]:
            pass_delta = (post_stats["pass_completion"] or 0.0) - (pre_stats["pass_completion"] or 0.0)

        if not (
            (attack_delta >= 2)
            or (pressure_delta >= 1)
            or (pass_delta >= 0.2)
            or (post_stats["pressure_events"] >= 2 and post_stats["shots"] >= 1)
        ):
            continue

        evidence = [
            {
                "label": "Pre-substitution base",
                "value": f"{pre_stats['attacking_activity']} attacking actions in the previous three minutes",
                "event_ids": pre_stats["event_ids"],
                "context": "The team’s baseline leading into the change.",
            },
            {
                "label": "Post-substitution effect",
                "value": f"{post_stats['attacking_activity']} attacking actions in the next three minutes",
                "event_ids": post_stats["event_ids"],
                "context": "The immediate response after the substitution was introduced.",
            },
            {
                "label": "Pressure and passing",
                "value": f"Pressure +{pressure_delta}; completion shift {pass_delta:.2f}",
                "event_ids": [*pre_stats["event_ids"][:2], *post_stats["event_ids"][:2]],
                "context": "A simple read of how the substitution altered pressure and ball retention.",
            },
        ]
        counterevidence = [
            "The improved activity may be a normal phase of the match rather than a direct result of the substitution.",
            "The sample is still small, so the case should be treated as a debatable tactical shift rather than proof of causation."
        ]
        window_data = [
            {"label": "Before substitution", "start": pre_start, "end": ts},
            {"label": "After substitution", "start": ts, "end": post_end},
        ]
        case = _build_case(
            match_id=match_id,
            case_type="substitution_impact",
            title=f"Did the substitution change the rhythm for {team_id.replace('_', ' ').title()}?",
            team_id=team_id,
            timestamp=ts,
            trigger_event_ids=[event.get("event_id")],
            evidence=evidence,
            counterevidence=counterevidence,
            relevant_windows=window_data,
            limitations=[
                "The estimate is event-based and not a direct causal model.",
                "Only data available before the replay cutoff has been used.",
            ],
            confidence=_confidence_from_delta(
                max(
                    attack_delta / max(pre_stats["attacking_activity"] + 1, 2),
                    pressure_delta / max(pre_stats["pressure_events"] + 1, 2),
                    abs(pass_delta),
                ),
                post_stats["event_count"],
            ),
            order=order,
            players=_summarize_event_players(ordered, [*pre_stats["event_ids"], *post_stats["event_ids"]]),
        )
        cases.append(case)
        order += 1
    return cases


def _detect_momentum_shift(events: Sequence[Dict[str, Any]], *, match_id: str) -> List[Dict[str, Any]]:
    ordered = _sorted_events(events)
    cases: List[Dict[str, Any]] = []
    last_seen: Dict[str, int] = {}
    order = 0

    for event in ordered:
        if event.get("event_type") not in {"goal", "possession_change"}:
            continue
        team_id = _team_for(event)
        if event.get("event_type") == "possession_change":
            metadata = event.get("metadata") or {}
            team_id = _normalize_team_key(metadata.get("new_team")) or team_id
        if team_id is None:
            continue
        ts = int(event.get("timestamp") or 0)
        if last_seen.get(team_id, -999999) + 240 > ts:
            continue
        last_seen[team_id] = ts

        pre_start = max(0, ts - 120)
        post_end = ts + 180
        pre_stats = _window_summary(ordered, team_id, pre_start, ts)
        post_stats = _window_summary(ordered, team_id, ts, post_end)

        if post_stats["event_count"] < 3 or pre_stats["event_count"] < 1:
            continue
        if not _has_meaningful_window(pre_stats, post_stats, min_pre_events=1, min_post_events=3, min_total_actions=3):
            continue

        attack_delta = post_stats["attacking_activity"] - pre_stats["attacking_activity"]
        pressure_delta = post_stats["pressure_events"] - pre_stats["pressure_events"]
        if not (
            (attack_delta >= 4 and pressure_delta >= 1)
            or (post_stats["attacking_activity"] >= 6 and post_stats["pressure_events"] >= 2)
            or (post_stats["shots"] >= 1 and post_stats["pressure_events"] >= 2)
        ):
            continue

        evidence = [
            {
                "label": "Before the turning point",
                "value": f"{pre_stats['attacking_activity']} attacking actions and {pre_stats['pressure_events']} pressing events",
                "event_ids": pre_stats["event_ids"],
                "context": "The team’s pattern leading into the turning point.",
            },
            {
                "label": "After the turning point",
                "value": f"{post_stats['attacking_activity']} attacking actions and {post_stats['pressure_events']} pressing events",
                "event_ids": post_stats["event_ids"],
                "context": "The immediate burst after the turning point.",
            },
        ]
        case = _build_case(
            match_id=match_id,
            case_type="momentum_shift",
            title=f"Did {team_id.replace('_', ' ').title()} gain a decisive momentum swing?",
            team_id=team_id,
            timestamp=ts,
            trigger_event_ids=[event.get("event_id")],
            evidence=evidence,
            counterevidence=[
                "A short surge can sometimes be a statistical blip rather than a sustained tactical shift.",
                "This should not be treated as proof that the trigger caused the match swing on its own.",
            ],
            relevant_windows=[
                {"label": "Before the turning point", "start": pre_start, "end": ts},
                {"label": "After the turning point", "start": ts, "end": post_end},
            ],
            limitations=[
                "The evidence is a short-window comparison within the available event stream.",
                "Different match states can feed similar volume spikes without a clear causal chain.",
            ],
            confidence=_confidence_from_delta(
                max(
                    attack_delta / max(pre_stats["attacking_activity"] + 1, 2),
                    pressure_delta / max(pre_stats["pressure_events"] + 1, 2),
                ),
                post_stats["event_count"],
            ),
            order=order,
            players=_summarize_event_players(ordered, [*pre_stats["event_ids"], *post_stats["event_ids"]]),
        )
        cases.append(case)
        order += 1
    return cases


def _detect_missed_opportunity(events: Sequence[Dict[str, Any]], *, match_id: str) -> List[Dict[str, Any]]:
    ordered = _sorted_events(events)
    cases: List[Dict[str, Any]] = []
    last_seen: Dict[str, int] = {}
    order = 0

    for event in ordered:
        if event.get("event_type") != "shot":
            continue
        metadata = event.get("metadata") or {}
        outcome = str(metadata.get("outcome") or "").lower()
        if outcome == "goal":
            continue
        team_id = _team_for(event)
        if team_id is None:
            continue
        ts = int(event.get("timestamp") or 0)
        if last_seen.get(team_id, -999999) + 300 > ts:
            continue
        last_seen[team_id] = ts

        pre_start = max(0, ts - 90)
        pre_end = max(0, ts - 1)
        if ts < 30:
            continue
        post_start = ts + 1
        post_end = ts + 90
        pre_stats = _window_summary(ordered, team_id, pre_start, pre_end)
        post_stats = _window_summary(ordered, team_id, post_start, post_end)
        if pre_stats["event_count"] < 3 or pre_stats["pass_attempts"] + pre_stats["pressure_events"] < 2:
            continue
        if post_stats["shots"] > 0 or post_stats["goals"] > 0:
            continue
        if not (pre_stats["pass_attempts"] >= 1 and (pre_stats["pressure_events"] >= 1 or pre_stats["shots"] >= 1)):
            continue

        evidence = [
            {
                "label": "Build-up before the shot",
                "value": f"{pre_stats['pass_attempts']} passes and {pre_stats['pressure_events']} pressure actions in the previous 90 seconds",
                "event_ids": pre_stats["event_ids"],
                "context": "The sequence building to the chance.",
            },
            {
                "label": "Shot outcome",
                "value": f"Outcome recorded as {outcome or 'off_target'}",
                "event_ids": [event.get("event_id")],
                "context": "The actual result of the attempt.",
            },
        ]
        case = _build_case(
            match_id=match_id,
            case_type="missed_opportunity",
            title=f"Was {team_id.replace('_', ' ').title()} left with a significant missed chance?",
            team_id=team_id,
            timestamp=ts,
            trigger_event_ids=[event.get("event_id")],
            evidence=evidence,
            counterevidence=[
                "The attempt may have been a low-value shot from a poor angle, so the buildup alone should not be overstated.",
                "The immediate follow-up did not show sustained pressure, which weakens the case for a broader tactical failure.",
            ],
            relevant_windows=[
                {"label": "Before shot", "start": pre_start, "end": ts},
                {"label": "After shot", "start": ts, "end": post_end},
            ],
            limitations=[
                "This does not model expected goals or shot quality directly.",
                "It is only a structured interpretation of the event stream available at the cutoff.",
            ],
            confidence=_confidence_from_delta(
                min(1.0, (pre_stats["pass_attempts"] + pre_stats["pressure_events"]) / 6.0),
                max(pre_stats["event_count"], 1),
            ),
            order=order,
            players=_summarize_event_players(ordered, [*pre_stats["event_ids"], event.get("event_id")]),
        )
        cases.append(case)
        order += 1
    return cases


def detect_cases(
    events: Sequence[Dict[str, Any]],
    through_timestamp: Optional[int] = None,
    through_event: Optional[int] = None,
    match_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ordered = _sorted_events(events)
    if through_event is not None:
        ordered = [event for event in ordered if int((event.get("index") or 0)) <= int(through_event)]
    if through_timestamp is not None:
        ordered = [event for event in ordered if int((event.get("timestamp") or 0)) <= int(through_timestamp)]

    if not ordered:
        return []

    resolved_match_id = match_id or _infer_match_id(ordered)

    cases: List[Dict[str, Any]] = []
    cases.extend(_detect_substitution_impact(ordered, match_id=resolved_match_id))
    cases.extend(_detect_momentum_shift(ordered, match_id=resolved_match_id))
    cases.extend(_detect_missed_opportunity(ordered, match_id=resolved_match_id))

    deduped: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        deduped[case["case_id"]] = case
    return sorted(deduped.values(), key=lambda item: (item["detection_timestamp"], item["case_type"]))
