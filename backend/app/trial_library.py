"""Portable, validated AI results. Reading this library never requires Azure.

Only the offline publisher/batch CLI writes here. Ship this directory with the
backend (or mount it read-only); private usage/failure records stay in .logs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

from .courtroom_evidence import digest, validate_submission
from .courtroom_models import TrialResult
ROOT = Path(__file__).resolve().parents[2]

ROLES = ('evidence', 'prosecution', 'defense', 'judge')


def validate_completed(result, evidence):
    """Accept a complete grounded four-agent result, never a partial/fallback."""
    result = TrialResult.model_validate(result)
    if (result.source != 'live_ai' or result.evidence != evidence
            or result.evidence_agent is None or result.api_attempts != 4
            or result.original_api_attempts != 4 or result.error_category is not None
            or result.http_status != 200 or len(result.trace) != 4
            or not re.fullmatch(r'[a-f0-9]{64}', result.cache_key or '')):
        raise ValueError('Invalid completed trial')
    for index, role in enumerate(ROLES):
        output = getattr(result, 'evidence_agent' if role == 'evidence' else role)
        validate_submission(role, output, evidence)
        trace = result.trace[index]
        if (trace.agent != role or trace.status != 'completed' or trace.error_category is not None
                or trace.handoff_to != (ROLES[index + 1] if index < 3 else None)
                or not re.fullmatch(r'[a-f0-9]{64}', trace.input_digest)
                or trace.output_digest != digest(output.model_dump())):
            raise ValueError('Invalid completed handoff')
    return result


def cached_view(result):
    return result.model_copy(update={'source': 'cached_ai', 'api_attempts': 0,
        'disclosure': 'Cached AI reasoning over verified synthetic facts; no new model requests.'})


class TrialLibrary:
    def __init__(self, directory=None):
        self.directory = Path(directory if directory is not None else os.environ.get(
            'COURTROOM_TRIAL_LIBRARY_DIR', ROOT / 'backend' / 'data' / 'courtroom-trials'))

    def path_for(self, evidence):
        # No resource/key/deployment identity is needed by a public reader.
        return self.directory / (digest(evidence.model_dump()) + '.json')

    def read(self, evidence):
        path = self.path_for(evidence)
        if not path.exists():
            return None
        if path.stat().st_size > 2_000_000:
            raise ValueError('Invalid trial artifact')
        record = json.loads(path.read_text())
        if (set(record) != {'format_version', 'evidence_digest', 'result'}
                or record['format_version'] != 1
                or record['evidence_digest'] != digest(evidence.model_dump())):
            raise ValueError('Invalid trial artifact')
        return validate_completed(record['result'], evidence)

    def publish(self, result):
        result = validate_completed(result, result.evidence)
        existing = self.read(result.evidence)
        if existing is not None:
            return False  # A valid result is immutable, even if wording differs.
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.directory, prefix='.publish-')
        try:
            # These are public synthetic results, not private runtime records.
            # A deployment may serve them under a different unprivileged UID.
            os.fchmod(fd, 0o644)
            with os.fdopen(fd, 'w') as stream:
                json.dump({'format_version': 1, 'evidence_digest': digest(result.evidence.model_dump()),
                           'result': result.model_dump()}, stream, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                # Atomic create, never replace: concurrent publishers cannot win
                # by overwriting a valid artifact or an invalid record.
                os.link(temporary, self.path_for(result.evidence))
            except FileExistsError:
                self.read(result.evidence)  # Existing corrupt artifacts fail closed.
                return False
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return True
        finally:
            os.unlink(temporary)
