"""All model requests use MockTransport. No Azure credentials or network."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import httpx
import pytest

from app import check_foundry, foundry
from app.main import app


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for name in list(foundry.os.environ):
        if name.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'OPENAI_')):
            monkeypatch.delenv(name)
    # Even if a developer has real .env credentials, tests never read them.
    monkeypatch.setattr(check_foundry, 'load_dotenv', lambda *a, **kw: None)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv('FOUNDRY_LIVE_ENABLED', 'true')
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://test-resource.openai.azure.com')
    monkeypatch.setenv('AZURE_OPENAI_API_KEY', 'fake-secret-never-output')


@pytest.fixture
def wire(monkeypatch):
    calls = []
    outcomes = []

    def handler(request):
        calls.append(request)
        status, body = outcomes.pop(0) if outcomes else (200, {
            'id': 'resp_test', 'object': 'response', 'created_at': 0,
            'model': 'gpt-4.1-mini', 'status': 'completed',
            'output': [{'type': 'message', 'id': 'msg_test', 'role': 'assistant',
                        'status': 'completed', 'content': [{'type': 'output_text',
                        'text': 'FOOTBALL_COURTROOM_OK', 'annotations': []}]}],
        })
        if status == 'timeout':
            raise httpx.ReadTimeout('fake-secret-never-output', request=request)
        return httpx.Response(status, json=body)

    real_client = httpx.AsyncClient
    class MockClient(real_client):
        def __init__(self, **kw):
            super().__init__(transport=httpx.MockTransport(handler), **kw)
    monkeypatch.setattr(foundry.httpx, 'AsyncClient', MockClient)
    return calls, outcomes


def probe(tmp_path, **kwargs):
    budget = foundry.DailyRequestBudget(tmp_path / 'usage.json')
    asyncio.run(foundry.FoundryConnection(budget).test_connection(**kwargs))


def test_disabled_missing_credentials_no_network(tmp_path, monkeypatch, wire):
    with pytest.raises(foundry.FoundryUnavailable, match='disabled'):
        probe(tmp_path)
    monkeypatch.setenv('FOUNDRY_LIVE_ENABLED', 'true')
    with pytest.raises(foundry.FoundryUnavailable, match='missing'):
        probe(tmp_path)
    assert wire[0] == []
    assert not (tmp_path / 'usage.json').exists()


@pytest.mark.parametrize('endpoint', [
    'http://test.openai.azure.com', 'https://evil.example',
    'https://test.openai.azure.com/api/projects/foo',
    'https://test.openai.azure.com?key=secret',
    'https://user:secret@test.openai.azure.com',
    'https://test.openai.azure.com:bad',
])
def test_invalid_endpoint(enabled, monkeypatch, tmp_path, wire, endpoint):
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', endpoint)
    with pytest.raises(foundry.FoundryUnavailable):
        probe(tmp_path)
    assert wire[0] == []


@pytest.mark.parametrize('name,value', [
    ('FOUNDRY_MAX_OUTPUT_TOKENS', '100000'), ('FOUNDRY_MAX_OUTPUT_TOKENS', '0'),
    ('FOUNDRY_DAILY_REQUEST_CAP', '-1'), ('FOUNDRY_TIMEOUT_SECONDS', 'NaN'),
    ('FOUNDRY_MAX_RETRIES', '3'), ('AZURE_OPENAI_DEPLOYMENT', ''),
])
def test_invalid_limits(enabled, monkeypatch, tmp_path, wire, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(foundry.FoundryUnavailable):
        probe(tmp_path)
    assert not wire[0]


@pytest.mark.parametrize('suffix', ['', '/openai/v1/'])
def test_real_sdk_payload_success(enabled, monkeypatch, tmp_path, wire, suffix):
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://test.services.ai.azure.com' + suffix)
    probe(tmp_path)
    request, = wire[0]
    assert str(request.url) == 'https://test.services.ai.azure.com/openai/v1/responses'
    assert json.loads(request.content) == {
        'model': 'gpt-4.1-mini', 'input': foundry.PROBE_INPUT,
        'max_output_tokens': 32, 'store': False,
    }
    assert json.loads((tmp_path / 'usage.json').read_text())['count'] == 1
    assert 'fake-secret' not in repr(foundry.FoundrySettings.from_env())


@pytest.mark.parametrize('status,match', [(401, 'authentication'), (403, 'authentication'),
    (404, 'unavailable'), (400, 'rejected'), (429, 'rate limited'), (503, 'unavailable'),
    ('timeout', 'timed out')])
def test_failures_sanitized_and_counted(enabled, tmp_path, wire, status, match):
    wire[1].append((status, {'error': {'message': 'fake-secret-never-output'}}))
    with pytest.raises(foundry.FoundryUnavailable, match=match) as exc:
        probe(tmp_path)
    assert 'fake-secret' not in str(exc.value)
    assert len(wire[0]) == 1
    assert json.loads((tmp_path / 'usage.json').read_text())['count'] == 1


def test_bounded_retry_and_each_attempt_counted(enabled, monkeypatch, tmp_path, wire):
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '1')
    wire[1].append((503, {}))
    probe(tmp_path)
    assert len(wire[0]) == 2
    assert json.loads((tmp_path / 'usage.json').read_text())['count'] == 2


def test_retry_cannot_exceed_budget(enabled, monkeypatch, tmp_path, wire):
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '2')
    monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '1')
    wire[1].append((503, {}))
    with pytest.raises(foundry.FoundryUnavailable, match='cap reached'):
        probe(tmp_path)
    assert len(wire[0]) == 1


def test_kill_switch_rechecked_between_retries(enabled, monkeypatch, tmp_path, wire):
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '1')
    wire[1].append((503, {}))
    async def disable(_):
        monkeypatch.setenv('FOUNDRY_LIVE_ENABLED', 'false')
    monkeypatch.setattr(foundry.asyncio, 'sleep', disable)
    with pytest.raises(foundry.FoundryUnavailable, match='disabled'):
        probe(tmp_path)
    assert len(wire[0]) == 1


@pytest.mark.parametrize('body', [
    {'status': 'completed', 'output': []},
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant',
        'content': [{'type': 'output_text', 'text': 'not our expected response'}]}]},
])
def test_invalid_model_output(enabled, tmp_path, wire, body):
    wire[1].append((200, body))
    with pytest.raises(foundry.FoundryUnavailable):
        probe(tmp_path)


def test_budget_survives_new_instances_and_rolls_over(tmp_path):
    path = tmp_path / 'usage.json'
    foundry.DailyRequestBudget(path).reserve(1)
    with pytest.raises(foundry.FoundryUnavailable, match='cap reached'):
        foundry.DailyRequestBudget(path).reserve(1)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    path.write_text(json.dumps({'day': yesterday, 'count': 10}))
    foundry.DailyRequestBudget(path).reserve(1)
    assert json.loads(path.read_text())['count'] == 1


def test_budget_concurrency(tmp_path):
    path = tmp_path / 'usage.json'
    def reserve(_):
        try:
            foundry.DailyRequestBudget(path).reserve(3)
            return True
        except foundry.FoundryUnavailable:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(20))) <= 3
    assert json.loads(path.read_text())['count'] <= 3


def test_corrupt_or_unwritable_ledger_fails_closed(tmp_path):
    path = tmp_path / 'usage.json'
    path.write_text('broken')
    with pytest.raises(foundry.FoundryUnavailable, match='ledger unavailable'):
        foundry.DailyRequestBudget(path).reserve(10)
    with pytest.raises(foundry.FoundryUnavailable, match='ledger unavailable'):
        foundry.DailyRequestBudget(tmp_path).reserve(10)


def test_zero_cap_blocks(enabled, monkeypatch, tmp_path, wire):
    monkeypatch.setenv('FOUNDRY_DAILY_REQUEST_CAP', '0')
    with pytest.raises(foundry.FoundryUnavailable, match='cap reached'):
        probe(tmp_path)
    assert not wire[0]


def test_cli_opt_in_and_single_attempt(enabled, monkeypatch, tmp_path, wire, capsys):
    monkeypatch.setattr(check_foundry, 'FoundryConnection', lambda: foundry.FoundryConnection(
        foundry.DailyRequestBudget(tmp_path / 'usage.json')))
    assert check_foundry.main([]) == 0
    assert wire[0] == []
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '2')
    wire[1].append((503, {'error': {'message': 'fake-secret-never-output'}}))
    assert check_foundry.main(['--live']) == 1
    assert len(wire[0]) == 1
    assert 'fake-secret' not in capsys.readouterr().out
    assert check_foundry.main(['--live']) == 0
    assert 'verified' in capsys.readouterr().out


def test_existing_app_ignores_absent_or_broken_azure(wire, monkeypatch):
    client = TestClient(app)
    for endpoint in ('', 'https://invalid.example'):
        monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', endpoint)
        assert client.get('/health').status_code == 200
        fixtures = client.get('/api/matches').json()['matches']
        match_id = fixtures[0]['match_id']
        cases = client.get(f'/api/matches/{match_id}/cases?through_timestamp=5400')
        assert cases.status_code == 200
        assert cases.json()['cases']
    assert wire[0] == []


def test_whole_request_deadline(enabled, monkeypatch, tmp_path, wire):
    # Simulate a transport coroutine that ignores socket timeout. The outer
    # wait_for deadline still bounds the attempt without making a wire request.
    async def timeout(awaitable, *, timeout):
        assert timeout == 10
        awaitable.close()
        raise asyncio.TimeoutError()
    monkeypatch.setattr(foundry.asyncio, 'wait_for', timeout)
    with pytest.raises(foundry.FoundryUnavailable, match='timed out'):
        probe(tmp_path)
    assert not wire[0]


def test_retry_exhaustion_is_bounded(enabled, monkeypatch, tmp_path, wire):
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '1')
    wire[1].extend([(503, {}), (503, {})])
    with pytest.raises(foundry.FoundryUnavailable, match='unavailable'):
        probe(tmp_path)
    assert len(wire[0]) == 2


def test_auth_failure_never_retried(enabled, monkeypatch, tmp_path, wire):
    monkeypatch.setenv('FOUNDRY_MAX_RETRIES', '2')
    wire[1].append((401, {}))
    with pytest.raises(foundry.FoundryUnavailable, match='authentication'):
        probe(tmp_path)
    assert len(wire[0]) == 1
