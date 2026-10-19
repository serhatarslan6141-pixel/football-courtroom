"""Fresh fixed allocation; exact CLI/framework path, fake network and records."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json

import httpx
import pytest
from agent_framework import Agent, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient

from app import courtroom, diagnose_evidence as diagnostic
from app.courtroom_evidence import build_evidence, digest
from app.synthetic_match import get_match
from test_courtroom import MockWire, assert_azure_evidence_schema, evidence_fact_choices
from test_evidence_diagnostic import isolated, wired as original_wired, run


@pytest.fixture
def wired(monkeypatch, tmp_path):
    args = original_wired.__wrapped__(monkeypatch, tmp_path)
    allocation = diagnostic.SCHEMA_DIAGNOSTIC
    evidence = build_evidence(get_match(allocation.match_id), allocation.case_id, allocation.cutoff)
    wire = MockWire(evidence)
    wire.response_transform = lambda body: {**body, 'usage': {
        'input_tokens': 18500, 'output_tokens': 256, 'total_tokens': 18756}}
    args.update(wire=wire, transport=httpx.MockTransport(wire.handle), allocation=allocation,
                trial_cache=courtroom.TrialCache(tmp_path / 'courtroom'))
    args['budget'].path.write_text(json.dumps({
        'day': datetime.now(timezone.utc).date().isoformat(), 'count': 6}))
    return args


def test_new_default_cli_is_disabled_and_does_not_load_config(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError('Default command cannot enter live configuration')
    monkeypatch.setattr(diagnostic, '_live_environment', forbidden)
    assert diagnostic.main(['--schema-check']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['diagnostic'] == diagnostic.SCHEMA_DIAGNOSTIC.diagnostic_id
    assert report['status'] == 'disabled' and report['api_attempts'] == 0


def test_exact_new_live_cli_with_fake_config_and_mock_transport(
        wired, monkeypatch, tmp_path, capsys):
    # Exercise --live ONLY with a temporary fake .env and injected MockTransport.
    monkeypatch.setattr(diagnostic, 'ROOT', tmp_path)
    (tmp_path / '.env').write_text('AZURE_OPENAI_ENDPOINT=https://test-resource.services.ai.azure.com\n'
        'AZURE_OPENAI_API_KEY=fake-secret-never-output\nAZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini\n'
        'FOUNDRY_LIVE_ENABLED=false\nCOURTROOM_LIVE_ENABLED=false\nFOUNDRY_DAILY_REQUEST_CAP=10\n')
    created = []
    original_agent = OpenAIChatClient.as_agent
    def as_agent(self, *args, **kwargs):
        created.append(kwargs['name'])
        return original_agent(self, *args, **kwargs)
    def forbidden(*args, **kwargs):
        raise AssertionError('No full trial or handoff may execute')
    monkeypatch.setattr(OpenAIChatClient, 'as_agent', as_agent)
    monkeypatch.setattr(WorkflowBuilder, 'add_edge', forbidden)
    monkeypatch.setattr(courtroom.TrialService, 'analyze', forbidden)
    monkeypatch.setattr('app.courtroom_workflow.execute_trial', forbidden)
    original_runner = diagnostic.run_diagnostic
    async def intercepted(settings, config, **kwargs):
        assert settings.timeout == 120 and settings.retries == 0
        assert kwargs['allocation'] == diagnostic.SCHEMA_DIAGNOSTIC
        assert config.output_tokens_for('evidence') == 768
        return await original_runner(settings, config, **kwargs,
            **{k: wired[k] for k in ('cache', 'budget', 'transport', 'trial_cache')})
    monkeypatch.setattr(diagnostic, 'run_diagnostic', intercepted)
    assert diagnostic.main(['--schema-check', '--live']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'completed' and report['http_status'] == 200
    assert report['usage_before'] == 6 and report['effective_daily_cap'] == 7
    assert report['api_attempts'] == len(wired['wire'].calls) == 1
    assert report['input_digest'] == diagnostic.SCHEMA_DIAGNOSTIC.input_digest
    assert report['diagnostics']['input_tokens'] == 18500
    assert report['diagnostics']['output_tokens'] == 256
    assert report['diagnostics']['response_status'] == 'completed'
    assert report['diagnostics']['stage'] == 'grounding_validation'
    assert created == ['FootballCourtroom_evidence']
    assert report['trace'][0]['handoff_to'] is None
    body = wired['wire'].calls[0][1]
    assert body['max_output_tokens'] == 768 and body['store'] is False
    assert body['text']['format']['strict'] is True
    schema = body['text']['format']['schema']
    assert_azure_evidence_schema(schema)
    a = diagnostic.SCHEMA_DIAGNOSTIC
    evidence = build_evidence(get_match(a.match_id), a.case_id, a.cutoff)
    expected = [f.fact_id for f in evidence.facts]
    assert evidence_fact_choices(schema) == expected
    assert all(4465 <= e.timestamp <= 4645 for e in evidence.events)
    assert 'fake-secret' not in json.dumps(report)
    assert diagnostic.main(['--schema-check', '--live']) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'blocked_previous_diagnostic'
    assert len(wired['wire'].calls) == 1


@pytest.mark.parametrize('failure,reason', [
    ('observation_fact', 'unknown_fact_reference'), ('interpretation_fact', 'unknown_fact_reference'),
    ('event', 'schema_validation_failed'), ('length', 'schema_validation_failed'),
    ('malformed', 'schema_validation_failed'), ('truncated', 'response_not_completed'),
    ('dns', 'dns_failure'), ('timeout', 'timeout'),
])
def test_new_allocation_rejection_captures_diagnostics_and_blocks_repeat(wired, failure, reason):
    wire = wired['wire']
    if failure == 'observation_fact':
        wire.outputs['evidence']['fact_ids'] = ['fake-secret-never-output']
    elif failure == 'interpretation_fact':
        wire.outputs['evidence']['fact_ids'] = ['fake-secret-never-output']
    elif failure == 'event':
        wire.outputs['evidence']['event_ids'] = ['fake-secret-never-output']
    elif failure == 'length':
        wire.outputs['evidence']['uncertainty'] = 'x' * 501
    elif failure == 'malformed':
        wire.outputs['evidence'] = '{fake-secret-never-output'
    elif failure == 'truncated':
        wire.response_status = 'incomplete'
        wire.response_transform = lambda body: {**body, 'incomplete_details': {'reason': 'max_output_tokens'},
            'usage': {'input_tokens': 18500, 'output_tokens': 768, 'total_tokens': 19268}}
    else:
        wire.fail_role, wire.fail_status = 'evidence', failure
    report = run(wired, allow_live=True)
    assert report['status'] == 'failed'
    assert report['diagnostics']['reason'] == reason
    assert report['api_attempts'] == len(wire.calls) == 1
    assert report['trace'][0]['handoff_to'] is None
    if failure in ('observation_fact', 'interpretation_fact'):
        assert report['diagnostics']['field'] == 'selection.fact_ids'
    if failure == 'truncated':
        assert report['diagnostics']['incomplete_reason'] == 'max_output_tokens'
        assert report['diagnostics']['output_tokens'] == 768
    assert 'fake-secret' not in json.dumps(report)
    assert run(wired, allow_live=True)['status'] == 'blocked_previous_diagnostic'
    assert len(wire.calls) == 1
    assert json.loads(wired['budget'].path.read_text())['count'] == 7


@pytest.mark.parametrize('status', ['failed', 'in_progress', 'completed'])
def test_new_allocation_does_not_bypass_existing_case_record(wired, status):
    a = diagnostic.SCHEMA_DIAGNOSTIC
    evidence = build_evidence(get_match(a.match_id), a.case_id, a.cutoff)
    cache = wired['trial_cache']
    key = courtroom.trial_cache_key(evidence, wired['settings'], wired['config'])
    with cache.claim(key):
        cache.write(key, {'status': status, 'api_attempts': 1})
    before = (cache.directory / f'{key}.json').read_bytes()
    assert run(wired, allow_live=True)['status'] == 'blocked_existing_trial'
    assert not wired['wire'].calls
    assert (cache.directory / f'{key}.json').read_bytes() == before
    assert json.loads(wired['budget'].path.read_text())['count'] == 6


def test_original_diagnostic_record_is_never_reused_or_rewritten(wired):
    old = build_evidence(get_match(diagnostic.MATCH_ID), diagnostic.CASE_ID, diagnostic.CUTOFF)
    key = digest({'diagnostic': diagnostic.DIAGNOSTIC_ID, 'evidence': old.model_dump()})
    with wired['cache'].claim(key):
        wired['cache'].write(key, {'status': 'completed', 'api_attempts': 1})
    before = (wired['cache'].directory / f'{key}.json').read_bytes()
    assert run(wired, allow_live=True)['status'] == 'completed'
    assert (wired['cache'].directory / f'{key}.json').read_bytes() == before
    assert len(list(wired['cache'].directory.glob('*.json'))) == 2


def test_new_allocation_budget_exhaustion_does_not_reset_or_consume(wired):
    wired['settings'] = replace(wired['settings'], daily_cap=6)
    before = wired['budget'].path.read_bytes()
    assert run(wired, allow_live=True)['status'] == 'daily_budget_exhausted'
    assert wired['budget'].path.read_bytes() == before
    assert not wired['wire'].calls
    assert not list(wired['cache'].directory.glob('*.json'))


def test_new_allocation_blocks_second_sdk_send(wired, monkeypatch):
    original = Agent.run
    async def duplicate(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(Agent, 'run', duplicate)
    report = run(wired, allow_live=True)
    assert report['error_category'] == 'duplicate_model_call_blocked'
    assert report['api_attempts'] == len(wired['wire'].calls) == 1
    assert json.loads(wired['budget'].path.read_text())['count'] == 7


def test_new_allocation_concurrent_calls_share_single_attempt(wired):
    wired['wire'].delay = .05
    async def parallel():
        args = {k: v for k, v in wired.items() if k != 'wire'}
        return await asyncio.gather(*(diagnostic.run_diagnostic(**args, allow_live=True) for _ in range(2)))
    reports = asyncio.run(parallel())
    assert sorted(r['status'] for r in reports) == ['blocked_concurrent_diagnostic', 'completed']
    assert len(wired['wire'].calls) == 1
