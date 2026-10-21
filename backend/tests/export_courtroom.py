"""Real framework → FastAPI fixtures for React tests; every socket is forbidden.

Only synthetic facts, fake credentials and temporary ledgers/caches are used.
This script never loads .env or reads/writes the project's runtime records.
"""
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app import courtroom, main
from app.courtroom_evidence import build_evidence
from app.synthetic_match import get_match
from test_courtroom import MockWire


def forbidden(*args, **kwargs):
    raise AssertionError('Cross-stack rehearsal forbids real sockets')


def export():
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'OPENAI_', 'COURTROOM_'))}
    environment.update(FOUNDRY_LIVE_ENABLED='true', COURTROOM_LIVE_ENABLED='true',
        AZURE_OPENAI_ENDPOINT='https://offline-fixture.services.ai.azure.com',
        AZURE_OPENAI_API_KEY='fake-offline-key', AZURE_OPENAI_DEPLOYMENT='gpt-4.1-mini')
    with patch.dict(os.environ, environment, clear=True), patch.object(socket.socket, 'connect', forbidden), TemporaryDirectory() as directory:
        root = Path(directory)
        match = get_match('synthetic-303')
        evidence = build_evidence(match, 'synthetic-303-missed_opportunity-home-2412', 2502)
        wire = MockWire(evidence)
        wire.outputs['evidence']['fact_ids'] = [fact.fact_id for fact in evidence.facts[:3]]
        wire.outputs['evidence']['explanation'] = 'The recorded incident and surrounding pattern frame the competing interpretations.'
        wire.outputs['prosecution']['points'][0]['interpretation'] = 'The recorded missed opportunity supports a cautious reading of the allegation.'
        wire.outputs['defense']['points'][0]['interpretation'] = 'The missed opportunity leaves alternative explanations for the alleged influence.'
        wire.outputs['judge']['result'] = 'prosecution_supported'
        wire.outputs['judge']['findings'][0]['interpretation'] = 'The allegation is better supported as an interpretation, while causal influence remains uncertain.'
        service = courtroom.TrialService(courtroom.TrialCache(root / 'cache'),
            courtroom.DailyRequestBudget(root / 'usage'), httpx.MockTransport(wire.handle))
        path = f'/api/matches/{match.match_id}/cases/{evidence.case_id}/courtroom'
        with patch.object(main, 'trial_service', service), TestClient(main.app) as client:
            preparation = client.post(path + '/prepare', json={'through_timestamp': 2502}).json()
            assert preparation == {'status': 'confirmation_required', 'result': None} and not wire.calls
            live = client.post(path, json={'through_timestamp': 2502, 'allow_live': True}).json()
            assert live['source'] == 'live_ai' and live['api_attempts'] == 4
            assert len(live['evidence_agent']['observations']) == 3
            assert all(entry['status'] == 'completed' for entry in live['trace'])
            cached = client.post(path + '/prepare', json={'through_timestamp': 2502}).json()['result']
            assert cached['source'] == 'cached_ai' and cached['api_attempts'] == 0 and len(wire.calls) == 4
            fixture = {'match': client.get(f'/api/matches/{match.match_id}').json(),
                'events': client.get(f'/api/matches/{match.match_id}/events').json()['events'],
                'case_id': evidence.case_id, 'cutoff': 2502, 'preparation': preparation,
                'live': live, 'cached': cached,
                'snapshots': {str(t): {'timestamp': t,
                    'state': client.get(f'/api/matches/{match.match_id}/state?through_timestamp={t}').json()['state'],
                    'cases': client.get(f'/api/matches/{match.match_id}/cases?through_timestamp={t}').json()['cases']}
                    for t in (0, 2502)}}
            wire.outputs['defense']['points'][0]['fact_ids'] = ['unauthorized-offline-reference']
            failed_service = courtroom.TrialService(courtroom.TrialCache(root / 'failed-cache'),
                courtroom.DailyRequestBudget(root / 'failed-usage'), httpx.MockTransport(wire.handle))
            with patch.object(main, 'trial_service', failed_service):
                fixture['fallback'] = client.post(path, json={'through_timestamp': 2502, 'allow_live': True}).json()
                assert fixture['fallback']['source'] == 'deterministic_fallback'
                assert fixture['fallback']['api_attempts'] == 3
                assert fixture['fallback']['trace'][-1]['agent'] == 'defense'
            return fixture


if __name__ == '__main__':
    json.dump(export(), sys.stdout)
