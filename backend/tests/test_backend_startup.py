"""Exercise real dev launchers and a local Uvicorn process, never Azure."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip('agent_framework', reason='Launcher checks need the Phase 4B environment')
pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason='Dev launchers require Python 3.12+')
ROOT = Path(__file__).resolve().parents[2]


def safe_environment():
    # No credentials or live switches are inherited by the child server.
    result = {name: value for name, value in os.environ.items()
              if not name.startswith(('AZURE_', 'OPENAI_', 'FOUNDRY_', 'COURTROOM_', 'FOOTBALL_'))}
    result.update(FOUNDRY_LIVE_ENABLED='false', COURTROOM_LIVE_ENABLED='false',
                  FOOTBALL_BACKEND_PYTHON=sys.executable)
    return result


def executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


def test_default_dev_launcher_prefers_framework_environment(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    for name in ['backend-python.sh', 'start-dev.sh']:
        shutil.copyfile(ROOT / 'scripts' / name, scripts / name)
    expected = executable(tmp_path / '.venv/phase4b/bin/python',
        '#!/usr/bin/env bash\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    executable(tmp_path / '.venv/bin/python', '#!/usr/bin/env bash\nexit 99\n')
    environment = safe_environment()
    environment.pop('FOOTBALL_BACKEND_PYTHON')
    result = subprocess.run(['bash', str(scripts / 'start-dev.sh'), '--check'],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert str(expected) in result.stdout
    assert 'Python 3.' in result.stdout
    assert not (tmp_path / '.logs').exists()  # --check starts no services.


@pytest.mark.parametrize('problem', ['old_python', 'missing_dependencies'])
def test_explicit_invalid_interpreter_is_rejected(tmp_path, problem):
    # Simulate the legacy version or missing packages while using a real Python
    # to execute the launcher's validation snippet. No package install occurs.
    setup = ('import sys; sys.version_info=(3,9,6); ' if problem == 'old_python'
             else "import importlib.metadata; importlib.metadata.version=lambda _: 'missing'; ")
    wrapper = executable(tmp_path / 'incompatible-python',
        '#!/usr/bin/env bash\nexec ' + shlex.quote(sys.executable) + ' -c ' +
        shlex.quote(setup + 'exec(__import__("sys").stdin.read())') + '\n')
    environment = safe_environment()
    environment['FOOTBALL_BACKEND_PYTHON'] = str(wrapper)
    result = subprocess.run(['bash', str(ROOT / 'scripts/start-dev.sh'), '--check'],
        env=environment, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'Python 3.12+' in result.stderr
    assert 'requirements-agents.txt' in result.stderr


def test_backend_launcher_starts_real_uvicorn_and_serves_registered_case():
    # Ephemeral localhost port, no persistent cache/ledger and no .env load.
    environment = safe_environment()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryFile(mode='w+b') as log:
        process = subprocess.Popen(['bash', str(ROOT / 'scripts/start-backend.sh'), '--port', '0'],
            cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            base = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                assert process.poll() is None, 'Backend process exited during startup'
                log.seek(0)
                match = re.search(rb'Uvicorn running on http://127\.0\.0\.1:(\d+)', log.read())
                if match:
                    base = 'http://127.0.0.1:' + match[1].decode()
                    break
                time.sleep(.05)
            assert base is not None, 'Backend did not become ready'
            def get(path):
                with opener.open(base + path, timeout=5) as response:
                    return json.load(response)
            assert get('/health')['status'] == 'ok'
            match_id = get('/api/matches')['matches'][0]['match_id']
            case = get(f'/api/matches/{match_id}/cases?through_timestamp=5400')['cases'][0]
            request = urllib.request.Request(
                base + f"/api/matches/{match_id}/cases/{case['case_id']}/courtroom",
                data=json.dumps({'through_timestamp': 5400}).encode(),
                headers={'Content-Type': 'application/json'}, method='POST')
            with opener.open(request, timeout=5) as response:
                result = json.load(response)
            assert result['source'] == 'deterministic_fallback'
            assert result['api_attempts'] == 0
            assert result['evidence']['case_id'] == case['case_id']
            assert result['judge']['result'] == 'inconclusive'
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
