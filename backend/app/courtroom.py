"""Opt-in trial service, persistent single-flight cache and deterministic fallback.

Importing this module never reads .env, imports Agent Framework, or opens a socket.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Optional

from .courtroom_evidence import InvalidAgentOutput, build_evidence, digest, fallback_parts, validate_submission
from .courtroom_models import AgentTrace, TrialResult, VerifiedEvidence
from .foundry import DailyRequestBudget, FoundrySettings, FoundryUnavailable, ROOT, _integer

CONFIGURATION_VERSION = 'courtroom-v2-agent-token-budgets-af-core1.22.0-openai1.17.0'
ROLES = ('evidence', 'prosecution', 'defense', 'judge')
DEFAULT_AGENT_OUTPUT_TOKENS = {'evidence': 768, 'prosecution': 1024, 'defense': 1024, 'judge': 1536}


@dataclass(frozen=True)
class TrialConfig:
    max_calls: int
    output_tokens: int
    agent_output_tokens: dict[str, int]
    max_input_bytes: int

    @classmethod
    def from_env(cls):
        return cls(
            max_calls=_integer('COURTROOM_MAX_MODEL_CALLS', 4, 0, 4),
            # FOUNDRY_MAX_OUTPUT_TOKENS belongs to the tiny Phase 4A probe.
            # Courtroom JSON needs its own explicit, bounded output budget.
            output_tokens=_integer('COURTROOM_MAX_OUTPUT_TOKENS', 1536, 32, 2048),
            agent_output_tokens={role: _integer(f'COURTROOM_{role.upper()}_MAX_OUTPUT_TOKENS',
                default, 32, 2048) for role, default in DEFAULT_AGENT_OUTPUT_TOKENS.items()},
            max_input_bytes=_integer('COURTROOM_MAX_INPUT_BYTES', 128000, 1024, 128000),
        )

    def output_tokens_for(self, role: str) -> int:
        return min(self.output_tokens, self.agent_output_tokens[role])


@dataclass
class TrialState:
    evidence: VerifiedEvidence
    outputs: dict = field(default_factory=dict)
    trace: list[AgentTrace] = field(default_factory=list)
    api_attempts: int = 0
    active_role: Optional[str] = None
    sent_roles: set = field(default_factory=set)
    error_category: Optional[str] = None
    http_status: Optional[int] = None


class CacheBusy(Exception):
    pass


class TrialCache:
    """POSIX per-key lock plus atomic private JSON records; no paid service.

    Write an in-progress tombstone BEFORE inference. A failed/cancelled/crashed
    trial is never automatically generated again for the same cache identity.
    """
    def __init__(self, directory: Path = ROOT / '.logs' / 'courtroom'):
        self.directory = directory

    @contextmanager
    def claim(self, key: str):
        self.directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.directory / f'{key}.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CacheBusy() from None
            yield
        finally:
            os.close(fd)

    def read(self, key: str):
        path = self.directory / f'{key}.json'
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def write(self, key: str, record: dict):
        fd, temporary = tempfile.mkstemp(dir=self.directory, prefix='.trial-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(record, stream, separators=(',', ':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / f'{key}.json')
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def fallback(evidence, reason, state=None, key=None) -> TrialResult:
    prosecution, defense, judge = fallback_parts(evidence)
    return TrialResult(
        source='deterministic_fallback',
        disclosure='Recorded-evidence assessment. No AI ruling is presented; any partial AI outputs were discarded.',
        evidence=evidence, evidence_agent=None, prosecution=prosecution,
        defense=defense, judge=judge, trace=state.trace if state else [],
        api_attempts=state.api_attempts if state else 0,
        original_api_attempts=state.api_attempts if state else 0,
        error_category=reason, http_status=state.http_status if state else None,
        cache_key=key, configuration_version=CONFIGURATION_VERSION,
    )


class TrialService:
    def __init__(self, cache=None, budget=None, transport=None):
        self.cache = cache if cache is not None else TrialCache()
        self.budget = budget if budget is not None else DailyRequestBudget()
        # Tests inject httpx.MockTransport. Production uses verified direct HTTPS.
        self.transport = transport

    async def analyze(self, match, case_id: str, through_timestamp: int, *, allow_live=False):
        evidence = build_evidence(match, case_id, through_timestamp)
        if not allow_live:
            return fallback(evidence, 'live_not_requested')
        if (os.environ.get('COURTROOM_LIVE_ENABLED', '').lower() != 'true'
                or os.environ.get('FOUNDRY_LIVE_ENABLED', '').lower() != 'true'):
            return fallback(evidence, 'live_disabled')
        try:
            settings = FoundrySettings.from_env()
            config = TrialConfig.from_env()
        except FoundryUnavailable:
            return fallback(evidence, 'configuration_unavailable')
        key = digest({
            'evidence': evidence.model_dump(), 'configuration_version': CONFIGURATION_VERSION,
            'deployment': settings.deployment, 'resource': settings.base_url,
            'output_tokens': config.output_tokens, 'max_calls': config.max_calls,
            'agent_output_tokens': config.agent_output_tokens,
            'max_input_bytes': config.max_input_bytes,
        })
        state = TrialState(evidence)
        try:
            with self.cache.claim(key):
                record = self.cache.read(key)
                if record is not None:
                    if record.get('status') != 'completed':
                        return fallback(evidence, 'previous_trial_failed_or_incomplete', key=key).model_copy(
                            update={'original_api_attempts': record.get('api_attempts', 0)})
                    cached = TrialResult.model_validate(record['result'])
                    if (cached.source != 'live_ai' or cached.cache_key != key
                            or cached.evidence != evidence or cached.evidence_agent is None):
                        raise ValueError('Invalid cache record')
                    for role in ROLES:
                        validate_submission(role, getattr(cached, 'evidence_agent' if role == 'evidence' else role), evidence)
                    return cached.model_copy(update={'source': 'cached_ai', 'api_attempts': 0,
                        'disclosure': 'Cached AI reasoning over verified synthetic facts; no new model requests.'})
                # Missing framework is reported before any request or tombstone.
                try:
                    from .courtroom_workflow import execute_trial
                except (ImportError, SyntaxError):
                    return fallback(evidence, 'framework_unavailable', key=key)
                self.cache.write(key, {'status': 'in_progress'})
                try:
                    await execute_trial(state, settings, config, self.budget, self.transport)
                    result = TrialResult(
                        source='live_ai',
                        disclosure='AI-generated interpretations over verified synthetic match facts. Causal claims remain uncertain.',
                        evidence=evidence, evidence_agent=state.outputs['evidence'],
                        prosecution=state.outputs['prosecution'], defense=state.outputs['defense'],
                        judge=state.outputs['judge'], trace=state.trace,
                        api_attempts=state.api_attempts, original_api_attempts=state.api_attempts,
                        error_category=None, http_status=state.http_status, cache_key=key,
                        configuration_version=CONFIGURATION_VERSION,
                    )
                    self.cache.write(key, {'status': 'completed', 'result': result.model_dump()})
                    return result
                except Exception:
                    # Workflow executors sanitize their own errors. Unexpected
                    # errors are also withheld, never interpolated into responses.
                    reason = state.error_category or 'agent_execution_failed'
                    self.cache.write(key, {'status': 'failed', 'error_category': reason,
                                           'api_attempts': state.api_attempts})
                    return fallback(evidence, reason, state, key)
        except CacheBusy:
            return fallback(evidence, 'trial_in_progress', key=key)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, InvalidAgentOutput):
            return fallback(evidence, 'cache_unavailable', state, key)


trial_service = TrialService()
