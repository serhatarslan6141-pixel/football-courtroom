"""Bounded production and deployment playback; all inference is MockTransport."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest

from app import batch_trials as batch, courtroom, main
from app.courtroom_evidence import InvalidAgentOutput
from app.foundry import DailyRequestBudget, FoundrySettings
from app.trial_library import TrialLibrary, validate_completed
from test_courtroom import MockWire, enabled, isolated, assert_azure_evidence_schema
from test_courtroom import resolve_schema_node, user_payload


@pytest.fixture
def setup(enabled, monkeypatch, tmp_path):
    monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '100')
    monkeypatch.setenv('FOUNDRY_TIMEOUT_SECONDS', '120')
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '0')
    settings, config = FoundrySettings.from_env(), courtroom.TrialConfig.from_env()
    cases = batch.built_in_cases()
    wires = {e.case_id: MockWire(e) for e in cases}
    calls = []

    async def handle(request):
        body = json.loads(request.content)
        serialized = json.dumps(body)
        case_id = next(e.case_id for e in cases if e.case_id in serialized)
        calls.append(case_id)
        return await wires[case_id].handle(request)

    return {'settings': settings, 'config': config, 'cases': cases, 'wires': wires, 'calls': calls,
            'options': {'cache': courtroom.TrialCache(tmp_path / 'cache'),
                        'library': TrialLibrary(tmp_path / 'library'),
                        'diagnostics': courtroom.TrialCache(tmp_path / 'diagnostics'),
                        'batches': courtroom.TrialCache(tmp_path / 'batches'),
                        'daily': DailyRequestBudget(tmp_path / 'usage.json'),
                        'transport': httpx.MockTransport(handle)}}


def run(s, *, batch_id='test-batch', max_requests=4, cost='100', case_ids=None, allow_live=True):
    return asyncio.run(batch.run_batch(s['settings'], s['config'], batch.BatchLimits(max_requests, 100, cost),
                                      batch_id, allow_live=allow_live, case_ids=case_ids, **s['options']))


def manifest(directory):
    return {str(p): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def test_entire_catalog_all_types_four_handoffs_azure_schemas_and_public_api(setup, monkeypatch, tmp_path):
    s = setup
    report = run(s, max_requests=44)
    assert report['status'] == 'completed'
    assert len(report['results']) == 11 and len(s['calls']) == 44
    assert report['batch_reservations'] == report['daily_usage_after'] == 44
    assert {e.case_type for e in s['cases']} == {'missed_opportunity', 'momentum_shift', 'substitution_impact'}
    assert all(row['status'] == 'published' for row in report['results'])
    for wire in s['wires'].values():
        assert [role for role, _ in wire.calls] == list(courtroom.ROLES)
        for role, body in wire.calls:
            assert_azure_evidence_schema(body['text']['format']['schema'])
            assert body['text']['format']['strict'] is True
            assert body['max_output_tokens'] == s['config'].output_tokens_for(role)
    before = manifest(tmp_path)
    # A restart on a deployment without .env, keys, live flags, a daily ledger,
    # framework imports or working network still serves all published cases.
    for key in list(courtroom.os.environ):
        if key.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'COURTROOM_')):
            monkeypatch.delenv(key)
    public = courtroom.TrialService(cache=courtroom.TrialCache(tmp_path / 'unused-cache'),
                                   library=TrialLibrary(s['options']['library'].directory))
    monkeypatch.setattr(main, 'trial_service', public)
    with TestClient(main.app) as client:
        for e in s['cases']:
            path = f'/api/matches/{e.match_id}/cases/{e.case_id}/courtroom'
            for suffix, body in (('/prepare', {'through_timestamp': e.evidence_cutoff}),
                                 ('', {'through_timestamp': 5400}),
                                 ('', {'through_timestamp': 5400, 'allow_live': True})):
                response = client.post(path + suffix, json=body)
                assert response.status_code == 200
                result = response.json()['result'] if suffix else response.json()
                assert result['source'] == 'cached_ai' and result['api_attempts'] == 0
                assert result['original_api_attempts'] == 4
                assert len(result['trace']) == 4 and result['evidence']['case_id'] == e.case_id
            assert client.post(path + '/prepare', json={'through_timestamp': e.evidence_cutoff - 1}).status_code == 404
    assert manifest(tmp_path) == before and len(s['calls']) == 44


def test_default_disabled_and_missing_public_case_never_sends(setup, monkeypatch):
    s = setup
    assert run(s, allow_live=False) == {'status': 'disabled'}
    assert not s['calls'] and not s['options']['batches'].directory.exists()
    monkeypatch.setenv('FOUNDRY_LIVE_ENABLED', 'false')
    service = courtroom.TrialService(library=s['options']['library'])
    e = s['cases'][0]
    result = asyncio.run(service.analyze(batch.get_match(e.match_id), e.case_id, 5400, allow_live=True))
    assert result.source == 'deterministic_fallback' and result.api_attempts == 0


def test_resume_preserves_first_success_and_never_raises_original_cap(setup):
    s = setup
    first = run(s)
    assert first['status'] == 'allowance_exhausted' and len(s['calls']) == 4
    snapshot = manifest(s['options']['library'].directory)
    again = run(s)
    assert again['status'] == 'allowance_exhausted' and len(s['calls']) == 4
    assert manifest(s['options']['library'].directory) == snapshot
    assert run(s, max_requests=8)['status'] == 'batch_identity_or_day_changed'
    second = run(s, batch_id='next-approved-batch')
    assert second['batch_reservations'] == 4 and len(s['calls']) == 8
    assert all(p.read_bytes() == data for path, data in snapshot.items() for p in [Path(path)])


@pytest.mark.parametrize('failure', ['schema', 'grounding', 'network', 'truncated'])
def test_failure_stops_no_retry_then_resume_skips_failed_case(setup, failure):
    s = setup
    e = s['cases'][0]
    wire = s['wires'][e.case_id]
    if failure == 'schema':
        wire.outputs['prosecution'] = {'extra': 'never log raw output'}
    elif failure == 'grounding':
        wire.outputs['prosecution']['points'][0]['fact_ids'] = ['unauthorized']
    elif failure == 'network':
        wire.fail_role, wire.fail_status = 'prosecution', 'timeout'
    else:
        wire.response_transform = lambda payload: {**payload, 'status': 'incomplete',
            'incomplete_details': {'reason': 'max_output_tokens'}} if payload['id'] == 'resp_prosecution' else payload
    report = run(s, max_requests=8)
    assert report['status'] == 'trial_failed_stop'
    assert len(s['calls']) == report['batch_reservations'] == 2
    assert [role for role, _ in wire.calls] == ['evidence', 'prosecution']
    assert not list(s['options']['library'].directory.glob('*.json'))
    key = courtroom.trial_cache_key(e, s['settings'], s['config'])
    failed = s['options']['cache'].read(key)
    assert failed['status'] == 'failed' and failed['case_id'] == e.case_id
    before = (s['options']['cache'].directory / (key + '.json')).read_bytes()
    resumed = run(s, max_requests=8)
    assert resumed['batch_reservations'] == 6 and len(wire.calls) == 2
    assert (s['options']['cache'].directory / (key + '.json')).read_bytes() == before


def test_interrupted_trial_is_blocked_without_reset_and_can_publish_after_interruption(setup):
    s = setup
    e = s['cases'][0]
    cache = s['options']['cache']
    key = courtroom.trial_cache_key(e, s['settings'], s['config'])
    cache.directory.mkdir()
    cache.write(key, {'status': 'in_progress'})  # Legacy tombstone, no metadata.
    before = (cache.directory / (key + '.json')).read_bytes()
    result = run(s)
    assert result['results'][0]['status'] == 'blocked' and len(s['calls']) == 4
    assert (cache.directory / (key + '.json')).read_bytes() == before
    # Simulate interruption after private completion but before publication.
    second = s['cases'][1]
    library = s['options']['library']
    completed = library.read(second)
    library.path_for(second).unlink()  # Temporary test fixture only.
    calls = len(s['calls'])
    resumed = run(s)
    assert any(row['status'] == 'published_existing' for row in resumed['results'])
    assert library.read(second) == completed and len(s['calls']) == calls


def test_diagnostic_failure_blocks_full_generation_and_unmapped_records_stop_batch(setup):
    s = setup
    diagnostics = s['options']['diagnostics']
    diagnostics.directory.mkdir()
    diagnostics.write('diagnostic', {'case_id': s['cases'][0].case_id, 'status': 'failed', 'api_attempts': 1})
    result = run(s)
    assert result['results'][0]['status'] == 'blocked'
    assert result['results'][0]['reason'] == 'previous_diagnostic_failed_or_incomplete'
    s['options']['cache'].write('unknown-legacy-identity', {'status': 'failed'})
    calls = len(s['calls'])
    assert run(s)['status'] == 'audit_blocked' and len(s['calls']) == calls


@pytest.mark.parametrize('condition', ['cost', 'daily', 'rollover'])
def test_cost_daily_and_utc_boundaries_block_before_first_request(setup, condition):
    s = setup
    if condition == 'daily':
        day, _ = batch._usage_today(s['options']['daily'].path)
        s['options']['daily'].path.write_text(json.dumps({'day': day, 'count': 98}))
    if condition == 'rollover':
        assert run(s)['batch_reservations'] == 4
        record = s['options']['batches'].read('test-batch')
        record['utc_day'] = '2000-01-01'
        s['options']['batches'].write('test-batch', record)
        calls = len(s['calls'])
        assert run(s)['status'] == 'batch_identity_or_day_changed'
        assert len(s['calls']) == calls
    else:
        result = run(s, cost='0.000001' if condition == 'cost' else '100')
        assert result['status'] == 'allowance_exhausted' and not s['calls']


def test_send_budget_independently_blocks_fifth_call_and_cost_overrun(setup):
    s = setup
    store = s['options']['batches']
    store.directory.mkdir()
    today, _ = batch._usage_today(s['options']['daily'].path)
    record = {'utc_day': today, 'reservations': 0, 'reserved_estimated_usd': '0'}
    limits = batch.BatchLimits(4, 100, '100')
    budget = batch.BatchBudget(store, 'guard', record, s['options']['daily'], limits, s['config'])
    with store.claim('guard'):
        for _ in range(4):
            budget.reserve(100)
        with pytest.raises(batch.FoundryUnavailable):
            budget.reserve(100)
        assert batch._usage_today(s['options']['daily'].path)[1] == 4
        record['reservations'] = 0  # Separate temporary cost-exhaustion scenario.
        record['reserved_estimated_usd'] = '100'
        with pytest.raises(batch.FoundryUnavailable):
            budget.reserve(100)
        assert batch._usage_today(s['options']['daily'].path)[1] == 4


def test_concurrent_batch_and_same_case_locks_make_no_duplicate_sends(setup):
    s = setup
    with s['options']['batches'].claim('test-batch'):
        assert run(s)['status'] == 'batch_in_progress'
        assert not s['calls']
    e = s['cases'][0]
    key = courtroom.trial_cache_key(e, s['settings'], s['config'])
    with s['options']['cache'].claim(key):
        assert run(s)['status'] == 'trial_failed_stop'
        assert not s['calls']


@pytest.mark.parametrize('damage', ['future_evidence', 'unknown_fact', 'partial_trace', 'fallback', 'fingerprint'])
def test_corrupt_published_content_fails_closed_without_inference(setup, damage):
    s = setup
    e = s['cases'][0]
    assert run(s, case_ids=[e.case_id])['status'] == 'completed'
    path = s['options']['library'].path_for(e)
    artifact = json.loads(path.read_text())
    result = artifact['result']
    if damage == 'future_evidence':
        result['evidence']['evidence_cutoff'] += 1
    elif damage == 'unknown_fact':
        result['evidence_agent']['observations'][0]['fact_id'] = 'unauthorized'
    elif damage == 'partial_trace':
        result['trace'].pop()
    elif damage == 'fallback':
        result['source'] = 'deterministic_fallback'
    else:
        result['trace'][0]['output_digest'] = 'a' * 64
    path.write_text(json.dumps(artifact))
    original = path.read_bytes()
    service = courtroom.TrialService(transport=s['options']['transport'], library=s['options']['library'])
    response = asyncio.run(service.prepare(batch.get_match(e.match_id), e.case_id, 5400))
    assert response.source == 'deterministic_fallback' and response.api_attempts == 0
    with pytest.raises((ValueError, InvalidAgentOutput)):
        s['options']['library'].publish(validate_completed(run_result(s, e), e))
    assert path.read_bytes() == original and len(s['calls']) == 4


def run_result(s, e):
    return s['options']['cache'].read(courtroom.trial_cache_key(e, s['settings'], s['config']))['result']


def test_publication_is_immutable_and_portable(setup):
    s = setup
    e = s['cases'][0]
    run(s, case_ids=[e.case_id])
    library = s['options']['library']
    before = library.path_for(e).read_bytes()
    assert library.publish(library.read(e)) is False
    assert library.path_for(e).read_bytes() == before
    assert b'fake-secret-never-output' not in before and b'test-resource' not in before


def test_audit_has_no_writes_and_never_counts_evidence_only_as_trial(setup, tmp_path):
    s = setup
    diagnostics = s['options']['diagnostics']
    diagnostics.directory.mkdir()
    diagnostics.write('evidence-only', {'case_id': s['cases'][0].case_id, 'status': 'completed', 'api_attempts': 1})
    before = manifest(tmp_path)
    report = batch.audit(s['settings'], s['config'], s['options']['cache'], s['options']['library'], diagnostics)
    assert report['counts']['missing'] == 11 and not report['issues']
    assert manifest(tmp_path) == before and not s['calls']
    assert FoundrySettings.from_env(require_live=False).deployment == 'gpt-4.1-mini'


def test_cli_generate_without_live_never_loads_configuration(monkeypatch, capsys):
    def forbidden(**kwargs):
        raise AssertionError('Configuration must remain unread')
    monkeypatch.setattr(batch, 'configuration', forbidden)
    assert batch.main(['generate']) == 0
    assert json.loads(capsys.readouterr().out) == {'status': 'disabled', 'api_attempts': 0}


@pytest.mark.parametrize('reject', [False, True])
def test_first_controlled_batch_exact_case_and_ten_attempt_daily_cap(setup, monkeypatch, reject):
    """Exact proposed live allocation; fake credentials and temporary state only."""
    s = setup
    case_id = 'synthetic-303-momentum_shift-home-583'
    e = next(e for e in s['cases'] if e.case_id == case_id)
    assert e.case_type == 'momentum_shift' and e.evidence_cutoff == 763
    assert len(e.events) == 119 and all(event.timestamp <= 763 for event in e.events)
    monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '10')
    settings = replace(s['settings'], daily_cap=10)
    limits = batch.BatchLimits(4, 10, '0.30')
    today, _ = batch._usage_today(s['options']['daily'].path)
    s['options']['daily'].path.write_text(json.dumps({'day': today, 'count': 6}))
    wire = s['wires'][case_id]
    trigger = next(f for f in e.facts if f.fact_id.startswith('trigger:'))
    context = [f for f in e.facts if f.event_ids and f.fact_id != trigger.fact_id][:2]
    wire.outputs['evidence']['fact_ids'] = [f.fact_id for f in [trigger, *context]]
    if reject:
        wire.outputs['prosecution']['points'][0]['fact_ids'] = ['unauthorized']

    def generate():
        return asyncio.run(batch.run_batch(settings, s['config'], limits, 'builtin-coverage-01',
            allow_live=True, case_ids=[case_id], **s['options']))

    report = generate()
    if reject:
        assert report['status'] == 'trial_failed_stop'
        assert report['batch_reservations'] == 2 and report['daily_usage_after'] == 8
        assert s['options']['library'].read(e) is None
        again = generate()
        assert again['results'][0]['status'] == 'blocked' and len(wire.calls) == 2
        return
    assert report['status'] == 'completed' and report['daily_usage_after'] == 10
    assert report['batch_reservations'] == 4 and report['daily_remaining'] == 0
    result = s['options']['library'].read(e)
    validate_completed(result, e)
    assert len(result.evidence_agent.observations) == 3
    assert [role for role, _ in wire.calls] == list(courtroom.ROLES)
    authorized = [f.fact_id for f in e.facts]
    for index, (role, body) in enumerate(wire.calls):
        schema = body['text']['format']['schema']
        assert_azure_evidence_schema(schema)
        if role == 'evidence':
            ids = schema['properties']['fact_ids']['items']['enum']
        else:
            key = 'findings' if role == 'judge' else 'points'
            point = resolve_schema_node(schema, schema['properties'][key]['items'])
            ids = point['properties']['fact_ids']['items']['enum']
            assert 'event_ids' not in point['properties']
        assert ids == authorized
        assert list(user_payload(body)['prior_submissions']) == list(courtroom.ROLES[:index])
        assert body['max_output_tokens'] == s['config'].output_tokens_for(role)
        assert len(json.dumps(body).encode()) < s['config'].max_input_bytes
    private_before = manifest(s['options']['cache'].directory)
    library_before = manifest(s['options']['library'].directory)
    ledger_before = s['options']['daily'].path.read_bytes()
    assert generate()['results'][0]['status'] == 'published'  # Skip, no fifth call.
    assert len(wire.calls) == 4
    for key in list(courtroom.os.environ):
        if key.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'COURTROOM_')):
            monkeypatch.delenv(key)
    # Simulate a restarted public backend with no credentials and no ledger.
    public = courtroom.TrialService(library=TrialLibrary(s['options']['library'].directory))
    monkeypatch.setattr(main, 'trial_service', public)
    path = f'/api/matches/{e.match_id}/cases/{case_id}/courtroom'
    with TestClient(main.app) as client:
        response = client.post(path + '/prepare', json={'through_timestamp': 763}).json()
        assert response['status'] == 'ready' and response['result']['source'] == 'cached_ai'
        assert response['result']['api_attempts'] == 0
        assert response['result']['judge'] == result.judge.model_dump()
    assert s['options']['daily'].path.read_bytes() == ledger_before
    assert manifest(s['options']['cache'].directory) == private_before
    assert manifest(s['options']['library'].directory) == library_before
    assert len(wire.calls) == 4
