"""Production artifacts and direct API behavior; sockets and AI are forbidden."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from app.courtroom_evidence import build_evidence
from app.public_courtroom import CachedOnlyTrialService
from app.public_mode import cors_origins
from app.synthetic_match import get_match
from app.trial_library import TrialLibrary

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_deployment', ROOT / 'scripts/prepare-deployment.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_public_context_contains_only_safe_runtime_and_validated_trials(tmp_path):
    output = tmp_path / 'context'
    report = packager.prepare(output)
    assert report['public_trials'] >= 1
    paths = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    expected = {'Dockerfile', '.dockerignore', 'backend/requirements-public.txt', 'backend/app/PUBLIC_ONLY'}
    expected.update('backend/app/' + name for name in packager.PUBLIC_MODULES)
    assert paths - expected == {
        p.relative_to(ROOT).as_posix() for p in (ROOT / 'backend/data/courtroom-trials').glob('*.json')}
    assert not any(part in p for p in paths for part in ('.env', '.logs', '__pycache__', '.git/', '.venv'))
    assert not any(p.endswith(name) for p in paths for name in (
        'foundry.py', 'courtroom_workflow.py', 'batch_trials.py', 'diagnose_evidence.py', 'check_foundry.py'))
    requirements = (output / 'backend/requirements-public.txt').read_text()
    assert 'openai==' not in requirements and 'agent-framework' not in requirements
    assert (output / 'backend/app/PUBLIC_ONLY').exists()
    with pytest.raises(ValueError):
        packager.prepare(output)


@pytest.mark.parametrize('fake_live', [False, True])
def test_public_artifact_ignores_live_flags_and_direct_requests(tmp_path, fake_live):
    output = tmp_path / 'context'
    packager.prepare(output)
    # A new interpreter imports only the shipped modules, with network disabled.
    # The image marker wins even over FOOTBALL_PUBLIC_MODE=false + fake keys.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('AZURE_', 'OPENAI_', 'FOUNDRY_', 'COURTROOM_', 'FOOTBALL_'))}
    environment.update(PYTHONPATH=str(output / 'backend'), FOOTBALL_PUBLIC_MODE='false',
        CORS_ORIGINS='https://demo.azurestaticapps.net',
        FOUNDRY_LIVE_ENABLED=str(fake_live).lower(), COURTROOM_LIVE_ENABLED=str(fake_live).lower(),
        AZURE_OPENAI_API_KEY='fake-never-use', AZURE_OPENAI_ENDPOINT='https://fake.services.ai.azure.com')
    code = '''
import asyncio, importlib.util, json, socket, sys
def forbidden(*args, **kwargs): raise AssertionError('Outbound networking forbidden')
socket.socket.connect = forbidden
socket.getaddrinfo = forbidden
from fastapi.testclient import TestClient
from app.main import app, PUBLIC_ONLY
assert PUBLIC_ONLY
assert importlib.util.find_spec('app.foundry') is None
assert importlib.util.find_spec('app.courtroom_workflow') is None
assert importlib.util.find_spec('app.batch_trials') is None
from app.case_detection import detect_cases
from app.synthetic_match import get_match
from app.courtroom_evidence import build_evidence
with TestClient(app) as client:
 assert client.get('/health').json()['ai_mode'] == 'cached_only'
 catalog = client.get('/api/matches').json()
 assert catalog['count'] == 3
 for match_id in ['synthetic-101', 'synthetic-202', 'synthetic-303']:
  assert client.get('/api/matches/' + match_id + '/events').json()['count'] > 0
  assert client.get('/api/matches/' + match_id + '/state?through_timestamp=5400').status_code == 200
  cases = client.get('/api/matches/' + match_id + '/cases?through_timestamp=5400').json()['cases']
  for case in cases:
   e = build_evidence(get_match(match_id), case['case_id'], 5400)
   path = '/api/matches/' + match_id + '/cases/' + e.case_id + '/courtroom'
   preparation = client.post(path+'/prepare', json={'through_timestamp':5400}).json()
   assert preparation['status'] == 'ready'
   for allow_live in (False, True):
    data = client.post(path, json={'through_timestamp':5400, 'allow_live':allow_live}).json()
    assert data['source'] in ['cached_ai', 'deterministic_fallback']
    assert data['api_attempts'] == 0
    assert data['source'] == preparation['result']['source']
    if data['source'] == 'cached_ai':
     assert len(data['trace']) == 4 and data['original_api_attempts'] == 4
   assert client.post(path+'/prepare',json={'through_timestamp':e.evidence_cutoff-1}).status_code==404
 origin = 'https://demo.azurestaticapps.net'
 headers = {'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'}
 preflight = client.options('/api/matches',headers=headers)
 assert preflight.status_code == 200 and preflight.headers['access-control-allow-origin'] == origin
 headers['Origin'] = 'https://untrusted.example'
 assert client.options('/api/matches',headers=headers).status_code == 400
 generated = client.post('/api/matches')
 assert generated.status_code == 201
 assert client.get('/api/matches/'+generated.json()['match_id']).status_code==200
 assert client.post('/check-foundry',json={'live':True}).status_code==404
assert not any(name in sys.modules for name in ['app.foundry','app.courtroom','app.courtroom_workflow','agent_framework','openai'])
from pathlib import Path
assert not Path('.logs').exists()
print('public artifact API, CORS and no-AI checks passed')
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=output, env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'checks passed' in result.stdout


def test_public_missing_and_corrupt_cache_cannot_generate(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Public cache cannot access network')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    library = TrialLibrary(tmp_path)
    service = CachedOnlyTrialService(library)
    match = get_match('synthetic-101')
    case = 'synthetic-101-missed_opportunity-away-3218'
    evidence = build_evidence(match, case, 5400)
    missing = asyncio.run(service.analyze(match, case, 5400, allow_live=True))
    assert missing.source == 'deterministic_fallback' and missing.api_attempts == 0
    library.path_for(evidence).write_text('{"corrupt":true}')
    before = library.path_for(evidence).read_bytes()
    corrupt = asyncio.run(service.prepare(match, case, 5400))
    assert corrupt.error_category == 'cache_unavailable' and corrupt.api_attempts == 0
    assert library.path_for(evidence).read_bytes() == before


@pytest.mark.parametrize('origin', ['*', 'null', 'https://example.com/path', 'https://user:pass@example.com',
                                    'https://example.com/', 'https://*.azurestaticapps.net'])
def test_cors_rejects_unsafe_or_ambiguous_origins(monkeypatch, origin):
    monkeypatch.setenv('CORS_ORIGINS', origin)
    with pytest.raises(ValueError):
        cors_origins()
