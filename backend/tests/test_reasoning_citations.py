"""Representative reproduction of the synthetic-303 Prosecution rejection.

The raw live response is not retained. All mutations below are mocked examples
of the confirmed fact/event relationship error, not recovered model content.
"""
import asyncio
from copy import deepcopy
import json

import httpx
import pytest

from app import courtroom
from app.courtroom_context import agent_payload, assemble_reasoning
from app.courtroom_evidence import build_evidence, digest, validate_submission, InvalidAgentOutput
from app.courtroom_models import Argument, Ruling
from app.synthetic_match import get_match
from test_courtroom import (MockWire, assert_azure_evidence_schema, enabled, isolated,
                            resolve_schema_node, submissions, user_payload)


@pytest.fixture
def evidence():
    return build_evidence(get_match('synthetic-303'),
                          'synthetic-303-missed_opportunity-home-2412', 2502)


def test_preserved_case_and_confirmed_relation_failure(evidence):
    assert digest(agent_payload('evidence', evidence, {})) == '2c87660655a08f6cd9963c9e751f912cc057ccfe99869c576a1d82d7076af29d'
    raw = submissions(evidence)['prosecution']
    point = raw['points'][0]
    known = {event.event_id for event in evidence.events}
    facts = {fact.fact_id: fact for fact in evidence.facts}
    point['event_ids'] = [next(ref for ref in known if ref not in facts[point['fact_ids'][0]].event_ids)]
    output = Argument.model_validate(raw)  # Schema succeeds, both IDs exist.
    with pytest.raises(InvalidAgentOutput) as caught:
        validate_submission('prosecution', output, evidence)
    assert caught.value.reason == 'event_not_supported_by_fact'


@pytest.mark.parametrize('role', ['prosecution', 'defense', 'judge'])
def test_assembly_preserves_reasoning_and_derives_only_supported_citations(evidence, role):
    wire = MockWire(evidence)
    raw = wire.outputs[role]
    key = 'findings' if role == 'judge' else 'points'
    selected = [next(f for f in evidence.facts if f.fact_id.startswith('trigger:')),
                *[f for f in evidence.facts if f.event_ids and f.value.isdigit()][:2]]
    raw[key][0]['fact_ids'] = [fact.fact_id for fact in selected]
    before = deepcopy(raw)
    result = assemble_reasoning(role, raw, evidence)
    assert raw == before
    point = getattr(result, key)[0]
    assert point.interpretation == raw[key][0]['interpretation']
    assert point.fact_ids == raw[key][0]['fact_ids']
    assert set(point.event_ids) <= {ref for fact in selected for ref in fact.event_ids}
    assert all(f.event_ids[0] in point.event_ids for f in selected)
    assert 1 <= len(point.event_ids) <= 12
    validate_submission(role, result, evidence)
    assert assemble_reasoning(role, raw, evidence) == result


@pytest.mark.parametrize('role', ['prosecution', 'defense', 'judge'])
@pytest.mark.parametrize('bad', ['unsupported_event', 'unknown_fact', 'duplicate_fact', 'numeric_prose'])
def test_mocked_bad_reasoning_stops_and_blocks_repeat(enabled, tmp_path, evidence, role, bad):
    wire = MockWire(evidence)
    point = wire.outputs[role]['findings' if role == 'judge' else 'points'][0]
    if bad == 'unsupported_event':
        support = next(f.event_ids for f in evidence.facts if f.fact_id == point['fact_ids'][0])
        point['event_ids'] = [next(e.event_id for e in evidence.events if e.event_id not in support)]
    elif bad == 'unknown_fact': point['fact_ids'] = ['private-reference-never-log']
    elif bad == 'duplicate_fact': point['fact_ids'] *= 2
    else: point['interpretation'] = 'There are two plausible readings of this spell.'
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    count = courtroom.ROLES.index(role) + 1
    assert result.source == 'deterministic_fallback' and result.evidence_agent is None
    assert result.api_attempts == len(wire.calls) == count
    assert result.trace[-1].agent == role and result.trace[-1].handoff_to is None
    diag = service.cache.read(result.cache_key)['diagnostics']
    expected = {'unsupported_event': 'schema_validation_failed', 'unknown_fact': 'unknown_fact_reference',
                'duplicate_fact': 'duplicate_fact_reference', 'numeric_prose': 'numeric_reasoning'}
    assert diag['reason'] == expected[bad]
    assert diag['stage'] == ('structured_output' if bad == 'unsupported_event' else 'grounding_validation')
    assert 'private-reference' not in json.dumps(service.cache.read(result.cache_key))
    again = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    assert again.error_category == 'previous_trial_failed_or_incomplete' and again.api_attempts == 0
    assert len(wire.calls) == count


def test_exact_case_complete_pipeline_serializes_selections_and_validates_public_handoffs(
        enabled, tmp_path, evidence):
    wire = MockWire(evidence)
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    assert result.source == 'live_ai' and result.api_attempts == 4
    expected = [fact.fact_id for fact in evidence.facts]
    for index, (role, body) in enumerate(wire.calls):
        schema = body['text']['format']['schema']
        assert_azure_evidence_schema(schema)
        assert body['text']['format']['strict'] is True
        assert body['max_output_tokens'] == courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[role]
        prior = user_payload(body)['prior_submissions']
        assert list(prior) == list(courtroom.ROLES[:index])
        for name, raw in prior.items():
            output = getattr(result, 'evidence_agent' if name == 'evidence' else name)
            assert raw == output.model_dump()  # Canonical, validated public output.
        if role != 'evidence':
            key = 'findings' if role == 'judge' else 'points'
            point = resolve_schema_node(schema, schema['properties'][key]['items'])
            assert set(point['properties']) == {'interpretation', 'fact_ids'}
            assert point['properties']['fact_ids']['items']['enum'] == expected
        output = getattr(result, 'evidence_agent' if role == 'evidence' else role)
        validate_submission(role, output, evidence)
    assert [entry.handoff_to for entry in result.trace] == ['prosecution', 'defense', 'judge', None]
    assert result.judge.causation_established is False
    assert result.judge.counterfactual_outcome == 'unknown'


@pytest.mark.parametrize('role', ['prosecution', 'defense', 'judge'])
def test_canonical_validator_still_rejects_mismatched_events(evidence, role):
    raw = submissions(evidence)[role]
    point = raw['findings' if role == 'judge' else 'points'][0]
    trigger = evidence.trigger_event_ids[0]
    point['event_ids'] = [next(event.event_id for event in evidence.events if event.event_id != trigger)]
    model = Ruling if role == 'judge' else Argument
    with pytest.raises(InvalidAgentOutput) as caught:
        validate_submission(role, model.model_validate(raw), evidence)
    assert caught.value.reason == 'event_not_supported_by_fact'


@pytest.mark.parametrize('role', ['prosecution', 'defense'])
def test_wire_stance_is_role_specific_and_local_validator_remains_independent(
        enabled, tmp_path, evidence, role):
    wire = MockWire(evidence)
    wire.outputs[role]['stance'] = 'challenge' if role == 'prosecution' else 'support'
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    body = wire.calls[-1][1]
    assert body['text']['format']['schema']['properties']['stance']['enum'] == [
        'support' if role == 'prosecution' else 'challenge']
    assert result.source == 'deterministic_fallback'
    assert service.cache.read(result.cache_key)['diagnostics']['reason'] == 'invalid_stance'


def test_all_roles_receive_local_limits_and_retain_sanitized_metrics(enabled, tmp_path, evidence):
    from app.courtroom_workflow import OUTPUT_GUIDANCE
    wire = MockWire(evidence)
    def usage(payload):
        payload['usage'] = {'input_tokens': 1234, 'output_tokens': 220, 'total_tokens': 1454}
        return payload
    wire.response_transform = usage
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    assert result.source == 'live_ai'
    record = service.cache.read(result.cache_key)
    assert list(record['agent_diagnostics']) == list(courtroom.ROLES)
    for role, body in wire.calls:
        serialized = json.dumps(body)
        assert OUTPUT_GUIDANCE[role] in serialized.replace('\\"', '"')
        assert f'Output ceiling: {courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[role]} tokens.' in serialized
        metadata = record['agent_diagnostics'][role]
        assert metadata['http_status'] == 200 and metadata['response_status'] == 'completed'
        assert metadata['input_tokens'] == 1234 and metadata['output_tokens'] == 220
        assert metadata['total_tokens'] == 1454
        assert len(metadata['prompt_digest']) == 64
    diagnostic_text = json.dumps(record['agent_diagnostics'])
    assert 'fake-secret' not in diagnostic_text
    assert 'interpretation' not in diagnostic_text and 'fact_ids' not in diagnostic_text


@pytest.mark.parametrize('failure,expected_status,category', [
    ('dns', None, 'dns_failure'), ('timeout', None, 'timeout'),
    (503, 503, 'provider_unavailable')])
def test_later_network_failure_does_not_inherit_previous_response_status(
        enabled, tmp_path, evidence, failure, expected_status, category):
    wire = MockWire(evidence)
    wire.fail_role, wire.fail_status = 'prosecution', failure
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    assert result.source == 'deterministic_fallback' and result.api_attempts == 2
    assert result.error_category == category and result.http_status == expected_status
    record = service.cache.read(result.cache_key)
    assert record['agent_diagnostics']['evidence']['http_status'] == 200
    assert record['agent_diagnostics']['prosecution']['http_status'] == expected_status
    assert 'fake-secret' not in json.dumps(record)


@pytest.mark.parametrize('verdict', ['prosecution_supported', 'defense_supported', 'inconclusive'])
def test_complete_trial_accepts_each_cautious_ruling(enabled, tmp_path, evidence, verdict):
    wire = MockWire(evidence)
    wire.outputs['judge']['result'] = verdict
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    assert result.source == 'live_ai' and result.judge.result == verdict
    assert result.judge.causation_established is False


@pytest.mark.parametrize('role', courtroom.ROLES)
@pytest.mark.parametrize('violation', ['long_text', 'empty_array', 'large_array'])
def test_all_roles_reject_local_bounds_omitted_from_wire_schema(
        enabled, tmp_path, evidence, role, violation):
    wire = MockWire(evidence)
    raw = wire.outputs[role]
    if violation == 'long_text':
        raw['uncertainty'] = 'a' * (181 if role == 'evidence' else 501)
    else:
        key = 'fact_ids' if role == 'evidence' else 'findings' if role == 'judge' else 'points'
        raw[key] = [] if violation == 'empty_array' else raw[key] * 4
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(get_match(evidence.match_id), evidence.case_id, 2502, allow_live=True))
    assert result.source == 'deterministic_fallback'
    assert result.api_attempts == len(wire.calls) == courtroom.ROLES.index(role) + 1
    diagnostics = service.cache.read(result.cache_key)['diagnostics']
    assert diagnostics['stage'] == 'structured_output'
    assert diagnostics['reason'] == 'schema_validation_failed'
    assert result.trace[-1].handoff_to is None
