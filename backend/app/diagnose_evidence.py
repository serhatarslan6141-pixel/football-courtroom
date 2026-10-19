"""Isolated, opt-in, one-attempt Evidence diagnostic. Never starts a server.

Without --live: no .env read, model call, ledger write, or diagnostic record.
With --live: only this CLI process gets the dedicated diagnostic permission;
the full courtroom kill switch is explicitly OFF. Never import/call TrialService.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import logging
import os
import sys

from .courtroom import CacheBusy, TrialCache, TrialConfig, TrialState
from .courtroom_evidence import build_evidence, digest
from .foundry import DailyRequestBudget, FoundrySettings, FoundryUnavailable, ROOT
from .synthetic_match import get_match

MATCH_ID = 'synthetic-101'
CASE_ID = 'synthetic-101-missed_opportunity-away-3218'
CUTOFF = 3308
DIAGNOSTIC_ID = 'first-evidence-only-v1'
EXPECTED_INPUT_DIGEST = '731856a6c450ae9bf52e6a9867e51b7cf955dcb46160382d2d41ba43131ca409'


def _summary(status, state=None, **extra):
    return {
        'diagnostic': DIAGNOSTIC_ID, 'match_id': MATCH_ID, 'case_id': CASE_ID,
        'evidence_cutoff': CUTOFF, 'status': status, 'max_api_attempts': 1,
        'api_attempts': state.api_attempts if state else 0,
        'http_status': state.http_status if state else None,
        'error_category': state.error_category if state else None,
        'diagnostics': state.diagnostics if state else {},
        'trace': [entry.model_dump() for entry in state.trace] if state else [],
        **extra,
    }


def _usage_today(path):
    """Read only. The existing locked reserve() remains the write authority."""
    try:
        record = json.loads(path.read_text()) if path.exists() else {}
        today = datetime.now(timezone.utc).date().isoformat()
        used = record.get('count', 0) if record.get('day') == today else 0
        if type(used) is not int or not 0 <= used <= 100:
            raise ValueError()
        return today, used
    except (OSError, ValueError, TypeError, AttributeError):
        raise FoundryUnavailable('Usage ledger unavailable; diagnostic blocked.') from None


async def run_diagnostic(settings, config, *, allow_live=False, cache=None, budget=None, transport=None):
    """Explicit permission plus a one-node framework workflow, never a trial.

    Tests inject MockTransport and temporary records. The diagnostic identity
    stays fixed across prompt/config changes, so rerunning cannot buy a retry.
    The original .logs/courtroom namespace is never read, rewritten or cleared.
    """
    if (not allow_live or os.environ.get('EVIDENCE_DIAGNOSTIC_LIVE_ENABLED', '').lower() != 'true'
            or os.environ.get('COURTROOM_LIVE_ENABLED', '').lower() == 'true'):
        return _summary('disabled')
    if settings.deployment != 'gpt-4.1-mini' or not 1 <= settings.timeout <= 120:
        return _summary('configuration_unavailable')
    try:
        from .courtroom_workflow import execute_evidence_diagnostic, failure_category
    except (ImportError, SyntaxError):
        return _summary('framework_unavailable')
    evidence = build_evidence(get_match(MATCH_ID), CASE_ID, CUTOFF)
    state = TrialState(evidence)
    key = digest({'diagnostic': DIAGNOSTIC_ID, 'evidence': evidence.model_dump()})
    fingerprint = digest({'evidence': evidence.model_dump(), 'prior_submissions': {}})
    if fingerprint != EXPECTED_INPUT_DIGEST:
        return _summary('evidence_changed')
    cache = cache if cache is not None else TrialCache(ROOT / '.logs' / 'evidence-diagnostics')
    budget = budget if budget is not None else DailyRequestBudget()
    # Independent of env overrides and full-trial settings, never exceed one.
    config = replace(config, max_calls=min(1, config.max_calls))
    settings = replace(settings, retries=0)
    try:
        with cache.claim(key):
            if cache.read(key) is not None:
                return _summary('blocked_previous_diagnostic')
            today, used = _usage_today(budget.path)
            settings = replace(settings, daily_cap=min(settings.daily_cap, used + 1))
            metadata = {'input_digest': fingerprint, 'evidence_digest': digest(evidence.model_dump()),
                        'utc_day': today, 'usage_before': used, 'effective_daily_cap': settings.daily_cap}
            # Never allow a failed/cancelled/crashed attempt to auto-regenerate.
            cache.write(key, _summary('in_progress', **metadata))
            try:
                await asyncio.wait_for(execute_evidence_diagnostic(
                    state, settings, config, budget, transport), timeout=settings.timeout)
                report = _summary('completed', state, **metadata)
            except Exception as exc:
                state.error_category = failure_category(exc, state)
                state.diagnostics.setdefault('reason', state.error_category)
                report = _summary('failed', state, **metadata)
            # Only metadata/fingerprints: no raw or validated narrative is saved.
            cache.write(key, report)
            return report
    except CacheBusy:
        return _summary('blocked_concurrent_diagnostic')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, FoundryUnavailable):
        return _summary('record_or_budget_unavailable', state)


@contextmanager
def _live_environment():
    from dotenv import dotenv_values
    env_file = ROOT / '.env'
    if not env_file.is_file():
        raise FoundryUnavailable('Project-root configuration missing; diagnostic blocked.')
    values = dotenv_values(env_file, interpolate=False)
    if not all((values.get(name) or '').strip() for name in ('AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY')):
        raise FoundryUnavailable('Saved Azure configuration incomplete; diagnostic blocked.')
    overrides = {name: value for name, value in values.items() if value is not None
                 and name.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'COURTROOM_'))}
    overrides.update({
        'FOUNDRY_LIVE_ENABLED': 'true', 'COURTROOM_LIVE_ENABLED': 'false',
        'EVIDENCE_DIAGNOSTIC_LIVE_ENABLED': 'true',
        'FOUNDRY_TIMEOUT_SECONDS': '120', 'FOUNDRY_MAX_RETRIES': '0',
    })
    previous = {name: os.environ.get(name) for name in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main(argv=None):
    parser = argparse.ArgumentParser(description='Isolated Evidence-only diagnostic; disabled by default.')
    parser.add_argument('--live', action='store_true', help='Authorize at most ONE potentially billable Evidence request.')
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps(_summary('disabled')))
        return 0
    previous_logging = logging.root.manager.disable
    logging.disable(sys.maxsize)
    try:
        with _live_environment():
            settings = FoundrySettings.from_env()
            report = asyncio.run(run_diagnostic(settings, TrialConfig.from_env(), allow_live=True))
    except KeyboardInterrupt:
        # A tombstone, if created, remains blocked. Do not claim zero usage.
        report = _summary('interrupted', api_attempts=None)
    except Exception:
        # Exception strings can contain credentials, URLs or provider content.
        report = _summary('configuration_or_execution_unavailable', api_attempts=None)
    finally:
        logging.disable(previous_logging)
    print(json.dumps(report))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
