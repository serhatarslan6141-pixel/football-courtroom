"""Compact model work, deterministic grounding, unchanged public contracts."""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest
from pydantic import ValidationError

from app import courtroom
from app.courtroom_context import agent_payload, assemble_evidence
from app.courtroom_evidence import build_evidence, InvalidAgentOutput, validate_submission
from app.courtroom_models import EvidenceSubmission
from app.synthetic_match import MATCH_LIBRARY, get_match
from app.case_detection import detect_cases
from test_courtroom import (MockWire, assert_azure_evidence_schema, assert_context_matches,
                            evidence_fact_choices, isolated, enabled, submissions, user_payload)

CASES = [
    ('synthetic-101', 'synthetic-101-missed_opportunity-away-3218', 3308),
    ('synthetic-202', 'synthetic-202-missed_opportunity-away-1910', 2000),
    ('synthetic-202', 'synthetic-202-missed_opportunity-home-4555', 4645),
    ('synthetic-303', 'synthetic-303-substitution_impact-away-4187', 4397),
]


@pytest.mark.parametrize('match_id,case_id,cutoff', CASES)
def test_full_four_agent_pipeline_has_compact_context_and_azure_schemas(
        enabled, tmp_path, match_id, case_id, cutoff):
    match = get_match(match_id)
    evidence = build_evidence(match, case_id, cutoff)
    before = evidence.model_dump_json()
    wire = MockWire(evidence)
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(match, case_id, cutoff, allow_live=True))
    assert result.source == 'live_ai'
    assert result.api_attempts == 4
    assert [entry.handoff_to for entry in result.trace] == ['prosecution', 'defense', 'judge', None]
    expected_facts = [fact.fact_id for fact in evidence.facts]
    original_size = len(json.dumps({'evidence': evidence.model_dump(), 'prior_submissions': {}}, separators=(',', ':')))
    for index, (role, body) in enumerate(wire.calls):
        payload = user_payload(body)
        assert_context_matches(payload['evidence'], evidence, role)
        assert list(payload['prior_submissions']) == list(courtroom.ROLES[:index])
        assert body['text']['format']['strict'] is True
        schema = body['text']['format']['schema']
        assert_azure_evidence_schema(schema)
        assert result.trace[index].input_digest == courtroom.digest(payload)
        output = getattr(result, 'evidence_agent' if role == 'evidence' else role)
        validate_submission(role, output, evidence)
        assert result.trace[index].output_digest == courtroom.digest(output.model_dump())
        if role == 'evidence':
            assert len(json.dumps(payload, separators=(',', ':'))) < original_size * .2
            assert set(schema['properties']) == {'fact_ids', 'explanation', 'uncertainty'}
            assert evidence_fact_choices(schema) == expected_facts
            assert body['max_output_tokens'] == 768
        if role == 'judge':
            assert schema['properties']['causation_established']['enum'] == [False]
            assert schema['properties']['counterfactual_outcome']['enum'] == ['unknown']
    assert evidence.model_dump_json() == before
    ledger = service.budget.path.read_bytes()
    cached = asyncio.run(service.analyze(match, case_id, cutoff, allow_live=True))
    assert cached.source == 'cached_ai' and cached.api_attempts == 0
    assert cached.model_dump(exclude={'source', 'api_attempts', 'disclosure'}) == result.model_dump(
        exclude={'source', 'api_attempts', 'disclosure'})
    assert len(wire.calls) == 4 and service.budget.path.read_bytes() == ledger


def test_all_builtin_cases_preserve_catalog_and_lossless_downstream_evidence():
    for match in MATCH_LIBRARY.values():
        for case in detect_cases(match.events, through_timestamp=5400, match_id=match.match_id):
            evidence = build_evidence(match, case['case_id'], 5400)
            before = evidence.model_dump_json()
            for role in courtroom.ROLES:
                payload = agent_payload(role, evidence, {})
                assert_context_matches(payload['evidence'], evidence, role)
                future = [e['event_id'] for e in match.events if e['timestamp'] > evidence.evidence_cutoff]
                assert not any(ref in json.dumps(payload) for ref in future)
            assert evidence.model_dump_json() == before


def test_evidence_prioritizes_facts_and_python_constructs_exact_values_and_support():
    e = build_evidence(get_match('synthetic-202'), 'synthetic-202-missed_opportunity-home-4555', 4645)
    chosen = [next(f for f in e.facts if f.fact_id.startswith('trigger:')),
              next(f for f in e.facts if f.value.isdigit() and f.event_ids)]
    selection = {'fact_ids': [f.fact_id for f in chosen],
        'explanation': 'The incident and surrounding spell support competing interpretations.',
        'uncertainty': 'Alternative explanations remain plausible.'}
    result = assemble_evidence(selection, e)
    assert [f.fact_id for f in result.observations] == selection['fact_ids']
    assert [f.value for f in result.observations] == [f.value for f in chosen]
    assert result.interpretation.interpretation == selection['explanation']
    assert set(e.trigger_event_ids) <= set(result.event_ids)
    assert len(result.interpretation.event_ids) <= 12 and len(result.event_ids) <= 20
    supports = {ref for fact in chosen for ref in fact.event_ids}
    assert set(result.interpretation.event_ids) <= supports
    assert all(e.evidence_start <= event.timestamp <= e.evidence_cutoff
        for event in e.events if event.event_id in result.event_ids)
    assert assemble_evidence(selection, e) == result


@pytest.mark.parametrize('corruption,reason', [
    ('unknown', 'unknown_fact_reference'), ('event_as_fact', 'unknown_fact_reference'),
    ('duplicate', 'duplicate_fact_reference'), ('numeric', 'numeric_reasoning'),
    ('certainty', 'overconfident_reasoning'), ('empty_support', 'missing_fact_support'),
])
def test_selection_assembly_fails_closed_without_repair(corruption, reason):
    e = build_evidence(get_match('synthetic-202'), 'synthetic-202-missed_opportunity-home-4555', 4645)
    fact = next(f for f in e.facts if f.fact_id.startswith('trigger:'))
    selection = {'fact_ids': [fact.fact_id], 'explanation': 'The recorded incident warrants cautious examination.',
                 'uncertainty': 'Alternative explanations remain plausible.'}
    if corruption == 'unknown': selection['fact_ids'] = [fact.fact_id + '-typo']
    elif corruption == 'event_as_fact': selection['fact_ids'] = e.trigger_event_ids
    elif corruption == 'duplicate': selection['fact_ids'] *= 2
    elif corruption == 'numeric': selection['explanation'] = 'There are two plausible explanations.'
    elif corruption == 'certainty': selection['explanation'] = 'The incident definitely changed the match.'
    else:
        e = e.model_copy(update={'facts': [fact.model_copy(update={'event_ids': []})]})
    before = deepcopy(selection)
    with pytest.raises(InvalidAgentOutput) as caught:
        assemble_evidence(selection, e)
    assert caught.value.reason == reason
    assert selection == before


@pytest.mark.parametrize('field,limit', [
    ('observations', 8), ('event_ids', 20), ('fact_ids', 8), ('interpretation_event_ids', 12),
])
@pytest.mark.parametrize('large', [False, True])
def test_canonical_public_array_constraints_are_unchanged(field, limit, large):
    e = build_evidence(get_match('synthetic-202'), 'synthetic-202-missed_opportunity-home-4555', 4645)
    raw = submissions(e)['evidence']
    target = raw['interpretation'] if field in ('fact_ids', 'interpretation_event_ids') else raw
    key = 'event_ids' if field == 'interpretation_event_ids' else field
    target[key] = [target[key][0]] * (limit + 1) if large else []
    with pytest.raises(ValidationError):
        EvidenceSubmission.model_validate(raw)


@pytest.mark.parametrize('field,limit', [('uncertainty', 500), ('interpretation', 600)])
@pytest.mark.parametrize('large', [False, True])
def test_canonical_public_text_constraints_are_unchanged(field, limit, large):
    e = build_evidence(get_match('synthetic-202'), 'synthetic-202-missed_opportunity-home-4555', 4645)
    raw = submissions(e)['evidence']
    target = raw if field == 'uncertainty' else raw['interpretation']
    target[field] = 'a' * (limit + 1 if large else 1)
    with pytest.raises(ValidationError):
        EvidenceSubmission.model_validate(raw)
