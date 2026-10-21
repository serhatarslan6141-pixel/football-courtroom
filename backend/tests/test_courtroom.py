"""Real framework and SDK execution over MockTransport; never load .env."""
import asyncio
from dataclasses import replace
import json
import socket
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from app import courtroom, main
from app.case_detection import detect_cases
from app.courtroom_evidence import build_evidence, validate_submission, InvalidAgentOutput
from app.courtroom_models import EvidenceSubmission
from app.foundry import DailyRequestBudget
from app.synthetic_match import generate_match, get_match

pytest.importorskip('agent_framework', reason='Full Phase 4B tests require requirements-agents.txt and Python >=3.10')


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in list(courtroom.os.environ):
        if name.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'OPENAI_', 'COURTROOM_')):
            monkeypatch.delenv(name)
    def network_forbidden(*args, **kwargs):
        raise AssertionError('Real sockets are forbidden in Phase 4B tests')
    monkeypatch.setattr(socket.socket, 'connect', network_forbidden)


@pytest.fixture(scope='module')
def match():
    return generate_match(101)


@pytest.fixture
def evidence(match):
    case = detect_cases(match.events, through_timestamp=5400, match_id=match.match_id)[0]
    return build_evidence(match, case['case_id'], 5400)


@pytest.fixture
def enabled(monkeypatch):
    for name, value in {
        'FOUNDRY_LIVE_ENABLED': 'true', 'COURTROOM_LIVE_ENABLED': 'true',
        'AZURE_OPENAI_ENDPOINT': 'https://test-resource.services.ai.azure.com',
        'AZURE_OPENAI_API_KEY': 'fake-secret-never-output',
        'AZURE_OPENAI_DEPLOYMENT': 'gpt-4.1-mini',
        'FOUNDRY_MAX_OUTPUT_TOKENS': '256', 'FOUNDRY_MAX_RETRIES': '2',
    }.items():
        monkeypatch.setenv(name, value)


def submissions(evidence):
    fact = next(f for f in evidence.facts if f.fact_id.startswith('trigger:'))
    point = {'interpretation': 'The recorded incident may support a cautious reading of the allegation.',
             'fact_ids': [fact.fact_id], 'event_ids': fact.event_ids}
    uncertainty = 'The available records cannot isolate causal influence.'
    return {
        'evidence': {'observations': [{'fact_id': fact.fact_id, 'value': fact.value}],
                     'event_ids': evidence.trigger_event_ids, 'interpretation': point,
                     'uncertainty': uncertainty},
        'prosecution': {'stance': 'support', 'points': [point], 'uncertainty': uncertainty},
        'defense': {'stance': 'challenge', 'points': [{**point, 'interpretation':
            'The prosecution reading may overlook alternative explanations for the recorded incident.'}],
                    'uncertainty': uncertainty},
        'judge': {'result': 'inconclusive', 'findings': [point],
                  'prosecution_assessment': 'The prosecution identifies a plausible interpretation of the incident.',
                  'defense_assessment': 'The defense reasonably challenges a causal reading of the record.',
                  'confidence': 'low', 'uncertainty': uncertainty,
                  'causation_established': False, 'counterfactual_outcome': 'unknown'},
    }


class MockWire:
    def __init__(self, evidence):
        self.calls = []
        self.outputs = json.loads(json.dumps(submissions(evidence)))
        original = self.outputs['evidence']
        self.outputs['evidence'] = {'fact_ids': original['interpretation']['fact_ids'],
            'explanation': original['interpretation']['interpretation'], 'uncertainty': original['uncertainty']}
        for role in ('prosecution', 'defense', 'judge'):
            key = 'findings' if role == 'judge' else 'points'
            self.outputs[role][key] = [{k: v for k, v in point.items() if k != 'event_ids'}
                                      for point in self.outputs[role][key]]
        self.fail_role = None
        self.fail_status = None
        self.on_call = None
        self.delay = 0
        self.response_status = 'completed'
        self.response_transform = None

    async def handle(self, request):
        body = json.loads(request.content)
        role = next(role for role in courtroom.ROLES if f'ROLE={role}' in json.dumps(body))
        self.calls.append((role, body))
        if self.on_call:
            self.on_call(role)
        if self.delay:
            await asyncio.sleep(self.delay)
        if role == self.fail_role:
            if self.fail_status == 'dns':
                raise httpx.ConnectError('fake-secret-never-output', request=request) from socket.gaierror(socket.EAI_NONAME, 'private-host')
            if self.fail_status == 'timeout':
                raise httpx.ReadTimeout('fake-secret-never-output', request=request)
            return httpx.Response(self.fail_status, json={'error': {'message': 'fake-secret-never-output'}})
        output = self.outputs[role]
        text = output if isinstance(output, str) else json.dumps(output)
        payload = {
            'id': f'resp_{role}', 'object': 'response', 'created_at': 0,
            'model': 'gpt-4.1-mini', 'status': self.response_status,
            'output': [{'type': 'message', 'id': f'msg_{role}', 'role': 'assistant',
                        'status': 'completed', 'content': [{'type': 'output_text',
                        'text': text, 'annotations': []}]}],
        }
        return httpx.Response(200, json=self.response_transform(payload) if self.response_transform else payload)


@pytest.fixture
def wired(tmp_path, evidence):
    wire = MockWire(evidence)
    budget = DailyRequestBudget(tmp_path / 'usage.json')
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
                                     budget, httpx.MockTransport(wire.handle))
    return service, wire


def run(service, match, evidence, **kwargs):
    return asyncio.run(service.analyze(match, evidence.case_id, 5400, allow_live=True, **kwargs))


def user_payload(body):
    for item in body['input']:
        if item.get('role') == 'user':
            content = item['content']
            return json.loads(content if isinstance(content, str) else content[0]['text'])
    raise AssertionError('No structured shared input')


def assert_context_matches(context, evidence, role):
    from app.courtroom_models import ObservedEvent, VerifiedEvidence
    assert context['evidence_cutoff'] == evidence.evidence_cutoff
    if role == 'evidence':
        assert context['facts'] == [
            {'fact_id': f.fact_id, 'label': f.label, 'value': f.value} for f in evidence.facts]
        assert context['trigger_events'] == [e.model_dump(exclude_none=True) for e in evidence.events
                                             if e.event_id in evidence.trigger_event_ids]
        assert 'events' not in context and 'support_groups' not in context
    else:
        full = {k: v for k, v in context.items() if k != 'support_groups'}
        full['facts'] = [{**{k: v for k, v in f.items() if k != 'support_group'},
                          'event_ids': context['support_groups'][f['support_group']]} for f in context['facts']]
        full['events'] = [{**dict.fromkeys(ObservedEvent.model_fields), **e} for e in context['events']]
        assert VerifiedEvidence.model_validate(full) == evidence


@pytest.fixture
def next_controlled_case(tmp_path):
    """Exact proposed browser case, isolated from all preserved live records."""
    match = get_match('synthetic-202')
    evidence = build_evidence(match, 'synthetic-202-missed_opportunity-away-1910', 2000)
    wire = MockWire(evidence)
    budget = DailyRequestBudget(tmp_path / 'usage.json')
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
                                     budget, httpx.MockTransport(wire.handle))
    return match, evidence, service, wire


def test_next_controlled_case_full_ui_contract_and_cache(enabled, next_controlled_case, monkeypatch):
    match, evidence, service, wire = next_controlled_case
    assert evidence.incident_timestamp == 1910
    assert (evidence.evidence_start, evidence.evidence_cutoff) == (1820, 2000)
    assert len(evidence.events) == 81
    with pytest.raises(KeyError):
        build_evidence(match, evidence.case_id, 1999)
    assert build_evidence(match, evidence.case_id, 5400) == evidence
    monkeypatch.setattr(main, 'trial_service', service)
    path = f'/api/matches/{match.match_id}/cases/{evidence.case_id}/courtroom'
    with TestClient(main.app) as client:
        assert client.post(path + '/prepare', json={'through_timestamp': 2000}).json() == {
            'status': 'confirmation_required', 'result': None}
        assert not wire.calls and not service.budget.path.exists()
        response = client.post(path, json={'through_timestamp': 2000, 'allow_live': True})
        assert response.status_code == 200
        result = courtroom.TrialResult.model_validate(response.json())
        assert result.source == 'live_ai'
        assert result.api_attempts == 4
        assert result.evidence == evidence
        assert [role for role, _ in wire.calls] == list(courtroom.ROLES)
        assert [entry.handoff_to for entry in result.trace] == ['prosecution', 'defense', 'judge', None]
        for index, (role, body) in enumerate(wire.calls):
            output = getattr(result, 'evidence_agent' if role == 'evidence' else role)
            validate_submission(role, output, evidence)
            trace = result.trace[index]
            payload = user_payload(body)
            assert trace.status == 'completed'
            assert trace.input_digest == courtroom.digest(payload)
            assert trace.output_digest == courtroom.digest(output.model_dump())
            assert_context_matches(payload['evidence'], evidence, role)
            assert list(payload['prior_submissions']) == list(courtroom.ROLES[:index])
            assert body['max_output_tokens'] == courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[role]
            assert len(json.dumps(body).encode()) < 128000
            assert body['text']['format']['strict'] is True
        assert result.judge.result == 'inconclusive'
        assert result.judge.causation_established is False
        assert result.judge.counterfactual_outcome == 'unknown'
        ledger = service.budget.path.read_bytes()
        for replay_cursor in (2000, 5400):
            cached = client.post(path + '/prepare', json={'through_timestamp': replay_cursor}).json()
            assert cached['status'] == 'ready'
            assert cached['result']['source'] == 'cached_ai'
            assert cached['result']['api_attempts'] == 0
        assert len(wire.calls) == 4
        assert service.budget.path.read_bytes() == ledger


@pytest.mark.parametrize('role', courtroom.ROLES)
def test_next_controlled_case_invalid_citation_stops_and_blocks_retry(enabled, next_controlled_case, role):
    match, evidence, service, wire = next_controlled_case
    output = wire.outputs[role]
    if role == 'evidence':
        output['fact_ids'] = ['outside-authorized-case-window']
    else:
        output['findings' if role == 'judge' else 'points'][0]['event_ids'] = ['outside-authorized-case-window']
    result = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'invalid_agent_output'
    assert result.evidence_agent is None
    assert result.api_attempts == len(wire.calls) == courtroom.ROLES.index(role) + 1
    assert result.trace[-1].handoff_to is None
    repeated = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert repeated.error_category == 'previous_trial_failed_or_incomplete'
    assert repeated.api_attempts == 0
    assert len(wire.calls) == result.api_attempts


def test_next_controlled_case_existing_usage_plus_four_cap(enabled, next_controlled_case, monkeypatch):
    from datetime import datetime, timezone
    match, evidence, service, wire = next_controlled_case
    service.budget.path.write_text(json.dumps({
        'day': datetime.now(timezone.utc).date().isoformat(), 'count': 5}))
    monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '9')
    result = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert result.source == 'live_ai'
    assert json.loads(service.budget.path.read_text())['count'] == 9
    with pytest.raises(courtroom.FoundryUnavailable):
        service.budget.reserve(9)
    assert len(wire.calls) == 4


def resolve_schema_node(schema, node):
    return schema['$defs'][node['$ref'].rsplit('/', 1)[-1]] if '$ref' in node else node


def evidence_fact_choices(schema):
    return schema['properties']['fact_ids']['items']['enum']


def assert_azure_evidence_schema(schema):
    """Check the serialized provider subset, including schemas behind refs."""
    supported = {'type', 'title', 'description', 'properties', 'required',
                 'additionalProperties', 'items', 'enum', 'anyOf', '$defs', '$ref'}
    assert schema['type'] == 'object'
    def visit(node, depth=0):
        assert set(node) <= supported
        if '$ref' in node:
            visit(resolve_schema_node(schema, node), depth)
            return
        if node.get('type') == 'object':
            depth += 1
            assert depth <= 5
            assert node['additionalProperties'] is False
            assert set(node['required']) == set(node['properties'])
            for child in node['properties'].values():
                visit(child, depth)
        if 'items' in node:
            visit(node['items'], depth)
        for child in node.get('anyOf', []):
            visit(child, depth)
    visit(schema)
    for node in schema.get('$defs', {}).values():
        visit(node)
    assert sum(len(node.get('properties', {})) for node in [schema, *schema.get('$defs', {}).values()]) <= 100


def test_exact_case_wire_schema_only_offers_authorized_facts(enabled, next_controlled_case):
    from app.courtroom_workflow import evidence_response_schema
    match, evidence, service, wire = next_controlled_case
    result = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert result.source == 'live_ai'
    body = wire.calls[0][1]
    schema = body['text']['format']['schema']
    assert_azure_evidence_schema(schema)
    expected = [fact.fact_id for fact in evidence.facts]
    assert evidence_fact_choices(schema) == expected
    assert body['text']['format']['strict'] is True
    assert body['max_output_tokens'] == 768
    assert 'An event_id alone is not a fact_id' in body['instructions']
    assert all(1820 <= event.timestamp <= 2000 for event in evidence.events)
    other = build_evidence(get_match('synthetic-101'),
                          'synthetic-101-missed_opportunity-away-3218', 3308)
    other_schema = evidence_response_schema(other).model_json_schema()
    assert evidence_fact_choices(other_schema) == [fact.fact_id for fact in other.facts]
    assert evidence_fact_choices(schema) == expected  # No cross-case mutation.
    trigger = next(f.fact_id for f in other.facts if f.fact_id.startswith('trigger:'))
    assert trigger not in expected
    # JSON Schema constraints narrow generation; the unchanged runtime validator
    # remains responsible for rejecting even a nonconforming provider response.
    assert all(event.event_id not in expected for event in evidence.events)


@pytest.mark.parametrize('field', ['selection.fact_ids'])
@pytest.mark.parametrize('kind', ['unknown', 'event_id', 'mistyped_fact', 'other_case_fact'])
def test_exact_case_unknown_facts_have_safe_field_diagnostics(
        enabled, next_controlled_case, field, kind):
    match, evidence, service, wire = next_controlled_case
    invalid = {
        'unknown': 'private-model-content-never-log',
        'event_id': evidence.trigger_event_ids[0],
        'mistyped_fact': 'trigger' + evidence.trigger_event_ids[0],
        'other_case_fact': next(f.fact_id for f in build_evidence(get_match('synthetic-101'),
            'synthetic-101-missed_opportunity-away-3218', 3308).facts if f.fact_id.startswith('trigger:')),
    }[kind]
    output = wire.outputs['evidence']
    output['fact_ids'] = [invalid]
    result = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert result.source == 'deterministic_fallback'
    assert result.api_attempts == len(wire.calls) == 1
    assert [role for role, _ in wire.calls] == ['evidence']
    assert result.evidence_agent is None and result.trace[0].handoff_to is None
    record = service.cache.read(result.cache_key)
    diagnostic = record['diagnostics']
    assert record['http_status'] == 200
    assert diagnostic['stage'] == 'grounding_validation'
    assert diagnostic['reason'] == 'unknown_fact_reference'
    assert diagnostic['field'] == field
    assert diagnostic['reference_kind'] == ('event_id' if kind == 'event_id' else 'unknown')
    assert diagnostic['max_output_tokens'] == 768
    serialized = json.dumps(record)
    assert invalid not in serialized
    assert output['uncertainty'] not in serialized
    assert 'private-model-content' not in result.model_dump_json()
    before = service.budget.path.read_bytes()
    blocked = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert blocked.error_category == 'previous_trial_failed_or_incomplete'
    assert blocked.api_attempts == 0 and len(wire.calls) == 1
    assert service.budget.path.read_bytes() == before


def test_reference_diagnostics_reject_unapproved_metadata(evidence):
    from app.courtroom_workflow import failure_category
    state = courtroom.TrialState(evidence)
    exc = InvalidAgentOutput('unknown_fact_reference', field='private-never-log',
                             reference_kind='private-never-log')
    assert failure_category(exc, state) == 'invalid_agent_output'
    assert state.diagnostics == {'reason': 'unknown_fact_reference'}


def test_exact_case_evidence_only_offline_path_uses_new_schema(
        enabled, next_controlled_case, monkeypatch):
    from agent_framework import WorkflowBuilder
    from agent_framework.openai import OpenAIChatClient
    from app.courtroom_workflow import execute_evidence_diagnostic
    from app.foundry import FoundrySettings
    _, evidence, service, wire = next_controlled_case
    monkeypatch.setenv('COURTROOM_LIVE_ENABLED', 'false')
    monkeypatch.setenv('EVIDENCE_DIAGNOSTIC_LIVE_ENABLED', 'true')
    created = []
    original = OpenAIChatClient.as_agent
    def as_agent(self, *args, **kwargs):
        created.append(kwargs['name'])
        return original(self, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError('Evidence-only must not create a full-trial handoff')
    monkeypatch.setattr(OpenAIChatClient, 'as_agent', as_agent)
    monkeypatch.setattr(WorkflowBuilder, 'add_edge', forbidden)
    state = courtroom.TrialState(evidence)
    asyncio.run(execute_evidence_diagnostic(state, FoundrySettings.from_env(),
        courtroom.TrialConfig.from_env(), service.budget, service.transport))
    assert created == ['FootballCourtroom_evidence']
    assert state.api_attempts == len(wire.calls) == 1
    assert list(state.outputs) == ['evidence']
    assert state.trace[0].handoff_to is None
    schema = wire.calls[0][1]['text']['format']['schema']
    assert_azure_evidence_schema(schema)
    expected = [fact.fact_id for fact in evidence.facts]
    assert evidence_fact_choices(schema) == expected


def test_wire_normalization_copies_schema_nodes_without_touching_data():
    from copy import deepcopy
    from app.courtroom_workflow import normalize_azure_evidence_schema
    schema = {'type': 'object', 'properties': {
        'minLength': {'type': 'string', 'minLength': 8, 'enum': ['minItems', 'maxLength']},
        'nested': {'anyOf': [{'type': 'array', 'minItems': 1, 'maxItems': 8,
                             'items': {'$ref': '#/$defs/Value'}}, {'type': 'null'}]},
    }, '$defs': {'Value': {'type': 'string', 'maxLength': 100}}}
    before = deepcopy(schema)
    normalized = normalize_azure_evidence_schema(schema)
    assert schema == before
    assert normalized['properties']['minLength'] == {'type': 'string', 'enum': ['minItems', 'maxLength']}
    assert normalized['properties']['nested']['anyOf'][0] == {
        'type': 'array', 'items': {'$ref': '#/$defs/Value'}}
    assert normalized['$defs']['Value'] == {'type': 'string'}
    assert normalize_azure_evidence_schema(normalized) == normalized


def test_wire_adapter_does_not_weaken_local_schema(next_controlled_case):
    from app.courtroom_workflow import evidence_response_schema, evidence_wire_response_schema
    from pydantic import ValidationError
    _, evidence, _, wire = next_controlled_case
    canonical_before = EvidenceSubmission.model_json_schema()
    local = evidence_response_schema(evidence)
    local_before = local.model_json_schema()
    adapter = evidence_wire_response_schema(evidence)
    outbound = adapter.model_json_schema()
    assert_azure_evidence_schema(outbound)
    assert EvidenceSubmission.model_json_schema() == canonical_before
    assert local.model_json_schema() == local_before
    assert local_before['properties']['fact_ids']['maxItems'] == 3
    assert local_before['properties']['uncertainty']['maxLength'] == 180
    invalid = {**wire.outputs['evidence'], 'uncertainty': 'a' * 501}
    for model in (local, adapter):
        with pytest.raises(ValidationError):
            model.model_validate(invalid)


@pytest.mark.parametrize('field,boundary', [
    ('uncertainty', 'short'), ('uncertainty', 'long'),
    ('explanation', 'short'), ('explanation', 'long'),
    ('fact_ids', 'empty'), ('fact_ids', 'large'),
])
def test_normalized_wire_retains_local_length_and_array_limits(
        enabled, next_controlled_case, field, boundary):
    match, evidence, service, wire = next_controlled_case
    output = wire.outputs['evidence']
    if field == 'fact_ids':
        output[field] = [] if boundary == 'empty' else output[field] * 4
    else:
        output[field] = 'a' * (1 if boundary == 'short' else (181 if field == 'uncertainty' else 241))
    result = asyncio.run(service.analyze(match, evidence.case_id, 2000, allow_live=True))
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'invalid_agent_output'
    assert result.api_attempts == len(wire.calls) == 1
    assert result.evidence_agent is None and result.trace[0].handoff_to is None
    body = wire.calls[0][1]
    assert_azure_evidence_schema(body['text']['format']['schema'])
    assert body['text']['format']['strict'] is True
    assert body['max_output_tokens'] == 768
    diagnostic = service.cache.read(result.cache_key)['diagnostics']
    assert diagnostic['stage'] == 'structured_output'
    assert diagnostic['reason'] == 'schema_validation_failed'


def test_real_framework_order_handoffs_shared_state(enabled, wired, match, evidence):
    service, wire = wired
    result = run(service, match, evidence)
    assert result.source == 'live_ai', result.error_category
    assert result.api_attempts == 4
    assert result.http_status == 200
    assert [role for role, _ in wire.calls] == list(courtroom.ROLES)
    assert [item.handoff_to for item in result.trace] == ['prosecution', 'defense', 'judge', None]
    for index, (role, body) in enumerate(wire.calls):
        assert body['model'] == 'gpt-4.1-mini'
        assert body['max_output_tokens'] == courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[role]
        assert body['store'] is False
        assert not body.get('tools')
        assert body['text']['format']['type'] == 'json_schema'
        assert body['text']['format']['strict'] is True
        payload = user_payload(body)
        assert_context_matches(payload['evidence'], evidence, role)
        assert list(payload['prior_submissions']) == list(courtroom.ROLES[:index])
    assert json.loads(service.budget.path.read_text())['count'] == 4
    assert 'fake-secret' not in result.model_dump_json()


def test_disabled_and_opt_in_make_no_calls(wired, match, evidence, monkeypatch):
    service, wire = wired
    assert run(service, match, evidence).error_category == 'live_disabled'
    monkeypatch.setenv('FOUNDRY_LIVE_ENABLED', 'true')
    assert run(service, match, evidence).error_category == 'live_disabled'
    result = asyncio.run(service.analyze(match, evidence.case_id, 5400))
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'live_not_requested'
    assert wire.calls == []
    assert not service.budget.path.exists()


@pytest.mark.parametrize('role', courtroom.ROLES)
def test_each_agent_failure_discards_partial_outputs_and_never_retries(enabled, wired, match, evidence, role):
    service, wire = wired
    wire.fail_role, wire.fail_status = role, 503
    result = run(service, match, evidence)
    assert result.source == 'deterministic_fallback'
    assert result.evidence_agent is None
    assert result.judge.result == 'inconclusive'
    assert result.error_category == 'provider_unavailable'
    assert result.http_status == 503
    assert len(wire.calls) == courtroom.ROLES.index(role) + 1
    assert result.trace[-1].status == 'failed'
    assert result.trace[-1].handoff_to is None
    assert json.loads(service.budget.path.read_text())['count'] == result.api_attempts
    assert 'fake-secret' not in result.model_dump_json()
    again = run(service, match, evidence)
    assert again.error_category == 'previous_trial_failed_or_incomplete'
    assert again.api_attempts == 0
    assert len(wire.calls) == result.api_attempts


@pytest.mark.parametrize('status,category', [(401, 'authentication_or_access_denied'),
    (403, 'authentication_or_access_denied'), (404, 'deployment_or_endpoint_unavailable'),
    (429, 'rate_limited'), ('dns', 'dns_failure'), ('timeout', 'timeout')])
def test_sanitized_failure_categories(enabled, wired, match, evidence, status, category):
    service, wire = wired
    wire.fail_role, wire.fail_status = 'evidence', status
    result = run(service, match, evidence)
    assert result.error_category == category
    assert result.api_attempts == len(wire.calls) == 1
    assert 'fake-secret' not in result.model_dump_json()


@pytest.mark.parametrize('bad_output', ['{bad json', '{}', '[]'])
def test_malformed_and_missing_fields(enabled, wired, match, evidence, bad_output):
    service, wire = wired
    wire.outputs['evidence'] = bad_output
    result = run(service, match, evidence)
    assert result.source == 'deterministic_fallback'
    assert len(wire.calls) == 1


@pytest.mark.parametrize('corruption', ['event', 'fact', 'statistic', 'numeric_prose', 'certainty', 'extra_field'])
def test_hallucinated_outputs_stop_before_next_agent(enabled, wired, match, evidence, corruption):
    service, wire = wired
    output = wire.outputs['evidence']
    if corruption == 'event':
        output['event_ids'] = ['invented-event']
    elif corruption == 'fact':
        output['fact_ids'] = ['invented-fact']
    elif corruption == 'statistic':
        output['observations'] = [{'fact_id': 'invented-fact', 'value': '999'}]
    elif corruption == 'numeric_prose':
        output['explanation'] = 'The team scored ninety goals in the spell.'
    elif corruption == 'certainty':
        output['explanation'] = 'The incident definitely changed the match outcome.'
    else:
        output['invented_statistics'] = {'xg': 999}
    result = run(service, match, evidence)
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'invalid_agent_output'
    assert len(wire.calls) == 1


def test_no_future_events_or_full_match_data(enabled, wired, match, evidence):
    service, wire = wired
    result = run(service, match, evidence)
    assert result.source == 'live_ai'
    assert all(evidence.evidence_start <= e.timestamp <= evidence.evidence_cutoff for e in evidence.events)
    assert max(e['timestamp'] for e in match.events) > evidence.evidence_cutoff
    future = {e['event_id'] for e in match.events if e['timestamp'] > evidence.evidence_cutoff}
    for _, body in wire.calls:
        payload = user_payload(body)
        assert not any(event_id in json.dumps(payload) for event_id in future)
    at_boundary = build_evidence(match, evidence.case_id, evidence.evidence_cutoff)
    assert at_boundary == evidence
    with pytest.raises(KeyError):
        build_evidence(match, evidence.case_id, evidence.evidence_cutoff - 1)


def test_future_reference_in_model_output_rejected(enabled, wired, match, evidence):
    service, wire = wired
    future = next(e for e in match.events if e['timestamp'] > evidence.evidence_cutoff)
    wire.outputs['prosecution']['points'][0]['event_ids'] = [future['event_id']]
    result = run(service, match, evidence)
    assert result.error_category == 'invalid_agent_output'
    assert len(wire.calls) == 2


@pytest.mark.parametrize('limit,expected', [(0, 0), (1, 1), (3, 3)])
def test_per_trial_call_limit(enabled, monkeypatch, wired, match, evidence, limit, expected):
    service, wire = wired
    monkeypatch.setenv('COURTROOM_MAX_MODEL_CALLS', str(limit))
    result = run(service, match, evidence)
    assert result.error_category == 'trial_call_limit'
    assert result.api_attempts == len(wire.calls) == expected


def test_partial_daily_budget_exhaustion(enabled, monkeypatch, wired, match, evidence):
    service, wire = wired
    monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '2')
    result = run(service, match, evidence)
    assert result.error_category == 'daily_budget_unavailable'
    assert result.api_attempts == len(wire.calls) == 2
    assert json.loads(service.budget.path.read_text())['count'] == 2


def test_cache_persists_and_returns_no_duplicate_calls(enabled, wired, match, evidence):
    service, wire = wired
    first = run(service, match, evidence)
    assert first.source == 'live_ai'
    second_service = courtroom.TrialService(service.cache, service.budget, service.transport)
    second = run(second_service, match, evidence)
    assert second.source == 'cached_ai'
    assert second.api_attempts == 0
    assert second.original_api_attempts == 4
    assert first.cache_key == second.cache_key
    assert len(wire.calls) == 4


def test_duplicate_concurrent_trial_single_flight(enabled, wired, match, evidence):
    service, wire = wired
    wire.delay = .01
    async def concurrent():
        return await asyncio.gather(*(service.analyze(match, evidence.case_id, 5400, allow_live=True) for _ in range(3)))
    results = asyncio.run(concurrent())
    assert len(wire.calls) == 4
    assert sum(result.source == 'live_ai' for result in results) == 1
    assert sum(result.error_category == 'trial_in_progress' for result in results) == 2


def test_cache_identity_includes_seed_evidence_and_config(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    first = run(service, match, evidence)
    changed_seed = run(service, replace(match, seed=match.seed + 1), evidence)
    monkeypatch.setenv('COURTROOM_MAX_OUTPUT_TOKENS', '128')
    changed_config = run(service, match, evidence)
    assert len({first.cache_key, changed_seed.cache_key, changed_config.cache_key}) == 3


def test_changed_evidence_invalidates_cache(enabled, wired, match, evidence):
    service, wire = wired
    first = run(service, match, evidence)
    updated = replace(match, home_team=replace(match.home_team, name='Updated synthetic team'))
    second = run(service, updated, evidence)
    assert first.cache_key != second.cache_key
    assert second.source == 'live_ai'
    assert len(wire.calls) == 8


def test_probe_token_limit_does_not_truncate_trials(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setenv('FOUNDRY_MAX_OUTPUT_TOKENS', '32')
    result = run(service, match, evidence)
    assert result.source == 'live_ai'
    assert all(body['max_output_tokens'] == courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[role]
               for role, body in wire.calls)
    monkeypatch.setenv('COURTROOM_MAX_INPUT_BYTES', '1024')
    again = run(service, match, evidence)
    assert again.error_category == 'input_limit'
    assert again.api_attempts == 0


def test_kill_switch_between_stages(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    wire.on_call = lambda role: monkeypatch.setenv('COURTROOM_LIVE_ENABLED', 'false')
    result = run(service, match, evidence)
    assert result.error_category == 'live_disabled'
    assert result.api_attempts == len(wire.calls) == 1


def test_api_defaults_fallback_and_retains_existing_endpoints(wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setattr(main, 'trial_service', service)
    monkeypatch.setattr(main, 'require_match', lambda _: match)
    client = TestClient(main.app)
    path = f'/api/matches/{match.match_id}/cases/{evidence.case_id}/courtroom'
    response = client.post(path, json={'through_timestamp': 5400})
    assert response.status_code == 200
    assert response.json()['source'] == 'deterministic_fallback'
    assert response.json()['judge']['result'] == 'inconclusive'
    assert client.post(path, json={'through_timestamp': evidence.evidence_cutoff - 1}).status_code == 404
    assert client.post(path, json={'through_timestamp': -1}).status_code == 422
    assert client.post(path, json={'through_timestamp': 5400, 'prompt': 'untrusted'}).status_code == 422
    assert client.get('/health').status_code == 200
    assert client.get(f'/api/matches/{match.match_id}/state?through_timestamp=100').status_code == 200
    assert wire.calls == []


def test_api_live_and_cached_metadata(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setattr(main, 'trial_service', service)
    monkeypatch.setattr(main, 'require_match', lambda _: match)
    client = TestClient(main.app)
    path = f'/api/matches/{match.match_id}/cases/{evidence.case_id}/courtroom'
    for expected in ['live_ai', 'cached_ai']:
        response = client.post(path, json={'through_timestamp': 5400, 'allow_live': True})
        assert response.status_code == 200
        assert response.json()['source'] == expected
        assert len(response.json()['trace']) == 4
    assert len(wire.calls) == 4


def test_incomplete_json_response_is_rejected(enabled, wired, match, evidence):
    service, wire = wired
    wire.response_status = 'incomplete'
    result = run(service, match, evidence)
    assert result.error_category == 'invalid_agent_output'
    assert len(wire.calls) == 1


def test_duplicate_framework_call_blocked_at_http_boundary(enabled, wired, match, evidence, monkeypatch):
    from agent_framework import Agent
    original = Agent.run
    async def duplicate(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(Agent, 'run', duplicate)
    service, wire = wired
    result = run(service, match, evidence)
    assert result.error_category == 'duplicate_model_call_blocked'
    assert result.api_attempts == len(wire.calls) == 1
    assert json.loads(service.budget.path.read_text())['count'] == 1


@pytest.mark.parametrize('corruption', ['json', 'object', 'output'])
def test_corrupt_cache_fails_closed(enabled, wired, match, evidence, corruption):
    service, wire = wired
    first = run(service, match, evidence)
    path = service.cache.directory / f'{first.cache_key}.json'
    if corruption == 'json':
        path.write_text('{broken')
    elif corruption == 'object':
        path.write_text('[]')
    else:
        record = json.loads(path.read_text())
        record['result']['judge']['findings'][0]['event_ids'] = ['invented-event']
        path.write_text(json.dumps(record))
    result = run(service, match, evidence)
    assert result.error_category == 'cache_unavailable'
    assert len(wire.calls) == 4


def test_in_progress_tombstone_prevents_restart_generation(enabled, wired, match, evidence):
    service, wire = wired
    first = run(service, match, evidence)
    service.cache.write(first.cache_key, {'status': 'in_progress'})
    result = run(service, match, evidence)
    assert result.error_category == 'previous_trial_failed_or_incomplete'
    assert result.api_attempts == 0
    assert len(wire.calls) == 4


def test_cancelled_trial_leaves_tombstone(enabled, wired, match, evidence):
    service, wire = wired
    wire.delay = 1
    async def cancel():
        task = asyncio.create_task(service.analyze(match, evidence.case_id, 5400, allow_live=True))
        for _ in range(200):
            if wire.calls:
                break
            await asyncio.sleep(.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(cancel())
    result = run(service, match, evidence)
    assert result.error_category == 'previous_trial_failed_or_incomplete'
    assert len(wire.calls) == 1


def test_unrelated_event_cannot_be_used_for_a_fact(evidence):
    output = EvidenceSubmission.model_validate(submissions(evidence)['evidence'])
    unrelated = next(e.event_id for e in evidence.events if e.event_id not in output.interpretation.event_ids)
    output = output.model_copy(update={'interpretation': output.interpretation.model_copy(
        update={'event_ids': [unrelated]})})
    with pytest.raises(InvalidAgentOutput):
        validate_submission('evidence', output, evidence)


def test_cached_result_still_respects_live_kill_switch(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    run(service, match, evidence)
    monkeypatch.setenv('COURTROOM_LIVE_ENABLED', 'false')
    result = run(service, match, evidence)
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'live_disabled'
    assert len(wire.calls) == 4


def test_prepare_disabled_is_non_billable_fallback(wired, match, evidence):
    service, wire = wired
    result = asyncio.run(service.prepare(match, evidence.case_id, 5400))
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'live_disabled'
    assert result.api_attempts == 0
    assert wire.calls == []
    assert not service.budget.path.exists()


def test_prepare_uncached_cannot_execute_workflow_or_reserve_budget(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setitem(sys.modules, 'app.courtroom_workflow', None)
    def forbidden(*args, **kwargs):
        raise AssertionError('Preparation must not reserve model budget')
    monkeypatch.setattr(service.budget, 'reserve', forbidden)
    for _ in range(3):
        assert asyncio.run(service.prepare(match, evidence.case_id, 5400)) is None
    assert wire.calls == []
    assert not list(service.cache.directory.glob('*.json'))  # No tombstone consumed.
    assert not service.budget.path.exists()


def test_prepare_cached_reuses_validated_result_without_requests(enabled, wired, match, evidence):
    service, wire = wired
    original = run(service, match, evidence)
    ledger = service.budget.path.read_bytes()
    for _ in range(2):
        result = asyncio.run(service.prepare(match, evidence.case_id, 5400))
        assert result.source == 'cached_ai'
        assert result.api_attempts == 0
        assert result.original_api_attempts == 4
        assert result.judge == original.judge
    assert len(wire.calls) == 4
    assert service.budget.path.read_bytes() == ledger


@pytest.mark.parametrize('status', ['failed', 'in_progress', 'invalid_completed', 'busy'])
def test_prepare_does_not_regenerate_blocked_or_invalid_cache(enabled, wired, match, evidence, monkeypatch, status):
    service, wire = wired
    if status == 'busy':
        def busy(*args):
            raise courtroom.CacheBusy()
        monkeypatch.setattr(service.cache, 'claim', busy)
        category = 'trial_in_progress'
    else:
        monkeypatch.setattr(service.cache, 'read', lambda _: {'status': 'completed' if status == 'invalid_completed' else status})
        category = 'cache_unavailable' if status == 'invalid_completed' else 'previous_trial_failed_or_incomplete'
    result = asyncio.run(service.prepare(match, evidence.case_id, 5400))
    assert result.source == 'deterministic_fallback'
    assert result.error_category == category
    assert wire.calls == []
    assert not service.budget.path.exists()


def test_prepare_does_not_bypass_later_kill_switch(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    assert asyncio.run(service.prepare(match, evidence.case_id, 5400)) is None
    monkeypatch.setenv('COURTROOM_LIVE_ENABLED', 'false')
    result = run(service, match, evidence)
    assert result.error_category == 'live_disabled'
    assert wire.calls == []


def test_prepare_api_contract_rejects_live_opt_in_and_invalid_cutoffs(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setattr(main, 'trial_service', service)
    monkeypatch.setattr(main, 'require_match', lambda _: match)
    client = TestClient(main.app)
    path = f'/api/matches/{match.match_id}/cases/{evidence.case_id}/courtroom/prepare'
    assert client.post(path, json={'through_timestamp': 5400}).json() == {
        'status': 'confirmation_required', 'result': None}
    assert client.post(path, json={'through_timestamp': 5400, 'allow_live': True}).status_code == 422
    assert client.post(path, json={'through_timestamp': -1}).status_code == 422
    assert client.post(path, json={'through_timestamp': evidence.evidence_cutoff - 1}).status_code == 404
    assert wire.calls == []
    run(service, match, evidence)  # Four mocked framework requests, never Azure.
    response = client.post(path, json={'through_timestamp': 5400})
    assert response.status_code == 200
    assert response.json()['status'] == 'ready'
    assert response.json()['result']['source'] == 'cached_ai'
    assert response.json()['result']['api_attempts'] == 0
    assert len(wire.calls) == 4
    monkeypatch.setenv('COURTROOM_LIVE_ENABLED', 'false')
    response = client.post(path, json={'through_timestamp': 5400})
    assert response.json()['result']['error_category'] == 'live_disabled'
    assert len(wire.calls) == 4


@pytest.fixture(scope='module')
def varied_match():
    return generate_match(202)


@pytest.mark.parametrize('case_type', ['missed_opportunity', 'momentum_shift', 'substitution_impact'])
def test_all_existing_case_types_work_with_default_input_cap(enabled, varied_match, case_type, tmp_path):
    case = next(c for c in detect_cases(varied_match.events, through_timestamp=5400,
                match_id=varied_match.match_id) if c['case_type'] == case_type)
    evidence = build_evidence(varied_match, case['case_id'], 5400)
    wire = MockWire(evidence)
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        DailyRequestBudget(tmp_path / 'usage.json'), httpx.MockTransport(wire.handle))
    result = run(service, varied_match, evidence)
    assert result.source == 'live_ai', result.error_category
    assert result.api_attempts == 4
    assert result.evidence.case_type == case_type


def test_missing_framework_returns_safe_fallback(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setitem(sys.modules, 'app.courtroom_workflow', None)
    result = run(service, match, evidence)
    assert result.error_category == 'framework_unavailable'
    assert result.api_attempts == 0
    assert wire.calls == []


def test_invalid_configuration_blocks_requests(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setenv('COURTROOM_MAX_MODEL_CALLS', '100')
    result = run(service, match, evidence)
    assert result.error_category == 'configuration_unavailable'
    assert wire.calls == []


def test_statistic_value_is_exact_checked(evidence):
    output = submissions(evidence)['evidence']
    fact = next(f for f in evidence.facts if f.fact_id.endswith(':shots'))
    output['observations'] = [{'fact_id': fact.fact_id, 'value': str(int(fact.value) + 99)}]
    with pytest.raises(InvalidAgentOutput) as caught:
        validate_submission('evidence', EvidenceSubmission.model_validate(output), evidence)
    assert caught.value.reason == 'observation_value_mismatch'


def test_failed_provider_debug_logs_do_not_escape(enabled, wired, match, evidence, caplog):
    import logging
    service, wire = wired
    wire.fail_role, wire.fail_status = 'evidence', 401
    with caplog.at_level(logging.DEBUG):
        result = run(service, match, evidence)
    assert result.error_category == 'authentication_or_access_denied'
    assert 'fake-secret-never-output' not in caplog.text
    assert 'Authorization' not in caplog.text


@pytest.mark.parametrize('role', courtroom.ROLES)
def test_role_token_limits_and_shared_ceiling(enabled, wired, match, evidence, monkeypatch, role):
    service, wire = wired
    monkeypatch.setenv('COURTROOM_MAX_OUTPUT_TOKENS', '900')
    monkeypatch.setenv(f'COURTROOM_{role.upper()}_MAX_OUTPUT_TOKENS', '800')
    result = run(service, match, evidence)
    assert result.source == 'live_ai'
    for name, body in wire.calls:
        expected = 800 if name == role else min(900, courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[name])
        assert body['max_output_tokens'] == expected


def test_role_budget_change_invalidates_cache(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    first = run(service, match, evidence)
    monkeypatch.setenv('COURTROOM_JUDGE_MAX_OUTPUT_TOKENS', '1024')
    second = run(service, match, evidence)
    assert first.cache_key != second.cache_key
    assert len(wire.calls) == 8
    assert wire.calls[-1][1]['max_output_tokens'] == 1024


@pytest.mark.parametrize('name', ['COURTROOM_MAX_OUTPUT_TOKENS', *[
    f'COURTROOM_{role.upper()}_MAX_OUTPUT_TOKENS' for role in courtroom.ROLES]])
def test_unbounded_token_settings_rejected(enabled, wired, match, evidence, monkeypatch, name):
    service, wire = wired
    monkeypatch.setenv(name, '100000')
    result = run(service, match, evidence)
    assert result.error_category == 'configuration_unavailable'
    assert wire.calls == []


@pytest.mark.parametrize('invalid_citation', [False, True])
def test_registered_match_api_round_trip_and_repeated_requests(enabled, monkeypatch, tmp_path, invalid_citation):
    client = TestClient(main.app)
    # Use the actual match registry and case endpoints, without replacing
    # require_match or inventing a request-only controversy fixture.
    match_id = client.get('/api/matches').json()['matches'][1]['match_id']
    cases = client.get(f'/api/matches/{match_id}/cases?through_timestamp=5400').json()['cases']
    case = cases[0]
    evidence = build_evidence(get_match(match_id), case['case_id'], 5400)
    wire = MockWire(evidence)
    if invalid_citation:
        wire.outputs['evidence']['fact_ids'] = ['invented-fact']
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        DailyRequestBudget(tmp_path / 'usage.json'), httpx.MockTransport(wire.handle))
    monkeypatch.setattr(main, 'trial_service', service)
    path = f"/api/matches/{match_id}/cases/{case['case_id']}/courtroom"
    request = {'through_timestamp': 5400, 'allow_live': True}
    first = client.post(path, json=request)
    assert first.status_code == 200
    data = first.json()
    assert data['evidence'] == evidence.model_dump()
    assert not any(event['event_id'] == 'invented-event' for event in data['evidence']['events'])
    if invalid_citation:
        assert data['source'] == 'deterministic_fallback'
        assert data['evidence_agent'] is None
        assert data['error_category'] == 'invalid_agent_output'
        repeated = client.post(path, json=request).json()
        assert repeated['error_category'] == 'previous_trial_failed_or_incomplete'
        assert repeated['api_attempts'] == 0
        assert len(wire.calls) == 1
    else:
        assert data['source'] == 'live_ai'
        assert [item['agent'] for item in data['trace']] == list(courtroom.ROLES)
        assert [item['handoff_to'] for item in data['trace']] == ['prosecution', 'defense', 'judge', None]
        assert all(item['output_digest'] and item['input_digest'] for item in data['trace'])
        assert all(data[name] for name in ['evidence_agent', 'prosecution', 'defense', 'judge'])
        # Cached responses need no budget; a fresh case must still respect it.
        monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '0')
        cached = client.post(path, json=request).json()
        assert cached['source'] == 'cached_ai'
        assert cached['api_attempts'] == 0
        fresh_path = f"/api/matches/{match_id}/cases/{cases[1]['case_id']}/courtroom"
        limited = client.post(fresh_path, json=request).json()
        assert limited['error_category'] == 'daily_budget_unavailable'
        assert len(wire.calls) == 4
    deterministic = client.post(path, json={'through_timestamp': 5400}).json()
    assert deterministic['source'] == 'deterministic_fallback'
    assert deterministic['api_attempts'] == 0


@pytest.mark.parametrize('failure,stage,reason', [
    ('truncated', 'provider_response', 'response_not_completed'),
    ('refusal', 'provider_response', 'response_refusal'),
    ('envelope', 'provider_response', 'invalid_response_envelope'),
    ('schema', 'structured_output', 'schema_validation_failed'),
    ('unknown_event', 'structured_output', 'schema_validation_failed'),
    ('wrong_value', 'structured_output', 'schema_validation_failed'),
    ('numeric_prose', 'grounding_validation', 'numeric_reasoning'),
])
def test_failed_evidence_diagnostics_distinguish_same_browser_symptoms(
        enabled, wired, match, evidence, failure, stage, reason):
    """All can look like the first live failure. Its raw response was not retained;
    these reproduce the observable envelope, not an asserted provider payload.
    """
    service, wire = wired
    private = 'fake-secret-never-output'
    if failure == 'truncated':
        wire.response_status = 'incomplete'
        wire.response_transform = lambda body: {**body,
            'incomplete_details': {'reason': 'max_output_tokens', 'private': private},
            'usage': {'input_tokens': 12000, 'output_tokens': 768, 'total_tokens': 12768},
            'private': private}
    elif failure == 'refusal':
        def refusal(body):
            body['output'][0]['content'] = [{'type': 'refusal', 'refusal': private}]
            return body
        wire.response_transform = refusal
    elif failure == 'envelope':
        wire.response_transform = lambda _: [private]
    elif failure == 'schema':
        wire.outputs['evidence']['private'] = private  # Strict extra-field rejection.
    elif failure == 'unknown_event':
        wire.outputs['evidence']['event_ids'] = [private]
    elif failure == 'wrong_value':
        wire.outputs['evidence']['observations'] = [{'fact_id': 'invented-fact', 'value': private}]
    elif failure == 'numeric_prose':
        wire.outputs['evidence']['uncertainty'] = 'There are two plausible explanations.'
    result = run(service, match, evidence)
    assert result.source == 'deterministic_fallback'
    assert result.error_category == 'invalid_agent_output'
    assert result.http_status == 200
    assert result.api_attempts == len(wire.calls) == 1
    assert len(result.trace) == 1
    assert result.trace[0].agent == 'evidence'
    assert result.trace[0].handoff_to is None
    assert result.trace[0].output_digest is None
    record = json.loads((service.cache.directory / f'{result.cache_key}.json').read_text())
    assert record['http_status'] == 200
    assert record['trace'] == [entry.model_dump() for entry in result.trace]
    diagnostic = record['diagnostics']
    assert diagnostic['stage'] == stage
    assert diagnostic['reason'] == reason
    assert diagnostic['agent'] == 'evidence'
    assert diagnostic['max_output_tokens'] == 768
    assert 0 < diagnostic['payload_bytes'] < diagnostic['request_bytes'] <= 128000
    if failure == 'truncated':
        assert diagnostic['response_status'] == 'incomplete'
        assert diagnostic['incomplete_reason'] == 'max_output_tokens'
        assert diagnostic['output_tokens'] == 768
    serialized = json.dumps(record)
    assert private not in serialized
    assert private not in result.model_dump_json()
    assert 'prior_submissions' not in serialized
    assert 'interpretation' not in serialized
    assert json.loads(service.budget.path.read_text())['count'] == 1
    blocked = run(service, match, evidence)
    assert blocked.error_category == 'previous_trial_failed_or_incomplete'
    assert blocked.api_attempts == 0
    assert len(wire.calls) == 1


@pytest.mark.parametrize('status,category', [(401, 'authentication_or_access_denied'),
    ('dns', 'dns_failure'), ('timeout', 'timeout')])
def test_failure_diagnostics_do_not_confuse_network_access_and_validation(
        enabled, wired, match, evidence, status, category):
    service, wire = wired
    wire.fail_role, wire.fail_status = 'evidence', status
    result = run(service, match, evidence)
    record = json.loads((service.cache.directory / f'{result.cache_key}.json').read_text())
    assert result.error_category == category
    assert record['diagnostics']['stage'] == ('provider_response' if status == 401 else 'network')
    assert record['diagnostics']['reason'] == category
    assert record['http_status'] == (401 if status == 401 else None)
    assert len(wire.calls) == 1
    assert 'fake-secret' not in json.dumps(record)


def test_diagnostics_allowlist_untrusted_status_and_usage(enabled, wired, match, evidence):
    service, wire = wired
    private = 'fake-secret-never-output'
    wire.response_transform = lambda body: {**body, 'status': private,
        'incomplete_details': {'reason': private},
        'usage': {'input_tokens': private, 'output_tokens': -1, 'total_tokens': True}}
    result = run(service, match, evidence)
    record = json.loads((service.cache.directory / f'{result.cache_key}.json').read_text())
    assert record['diagnostics']['response_status'] == 'unknown'
    assert record['diagnostics']['incomplete_reason'] == 'unknown'
    assert not {'input_tokens', 'output_tokens', 'total_tokens'} & record['diagnostics'].keys()
    assert private not in json.dumps(record)


def test_legacy_failed_record_stays_blocked_without_rewriting(enabled, wired, match, evidence):
    service, wire = wired
    wire.outputs['evidence']['fact_ids'] = ['incorrect']
    first = run(service, match, evidence)
    legacy = {'status': 'failed', 'error_category': 'invalid_agent_output', 'api_attempts': 1}
    service.cache.write(first.cache_key, legacy)
    path = service.cache.directory / f'{first.cache_key}.json'
    before = path.read_bytes()
    repeat = run(service, match, evidence)
    assert repeat.error_category == 'previous_trial_failed_or_incomplete'
    assert repeat.api_attempts == 0
    assert path.read_bytes() == before
    assert len(wire.calls) == 1


def test_exact_live_case_input_matches_reported_handoff_without_inference():
    from app.courtroom_evidence import digest
    evidence = build_evidence(get_match('synthetic-101'),
        'synthetic-101-missed_opportunity-away-3218', 3308)
    assert digest({'evidence': evidence.model_dump(), 'prior_submissions': {}}).startswith('731856a6c450')
    assert len(evidence.events) == 59
    assert len(evidence.facts) == 33


@pytest.mark.parametrize('variant,expected_stage,expected_reason', [
    ('valid_numeric_observation', None, None),
    ('missing_trigger', 'grounding_validation', 'missing_trigger_reference'),
    ('future_event', 'grounding_validation', 'unknown_event_reference'),
    ('unsupported_citation', 'grounding_validation', 'event_not_supported_by_fact'),
    ('numeric_value_type', 'structured_output', 'schema_validation_failed'),
    ('missing_required_field', 'structured_output', 'schema_validation_failed'),
    ('malformed_json', 'structured_output', 'schema_validation_failed'),
    ('overlong_interpretation', 'structured_output', 'schema_validation_failed'),
    ('numeric_word_in_prose', 'grounding_validation', 'numeric_reasoning'),
])
def test_exact_case_canonical_evidence_validation_boundaries(
        variant, expected_stage, expected_reason):
    """Public records remain strictly validated after deterministic assembly.

    These canonical-value mutations are not fields the selection agent emits.
    They exercise unchanged schema and grounding boundaries independently.
    """
    match = get_match('synthetic-101')
    evidence = build_evidence(match, 'synthetic-101-missed_opportunity-away-3218', 3308)
    output = submissions(evidence)['evidence']
    if variant == 'valid_numeric_observation':
        fact = next(f for f in evidence.facts if f.event_ids and f.value.isdigit())
        output['observations'] = [{'fact_id': fact.fact_id, 'value': fact.value}]
        output['interpretation']['fact_ids'] = [fact.fact_id]
        output['interpretation']['event_ids'] = [fact.event_ids[0]]
    elif variant == 'missing_trigger':
        output['event_ids'] = [next(e.event_id for e in evidence.events
            if e.event_id not in evidence.trigger_event_ids)]
    elif variant == 'future_event':
        output['event_ids'].append(next(e['event_id'] for e in match.events
            if e['timestamp'] > evidence.evidence_cutoff))
    elif variant == 'unsupported_citation':
        trigger = evidence.trigger_event_ids[0]
        fact = next(f for f in evidence.facts if f.event_ids and trigger not in f.event_ids)
        output['interpretation']['fact_ids'] = [fact.fact_id]
        output['interpretation']['event_ids'] = [trigger]
    elif variant == 'numeric_value_type':
        output['observations'][0]['value'] = 7  # Contract requires an exact string.
    elif variant == 'missing_required_field':
        del output['uncertainty']
    elif variant == 'malformed_json':
        output = '{bad-json'
    elif variant == 'overlong_interpretation':
        output['interpretation']['interpretation'] = 'The recorded spell permits alternative readings. ' * 15
    else:
        output['uncertainty'] = 'The record leaves more than one plausible explanation.'
    from pydantic import ValidationError
    try:
        parsed = EvidenceSubmission.model_validate_json(output) if isinstance(output, str) else EvidenceSubmission.model_validate(output)
        validate_submission('evidence', parsed, evidence)
    except ValidationError:
        assert expected_stage == 'structured_output' and expected_reason == 'schema_validation_failed'
    except InvalidAgentOutput as exc:
        assert expected_stage == 'grounding_validation' and exc.reason == expected_reason
    else:
        assert expected_reason is None
        assert parsed.observations[0].value == fact.value


@pytest.mark.parametrize('uncertainty,expected_reason', [
    ('Alternative explanations remain plausible; causal influence is uncertain.', None),
    ('Causal influence cannot be proved from this record.', 'overconfident_reasoning'),
    ('There is more than one plausible explanation.', 'numeric_reasoning'),
])
def test_evidence_prompt_narrative_examples_match_unchanged_validator(
        enabled, wired, match, evidence, uncertainty, expected_reason):
    """The prompt's safe example passes; literal banned words still fail even
    in semantically cautious prose. Typed numeric facts remain permissible.
    """
    from app.courtroom_evidence import digest
    service, wire = wired
    fact = next(f for f in evidence.facts if f.event_ids and f.value.isdigit())
    contribution = wire.outputs['evidence']
    contribution['fact_ids'] = [fact.fact_id]
    contribution['uncertainty'] = uncertainty
    result = run(service, match, evidence)
    body = wire.calls[0][1]
    assert body['max_output_tokens'] == 768
    assert set(body['text']['format']['schema']['properties']) == {
        'fact_ids', 'explanation', 'uncertainty'}
    if expected_reason is None:
        assert uncertainty in body['instructions']  # Exact recommended wording.
        assert result.source == 'live_ai'
        assert result.evidence_agent.observations[0].value == fact.value
        assert len(wire.calls) == 4
        cached = run(service, match, evidence)
        assert cached.source == 'cached_ai' and cached.api_attempts == 0
        assert len(wire.calls) == 4
    else:
        assert result.source == 'deterministic_fallback'
        assert result.evidence_agent is None
        assert len(wire.calls) == 1
        record = json.loads((service.cache.directory / f'{result.cache_key}.json').read_text())
        assert record['diagnostics']['reason'] == expected_reason
        assert record['diagnostics']['prompt_digest'] == digest({'instructions': body['instructions']})
        assert body['instructions'] not in json.dumps(record)


def test_evidence_trigger_citation_must_be_top_level_even_if_interpretation_cites_it(evidence):
    output = submissions(evidence)['evidence']
    assert set(evidence.trigger_event_ids) <= set(output['interpretation']['event_ids'])
    output['event_ids'] = [next(event.event_id for event in evidence.events
        if event.event_id not in evidence.trigger_event_ids)]
    with pytest.raises(InvalidAgentOutput) as caught:
        validate_submission('evidence', EvidenceSubmission.model_validate(output), evidence)
    assert caught.value.reason == 'missing_trigger_reference'
