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
from app.synthetic_match import generate_match

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
        self.fail_role = None
        self.fail_status = None
        self.on_call = None
        self.delay = 0
        self.response_status = 'completed'

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
        return httpx.Response(200, json={
            'id': f'resp_{role}', 'object': 'response', 'created_at': 0,
            'model': 'gpt-4.1-mini', 'status': self.response_status,
            'output': [{'type': 'message', 'id': f'msg_{role}', 'role': 'assistant',
                        'status': 'completed', 'content': [{'type': 'output_text',
                        'text': text, 'annotations': []}]}],
        })


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
        assert body['max_output_tokens'] == 256
        assert body['store'] is False
        assert not body.get('tools')
        assert body['text']['format']['type'] == 'json_schema'
        assert body['text']['format']['strict'] is True
        payload = user_payload(body)
        assert payload['evidence'] == evidence.model_dump()
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
        output['event_ids'].append('invented-event')
    elif corruption == 'fact':
        output['observations'][0]['fact_id'] = 'invented-fact'
    elif corruption == 'statistic':
        output['observations'][0]['value'] = '999'
    elif corruption == 'numeric_prose':
        output['interpretation']['interpretation'] = 'The team scored ninety goals in the spell.'
    elif corruption == 'certainty':
        output['interpretation']['interpretation'] = 'The incident definitely changed the match outcome.'
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
    monkeypatch.setenv('FOUNDRY_MAX_OUTPUT_TOKENS', '128')
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


def test_global_token_limit_and_input_size_limit(enabled, wired, match, evidence, monkeypatch):
    service, wire = wired
    monkeypatch.setenv('FOUNDRY_MAX_OUTPUT_TOKENS', '32')
    result = run(service, match, evidence)
    assert result.source == 'live_ai'
    assert all(body['max_output_tokens'] == 32 for _, body in wire.calls)
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


def test_statistic_value_is_exact_checked(enabled, wired, match, evidence):
    service, wire = wired
    fact = next(f for f in evidence.facts if f.fact_id.endswith(':shots'))
    wire.outputs['evidence']['observations'] = [{'fact_id': fact.fact_id, 'value': str(int(fact.value) + 99)}]
    result = run(service, match, evidence)
    assert result.error_category == 'invalid_agent_output'
    assert len(wire.calls) == 1


def test_failed_provider_debug_logs_do_not_escape(enabled, wired, match, evidence, caplog):
    import logging
    service, wire = wired
    wire.fail_role, wire.fail_status = 'evidence', 401
    with caplog.at_level(logging.DEBUG):
        result = run(service, match, evidence)
    assert result.error_category == 'authentication_or_access_denied'
    assert 'fake-secret-never-output' not in caplog.text
    assert 'Authorization' not in caplog.text
