#!/usr/bin/env python3
"""Create a validated, allowlisted build context. No cloud or credential access."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.courtroom_evidence import build_evidence
from app.synthetic_match import get_match
from app.trial_library import TrialLibrary

PUBLIC_MODULES = (
    '__init__.py', 'main.py', 'public_mode.py', 'public_courtroom.py',
    'courtroom_models.py', 'courtroom_evidence.py', 'trial_library.py',
    'case_detection.py', 'synthetic_match.py', 'simulation.py',
    'football_decisions.py', 'football_rules.py',
)


def prepare(output):
    if output.exists():
        raise ValueError('Choose a new output directory; existing files will not be overwritten.')
    library = TrialLibrary(ROOT / 'backend/data/courtroom-trials')
    artifacts = []
    for path in sorted(library.directory.glob('*.json')):
        record = json.loads(path.read_text())
        raw = record['result']['evidence']
        evidence = build_evidence(get_match(raw['match_id']), raw['case_id'], raw['evidence_cutoff'])
        if library.path_for(evidence) != path or library.read(evidence) is None:
            raise ValueError('Invalid public trial artifact.')
        artifacts.append(path)
    output.mkdir(parents=True)
    (output / 'backend/app').mkdir(parents=True)
    (output / 'backend/data/courtroom-trials').mkdir(parents=True)
    for name in ('Dockerfile', '.dockerignore', 'backend/requirements-public.txt'):
        shutil.copyfile(ROOT / name, output / name)
    for name in PUBLIC_MODULES:
        shutil.copyfile(ROOT / 'backend/app' / name, output / 'backend/app' / name)
    (output / 'backend/app/PUBLIC_ONLY').write_text('Cached-only public deployment. No AI execution modules.\n')
    for path in artifacts:
        shutil.copyfile(path, output / 'backend/data/courtroom-trials' / path.name)
    return {'status': 'prepared', 'public_trials': len(artifacts), 'ai_execution_modules': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.output.resolve())))
    except Exception:
        print('Preparation failed. Output must be new and public artifacts must validate.', file=sys.stderr)
        raise SystemExit(1) from None
