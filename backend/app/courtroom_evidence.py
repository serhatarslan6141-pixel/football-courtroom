"""Build facts from closed case windows; reject ungrounded model assertions."""
from __future__ import annotations

import hashlib
import json
import re

from .case_detection import _window_summary, detect_cases
from .courtroom_models import (
    Argument, EvidenceSubmission, GroundedPoint, ObservedEvent, RecordedFact,
    Ruling, VerifiedEvidence,
)
from .synthetic_match import select_replay_events

EVIDENCE_VERSION = 'courtroom-evidence-v1'


class InvalidAgentOutput(Exception):
    """No provider-controlled exception text may be returned to callers."""
    REASONS = frozenset({
        'validation_failed', 'numeric_reasoning', 'overconfident_reasoning',
        'unsafe_reasoning', 'unknown_fact_reference', 'unknown_event_reference',
        'event_not_supported_by_fact', 'wrong_submission_type',
        'observation_value_mismatch', 'missing_trigger_reference',
        'invalid_stance', 'missing_structured_value',
    })

    def __init__(self, reason='validation_failed'):
        super().__init__('Invalid agent output')
        self.reason = reason if reason in self.REASONS else 'validation_failed'


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


def build_evidence(match, case_id: str, through_timestamp: int) -> VerifiedEvidence:
    # First discover only cases already eligible at the caller's replay cursor.
    cases = detect_cases(match.events, through_timestamp=through_timestamp, match_id=match.match_id)
    case = next((item for item in cases if item['case_id'] == case_id), None)
    if case is None:
        raise KeyError(case_id)
    cutoff = max(case['available_timestamp'], case['detection_timestamp'],
                 *(window['end'] for window in case['relevant_windows']))
    start = min(window['start'] for window in case['relevant_windows'])
    # Re-detect at the fixed case boundary. Later replay cursors cannot change
    # its statistics, supply future players, or alter the cache identity.
    case = next(item for item in detect_cases(match.events, through_timestamp=cutoff,
                match_id=match.match_id) if item['case_id'] == case_id)
    selected = [event for event in select_replay_events(match.events, through_timestamp=cutoff)
                if start <= event['timestamp'] <= cutoff]
    teams = {'home': match.home_team, 'away': match.away_team}
    players = {p.player_id: p for team in teams.values() for p in team.players}
    observed = []
    # Only completed event fields are whitelisted. In particular, never send
    # full-match metadata, detector counterclaims, final scores, or future events.
    for event in selected:
        meta = event.get('metadata') or {}
        team_id, player_id = event.get('team_id'), event.get('player_id')
        observed.append(ObservedEvent(
            event_id=event['event_id'], timestamp=event['timestamp'],
            clock=f"{event['timestamp'] // 60:02d}:{event['timestamp'] % 60:02d}",
            event_type=event['event_type'], team_id=team_id,
            team_name=teams[team_id].name if team_id in teams else None,
            player_id=player_id,
            player_name=players[player_id].name if player_id in players else None,
            outcome=meta.get('outcome'), shot_quality=meta.get('shot_quality'),
            on_target=meta.get('on_target'), player_in=meta.get('player_in'),
            player_out=meta.get('player_out'),
        ))
    ids = {event.event_id for event in observed}
    if not set(case['trigger_event_ids']) <= ids:
        raise ValueError('Case record is incomplete')
    facts = []
    metrics = ('event_count', 'pass_attempts', 'pass_completions', 'shots',
               'shots_on_target', 'goals', 'threats', 'progressive_actions')
    for index, window in enumerate(case['relevant_windows']):
        for team_id in teams:
            stats = _window_summary(selected, team_id, window['start'], window['end'])
            for metric in metrics:
                facts.append(RecordedFact(
                    fact_id=f'window:{index}:{team_id}:{metric}',
                    label=f"{window['label']}: {teams[team_id].name}: {metric}",
                    value=str(stats[metric]), event_ids=stats['event_ids'],
                ))
    for event in observed:
        if event.event_id in case['trigger_event_ids']:
            facts.append(RecordedFact(fact_id=f'trigger:{event.event_id}',
                         label='Recorded incident type', value=event.event_type,
                         event_ids=[event.event_id]))
    return VerifiedEvidence(
        match_id=match.match_id, case_id=case_id, seed=match.seed,
        allegation=case['title'], case_type=case['case_type'],
        incident_timestamp=case['detection_timestamp'], evidence_start=start,
        evidence_cutoff=cutoff, trigger_event_ids=case['trigger_event_ids'],
        events=observed, facts=facts, evidence_version=EVIDENCE_VERSION,
        limitations=[
            'These are synthetic event records, not real football tracking data.',
            'Observed associations do not establish causation or a different match outcome.',
            'No calibrated expected-goals or causal impact model is available.',
        ],
    )


def _reasoning_text(text: str, evidence: VerifiedEvidence) -> None:
    # Numeric claims belong only in exact-checked observations, never generated
    # prose. References live in typed fields, not free text. This catches invented
    # scores, times, percentages and familiar quantified-statistic spellings.
    if re.search(r'\d|%|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|'
                 r'eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|'
                 r'nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|'
                 r'hundred|thousand|million|percent|xg)\b', text, re.I):
        raise InvalidAgentOutput('numeric_reasoning')
    if re.search(r'\b(?:definitely|certainly|guaranteed|proved|proves|inevitably)\b', text, re.I):
        raise InvalidAgentOutput('overconfident_reasoning')
    # Prevent a model echoing backend secrets or URLs in public reasoning.
    if re.search(r'https?://|\b(?:api[_ -]?key|authorization|bearer|sk-)\b', text, re.I):
        raise InvalidAgentOutput('unsafe_reasoning')


def validate_submission(role: str, output, evidence: VerifiedEvidence) -> None:
    facts = {fact.fact_id: fact for fact in evidence.facts}
    known_ids = {event.event_id for event in evidence.events}

    def point(item: GroundedPoint):
        if not set(item.fact_ids) <= facts.keys():
            raise InvalidAgentOutput('unknown_fact_reference')
        if not set(item.event_ids) <= known_ids:
            raise InvalidAgentOutput('unknown_event_reference')
        cited = {event_id for fact_id in item.fact_ids for event_id in facts[fact_id].event_ids}
        if not set(item.event_ids) <= cited:
            raise InvalidAgentOutput('event_not_supported_by_fact')
        _reasoning_text(item.interpretation, evidence)

    if role == 'evidence':
        if not isinstance(output, EvidenceSubmission):
            raise InvalidAgentOutput('wrong_submission_type')
        for assertion in output.observations:
            if assertion.fact_id not in facts:
                raise InvalidAgentOutput('unknown_fact_reference')
            if assertion.value != facts[assertion.fact_id].value:
                raise InvalidAgentOutput('observation_value_mismatch')
        if not set(output.event_ids) <= known_ids:
            raise InvalidAgentOutput('unknown_event_reference')
        if not set(evidence.trigger_event_ids) <= set(output.event_ids):
            raise InvalidAgentOutput('missing_trigger_reference')
        point(output.interpretation)
    elif role in ('prosecution', 'defense'):
        if not isinstance(output, Argument) or output.stance != ('support' if role == 'prosecution' else 'challenge'):
            raise InvalidAgentOutput('invalid_stance')
        for item in output.points:
            point(item)
    else:
        if not isinstance(output, Ruling):
            raise InvalidAgentOutput('wrong_submission_type')
        for item in output.findings:
            point(item)
        _reasoning_text(output.prosecution_assessment, evidence)
        _reasoning_text(output.defense_assessment, evidence)
    _reasoning_text(output.uncertainty, evidence)


def fallback_parts(evidence: VerifiedEvidence):
    fact = next(f for f in evidence.facts if f.fact_id.startswith('trigger:'))
    def point(text):
        return GroundedPoint(interpretation=text, fact_ids=[fact.fact_id], event_ids=fact.event_ids)
    prosecution = Argument(stance='support', points=[point(
        'The recorded incident warrants examination within the completed evidence window.')],
        uncertainty='The record alone does not establish the alleged influence.')
    defense = Argument(stance='challenge', points=[point(
        'The incident record does not isolate its effect from alternative explanations.')],
        uncertainty='A counterfactual match outcome cannot be established from these records.')
    judge = Ruling(result='inconclusive', findings=[point(
        'The recorded incident is verifiable, while its causal influence remains uncertain.')],
        prosecution_assessment='The allegation identifies a recorded incident but does not prove its influence.',
        defense_assessment='Alternative explanations cannot be excluded with the available records.',
        confidence='low', uncertainty='The synthetic event window cannot establish causation.',
        causation_established=False, counterfactual_outcome='unknown')
    return prosecution, defense, judge
