"""Real framework, fake transport, temporary records; never read project .env."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
import socket

import httpx
import pytest

pytest.importorskip('agent_framework')
from agent_framework import Agent, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from app import diagnose_evidence as diagnostic
from app import courtroom
from app.courtroom_evidence import build_evidence
from app.foundry import FoundrySettings
from app.synthetic_match import get_match
from test_courtroom import MockWire, assert_azure_evidence_schema, evidence_fact_choices


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for name in list(os.environ):
        if name.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'OPENAI_', 'COURTROOM_', 'EVIDENCE_DIAGNOSTIC_')):
            monkeypatch.delenv(name)
    def network_forbidden(*args, **kwargs):
        raise AssertionError('Real sockets forbidden in Evidence diagnostic tests')
    monkeypatch.setattr(socket.socket, 'connect', network_forbidden)


@pytest.fixture
def wired(monkeypatch, tmp_path):
    for name, value in {
        'FOUNDRY_LIVE_ENABLED': 'true', 'COURTROOM_LIVE_ENABLED': 'false',
        'EVIDENCE_DIAGNOSTIC_LIVE_ENABLED': 'true',
        'AZURE_OPENAI_ENDPOINT': 'https://test-resource.services.ai.azure.com',
        'AZURE_OPENAI_API_KEY': 'fake-secret-never-output',
        'AZURE_OPENAI_DEPLOYMENT': 'gpt-4.1-mini',
        'FOUNDRY_TIMEOUT_SECONDS': '120', 'FOUNDRY_MAX_RETRIES': '2',
    }.items():
        monkeypatch.setenv(name, value)
    evidence = build_evidence(get_match(diagnostic.MATCH_ID), diagnostic.CASE_ID, diagnostic.CUTOFF)
    wire = MockWire(evidence)
    return {
        'settings': FoundrySettings.from_env(), 'config': courtroom.TrialConfig.from_env(),
        'cache': courtroom.TrialCache(tmp_path / 'evidence-diagnostics'),
        'budget': courtroom.DailyRequestBudget(tmp_path / 'usage.json'),
        'transport': httpx.MockTransport(wire.handle), 'wire': wire,
    }


def run(wired, **kwargs):
    args = {name: value for name, value in wired.items() if name != 'wire'}
    args.update(kwargs)
    return asyncio.run(diagnostic.run_diagnostic(**args))


def test_default_cli_does_not_load_env_write_records_or_request(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError('Default CLI must not enter live setup')
    monkeypatch.setattr(diagnostic, '_live_environment', forbidden)
    monkeypatch.setattr(diagnostic, 'run_diagnostic', forbidden)
    assert diagnostic.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'disabled'
    assert report['api_attempts'] == 0
    assert report['max_api_attempts'] == 1


def test_changed_canonical_evidence_blocks_before_records_or_budget(wired, monkeypatch):
    original = diagnostic.build_evidence
    monkeypatch.setattr(diagnostic, 'build_evidence', lambda *args: original(*args).model_copy(
        update={'allegation': 'Different evidence must not buy another diagnostic'}))
    assert run(wired, allow_live=True)['status'] == 'evidence_changed'
    assert wired['wire'].calls == []
    assert not wired['cache'].directory.exists()
    assert not wired['budget'].path.exists()


def test_missing_saved_config_cannot_fall_back_to_inherited_credentials(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(diagnostic, 'ROOT', tmp_path)
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://test-resource.services.ai.azure.com')
    monkeypatch.setenv('AZURE_OPENAI_API_KEY', 'fake-secret-never-output')
    def forbidden(*args, **kwargs):
        raise AssertionError('Missing root .env must block the runner')
    monkeypatch.setattr(diagnostic, 'run_diagnostic', forbidden)
    assert diagnostic.main(['--live']) == 1
    result = capsys.readouterr().out
    assert json.loads(result)['status'] == 'configuration_or_execution_unavailable'
    assert 'fake-secret' not in result


@pytest.mark.parametrize('gate', ['argument', 'diagnostic_switch', 'full_trial_enabled'])
def test_permission_gates_fail_closed(wired, monkeypatch, gate):
    if gate == 'diagnostic_switch':
        monkeypatch.setenv('EVIDENCE_DIAGNOSTIC_LIVE_ENABLED', 'false')
    if gate == 'full_trial_enabled':
        monkeypatch.setenv('COURTROOM_LIVE_ENABLED', 'true')
    result = run(wired, allow_live=gate != 'argument')
    assert result['status'] == 'disabled'
    assert wired['wire'].calls == []
    assert not wired['budget'].path.exists()
    assert not wired['cache'].directory.exists()


def test_success_only_constructs_and_runs_evidence_with_no_edges(wired, monkeypatch, tmp_path):
    created = []
    original = OpenAIChatClient.as_agent
    def as_agent(self, *args, **kwargs):
        created.append(kwargs['name'])
        return original(self, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError('Diagnostic must not call a full trial or create graph edges')
    monkeypatch.setattr(OpenAIChatClient, 'as_agent', as_agent)
    monkeypatch.setattr(WorkflowBuilder, 'add_edge', forbidden)
    monkeypatch.setattr(courtroom.TrialService, 'analyze', forbidden)
    monkeypatch.setattr('app.courtroom_workflow.execute_trial', forbidden)
    original_record = tmp_path / 'courtroom' / 'original-failed.json'
    original_record.parent.mkdir()
    original_record.write_text('{"status":"failed","api_attempts":1}')
    before = original_record.read_bytes()
    today = datetime.now(timezone.utc).date().isoformat()
    wired['budget'].path.write_text(json.dumps({'day': today, 'count': 4}))
    report = run(wired, allow_live=True)
    assert report['status'] == 'completed'
    assert report['api_attempts'] == 1
    assert report['http_status'] == 200
    assert report['input_digest'].startswith('731856a6c450')
    assert report['usage_before'] == 4 and report['effective_daily_cap'] == 5
    assert created == ['FootballCourtroom_evidence']
    assert [name for name, _ in wired['wire'].calls] == ['evidence']
    assert len(report['trace']) == 1 and report['trace'][0]['handoff_to'] is None
    assert report['trace'][0]['status'] == 'completed' and report['trace'][0]['output_digest']
    body = wired['wire'].calls[0][1]
    assert body['model'] == 'gpt-4.1-mini' and body['max_output_tokens'] == 768
    assert body['store'] is False and not body.get('tools')
    schema = body['text']['format']['schema']
    assert_azure_evidence_schema(schema)
    evidence = build_evidence(get_match(diagnostic.MATCH_ID), diagnostic.CASE_ID, diagnostic.CUTOFF)
    expected = [fact.fact_id for fact in evidence.facts]
    assert evidence_fact_choices(schema) == expected
    assert body['text']['format']['strict'] is True
    assert report['diagnostics']['max_output_tokens'] == 768
    assert len(report['diagnostics']['prompt_digest']) == 64
    records = list(wired['cache'].directory.glob('*.json'))
    assert len(records) == 1
    assert json.loads(records[0].read_text()) == report
    serialized = records[0].read_text()
    assert 'fake-secret' not in serialized and body['instructions'] not in serialized
    assert wired['wire'].outputs['evidence']['uncertainty'] not in serialized
    assert original_record.read_bytes() == before
    assert json.loads(wired['budget'].path.read_text()) == {'day': today, 'count': 5}
    repeated = run(wired, allow_live=True)
    assert repeated['status'] == 'blocked_previous_diagnostic' and repeated['api_attempts'] == 0
    assert len(wired['wire'].calls) == 1
    assert records[0].read_text() == serialized
    # Changes to prompt/config must not silently create a second diagnostic.
    repeated = run(wired, allow_live=True, config=replace(wired['config'], output_tokens=900))
    assert repeated['status'] == 'blocked_previous_diagnostic'


@pytest.mark.parametrize('failure,category,reason', [
    ('malformed', 'invalid_agent_output', 'schema_validation_failed'),
    ('citation', 'invalid_agent_output', 'unknown_fact_reference'),
    ('truncated', 'invalid_agent_output', 'response_not_completed'),
    ('dns', 'dns_failure', 'dns_failure'),
    ('timeout', 'timeout', 'timeout'),
    (401, 'authentication_or_access_denied', 'authentication_or_access_denied'),
    (429, 'rate_limited', 'rate_limited'),
    (503, 'provider_unavailable', 'provider_unavailable'),
])
def test_failures_capture_only_sanitized_metadata_and_block_repeats(wired, failure, category, reason):
    wire = wired['wire']
    if failure == 'malformed':
        wire.outputs['evidence'] = '{fake-secret-never-output'
    elif failure == 'citation':
        wire.outputs['evidence']['fact_ids'] = ['fake-secret-never-output']
    elif failure == 'truncated':
        wire.response_status = 'incomplete'
        wire.response_transform = lambda body: {**body,
            'incomplete_details': {'reason': 'max_output_tokens'},
            'usage': {'input_tokens': 12345, 'output_tokens': 768, 'total_tokens': 13113}}
    else:
        wire.fail_role, wire.fail_status = 'evidence', failure
    report = run(wired, allow_live=True)
    assert report['status'] == 'failed'
    assert report['error_category'] == category and report['diagnostics']['reason'] == reason
    assert report['api_attempts'] == len(wire.calls) == 1
    assert [name for name, _ in wire.calls] == ['evidence']
    assert report['trace'][0]['output_digest'] is None
    assert report['trace'][0]['handoff_to'] is None
    if failure == 'truncated':
        assert report['http_status'] == 200
        assert report['diagnostics']['incomplete_reason'] == 'max_output_tokens'
        assert report['diagnostics']['output_tokens'] == 768
    assert 'fake-secret' not in json.dumps(report)
    assert json.loads(wired['budget'].path.read_text())['count'] == 1
    assert run(wired, allow_live=True)['status'] == 'blocked_previous_diagnostic'
    assert len(wire.calls) == 1


def test_duplicate_sdk_call_cannot_exceed_one_attempt_or_reservation(wired, monkeypatch):
    original = Agent.run
    async def duplicate(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(Agent, 'run', duplicate)
    report = run(wired, allow_live=True)
    assert report['status'] == 'failed'
    assert report['error_category'] == 'duplicate_model_call_blocked'
    assert report['api_attempts'] == len(wired['wire'].calls) == 1
    assert json.loads(wired['budget'].path.read_text())['count'] == 1


def test_concurrent_diagnostic_cannot_consume_another_request(wired):
    wired['wire'].delay = .05
    async def parallel():
        args = {name: value for name, value in wired.items() if name != 'wire'}
        return await asyncio.gather(*(diagnostic.run_diagnostic(**args, allow_live=True) for _ in range(2)))
    reports = asyncio.run(parallel())
    assert sorted(r['status'] for r in reports) == ['blocked_concurrent_diagnostic', 'completed']
    assert len(wired['wire'].calls) == 1


def test_cancellation_preserves_tombstone_and_blocks_a_restart(wired):
    wired['wire'].delay = 2
    async def cancel():
        args = {name: value for name, value in wired.items() if name != 'wire'}
        task = asyncio.create_task(diagnostic.run_diagnostic(**args, allow_live=True))
        for _ in range(100):
            if wired['wire'].calls:
                break
            await asyncio.sleep(.005)
        assert len(wired['wire'].calls) == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(cancel())
    assert run(wired, allow_live=True)['status'] == 'blocked_previous_diagnostic'
    assert len(wired['wire'].calls) == 1
    record = json.loads(next(wired['cache'].directory.glob('*.json')).read_text())
    assert record['status'] == 'in_progress'


def test_bounded_timeout_never_retries(wired):
    wired['wire'].delay = 2
    report = run(wired, allow_live=True, settings=replace(wired['settings'], timeout=1))
    assert report['status'] == 'failed' and report['error_category'] == 'timeout'
    assert len(wired['wire'].calls) == 1
    assert run(wired, allow_live=True)['status'] == 'blocked_previous_diagnostic'


def test_existing_daily_budget_can_block_diagnostic_without_being_reset(wired, monkeypatch):
    today = datetime.now(timezone.utc).date().isoformat()
    wired['budget'].path.write_text(json.dumps({'day': today, 'count': 10}))
    before = wired['budget'].path.read_bytes()
    report = run(wired, allow_live=True)
    assert report['error_category'] == 'daily_budget_unavailable'
    assert report['api_attempts'] == 0 and wired['wire'].calls == []
    assert wired['budget'].path.read_bytes() == before


@pytest.mark.parametrize('raise_error', [False, True])
def test_live_cli_loads_only_private_process_config_and_restores_it(monkeypatch, tmp_path, capsys, raise_error):
    # This tests the --live parser branch with fake .env and a fake runner only.
    # It does not execute the live command against the project configuration.
    monkeypatch.setattr(diagnostic, 'ROOT', tmp_path)
    (tmp_path / '.env').write_text('AZURE_OPENAI_ENDPOINT=https://test-resource.services.ai.azure.com\n'
        'AZURE_OPENAI_API_KEY=fake-secret-never-output\nAZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini\n'
        'FOUNDRY_LIVE_ENABLED=false\nCOURTROOM_LIVE_ENABLED=false\nFOUNDRY_MAX_RETRIES=2\n')
    before = dict(os.environ)
    async def fake_run(settings, config, **kwargs):
        assert kwargs['allow_live'] is True
        assert settings.timeout == 120 and settings.retries == 0
        assert os.environ['COURTROOM_LIVE_ENABLED'] == 'false'
        assert os.environ['EVIDENCE_DIAGNOSTIC_LIVE_ENABLED'] == 'true'
        if raise_error:
            raise RuntimeError('fake-secret-never-output')
        return diagnostic._summary('completed', api_attempts=1)
    monkeypatch.setattr(diagnostic, 'run_diagnostic', fake_run)
    assert diagnostic.main(['--live']) == (1 if raise_error else 0)
    assert 'fake-secret' not in capsys.readouterr().out
    assert dict(os.environ) == before
