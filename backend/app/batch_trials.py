"""Explicit, resumable four-agent cache production. Default command is read-only.

No server is started. Only `generate --live` permits model sends. Published
artifacts contain validated public results, never settings or raw responses.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import logging
import os
import re
import sys

from .case_detection import detect_cases
from .courtroom import CacheBusy, TrialCache, TrialConfig, TrialService, trial_cache_key
from .courtroom_evidence import build_evidence, digest
from .diagnose_evidence import _usage_today
from .foundry import DailyRequestBudget, FoundrySettings, FoundryUnavailable, ROOT
from .synthetic_match import get_match
from .trial_library import TrialLibrary, validate_completed

MATCHES = ('synthetic-101', 'synthetic-202', 'synthetic-303')


def built_in_cases():
    return [build_evidence(get_match(match_id), case['case_id'], 5400)
            for match_id in MATCHES
            for case in detect_cases(get_match(match_id).events, through_timestamp=5400, match_id=match_id)]


def audit(settings, config, cache, library, diagnostics, *, cases=None):
    """Read every record, including legacy tombstones. Unmapped records block sends."""
    cases = built_in_cases() if cases is None else cases
    keys = {trial_cache_key(e, settings, config): e.case_id for e in cases}
    known = {e.case_id for e in cases}
    records = {case_id: [] for case_id in known}
    issues = []
    for directory, diagnostic in ((cache.directory, False), (diagnostics.directory, True)):
        for path in sorted(directory.glob('*.json')):
            try:
                record = json.loads(path.read_text())
                case_id = record.get('case_id') or record.get('result', {}).get('evidence', {}).get('case_id')
                case_id = case_id or (None if diagnostic else keys.get(path.stem))
                if (not diagnostic and record.get('status') == 'completed'
                        and record['result'].get('cache_key') != path.stem):
                    raise ValueError('Invalid cache identity')
                if case_id not in known:
                    # Do not guess the identity of an older failed allocation.
                    issues.append('unmapped_record')
                    continue
                records[case_id].append((record, diagnostic))
            except (OSError, ValueError, TypeError, AttributeError):
                issues.append('unreadable_record')
    rows = []
    for evidence in cases:
        status, reason, result = 'missing', None, None
        try:
            result = library.read(evidence)
            if result is not None:
                status = 'published'
            else:
                for record, diagnostic in records[evidence.case_id]:
                    if not diagnostic and record.get('status') == 'completed':
                        result = validate_completed(record['result'], evidence)
                        status = 'cached'
                        break
                if result is None:
                    for record, diagnostic in records[evidence.case_id]:
                        if not diagnostic or record.get('status') != 'completed':
                            status = 'blocked'
                            reason = 'previous_diagnostic_failed_or_incomplete' if diagnostic else 'previous_trial_failed_or_incomplete'
                            break
        except Exception:
            status, reason = 'blocked', 'cache_validation_failed'
        rows.append({'case_id': evidence.case_id, 'match_id': evidence.match_id,
                     'type': evidence.case_type, 'evidence_cutoff': evidence.evidence_cutoff,
                     'event_count': len(evidence.events), 'status': status, 'reason': reason})
    return {'cases': rows, 'issues': sorted(set(issues)),
            'counts': {status: sum(row['status'] == status for row in rows)
                       for status in ('published', 'cached', 'missing', 'blocked')}}


@dataclass(frozen=True)
class BatchLimits:
    max_requests: int
    daily_cap: int
    max_estimated_usd: str
    input_usd_per_million: str = '0.44'
    output_usd_per_million: str = '1.76'

    def validate(self):
        if (type(self.max_requests) is not int or not 4 <= self.max_requests <= 100
                or self.max_requests % 4 or type(self.daily_cap) is not int
                or not 4 <= self.daily_cap <= 100):
            raise ValueError('Invalid batch limits')
        for value in (self.max_estimated_usd, self.input_usd_per_million, self.output_usd_per_million):
            amount = Decimal(value)
            if not amount.is_finite() or amount <= 0:
                raise ValueError('Invalid cost limit')

    def per_request_reservation(self, config):
        # Conservative planning allowance, not an Azure billing guarantee:
        # one token per wire byte plus framing margin, and largest role output.
        # Azure region/SKU rates must be checked separately by the operator.
        return ((Decimal(config.max_input_bytes + 8192) * Decimal(self.input_usd_per_million)
                 + Decimal(max(config.output_tokens_for(r) for r in ('evidence', 'prosecution', 'defense', 'judge')))
                 * Decimal(self.output_usd_per_million)) / Decimal(1_000_000))


class BatchBudget:
    """Held batch lock + durable reservation BEFORE the global daily ledger.

    Interrupted reservations are never refunded. Losing a slot is preferable
    to an uncounted resend. Existing trial tombstones block partial reruns.
    """
    def __init__(self, store, batch_id, record, daily, limits, config):
        self.store, self.batch_id, self.record = store, batch_id, record
        self.daily, self.limits = daily, limits
        self.unit = limits.per_request_reservation(config)

    def has_trial_capacity(self):
        today, used = _usage_today(self.daily.path)
        return (today == self.record['utc_day']
                and self.record['reservations'] + 4 <= self.limits.max_requests
                and used + 4 <= self.limits.daily_cap
                and Decimal(self.record['reserved_estimated_usd']) + 4 * self.unit
                    <= Decimal(self.limits.max_estimated_usd))

    def reserve(self, cap):
        today, _ = _usage_today(self.daily.path)
        if (today != self.record['utc_day'] or self.record['reservations'] >= self.limits.max_requests
                or Decimal(self.record['reserved_estimated_usd']) + self.unit
                    > Decimal(self.limits.max_estimated_usd)):
            raise FoundryUnavailable('Batch request or estimated cost allowance exhausted.')
        self.record['reservations'] += 1
        self.record['reserved_estimated_usd'] = str(Decimal(self.record['reserved_estimated_usd']) + self.unit)
        self.store.write(self.batch_id, self.record)
        self.daily.reserve(min(cap, self.limits.daily_cap))


async def run_batch(settings, config, limits, batch_id, *, allow_live=False, case_ids=None,
                    cache=None, library=None, diagnostics=None, batches=None, daily=None, transport=None):
    """Never calls another agent path or retries a withheld/partial submission."""
    if not allow_live:
        return {'status': 'disabled'}
    limits.validate()
    if (not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', batch_id)
            or settings.deployment != 'gpt-4.1-mini' or settings.timeout != 120 or settings.retries != 0
            or config.max_calls != 4 or settings.daily_cap != limits.daily_cap
            or any(os.environ.get(name, '').lower() != 'true'
                   for name in ('FOUNDRY_LIVE_ENABLED', 'COURTROOM_LIVE_ENABLED'))):
        return {'status': 'configuration_unavailable'}
    cache = cache if cache is not None else TrialCache()
    library = library if library is not None else TrialLibrary()
    diagnostics = diagnostics if diagnostics is not None else TrialCache(ROOT / '.logs' / 'evidence-diagnostics')
    batches = batches if batches is not None else TrialCache(ROOT / '.logs' / 'trial-batches')
    daily = daily if daily is not None else DailyRequestBudget()
    all_cases = built_in_cases()
    chosen = sorted(case_ids) if case_ids else sorted(e.case_id for e in all_cases)
    if not set(chosen) <= {e.case_id for e in all_cases} or len(chosen) != len(set(chosen)):
        return {'status': 'invalid_case_selection'}
    # Identity binds both scope and ceilings, so --resume cannot raise them.
    signature = digest({'limits': limits.__dict__, 'cases': chosen,
                        'keys': [trial_cache_key(e, settings, config) for e in all_cases if e.case_id in chosen]})
    try:
        with batches.claim(batch_id):
            report = audit(settings, config, cache, library, diagnostics)
            if report['issues']:
                return {'status': 'audit_blocked', 'issues': report['issues']}
            today, used = _usage_today(daily.path)
            record = batches.read(batch_id)
            if record is None:
                record = {'signature': signature, 'utc_day': today, 'reservations': 0,
                          'reserved_estimated_usd': '0'}
                batches.write(batch_id, record)
            if (record['signature'] != signature or record['utc_day'] != today
                    or type(record['reservations']) is not int or record['reservations'] < 0
                    or not Decimal(record['reserved_estimated_usd']).is_finite()
                    or Decimal(record['reserved_estimated_usd']) < 0):
                return {'status': 'batch_identity_or_day_changed'}
            budget = BatchBudget(batches, batch_id, record, daily, limits, config)
            service = TrialService(cache, budget, transport, library=library)
            results = []
            status = 'completed'
            for evidence in all_cases:
                if evidence.case_id not in chosen:
                    continue
                # Recheck preserved records immediately before each case.
                fresh = audit(settings, config, cache, library, diagnostics)
                if fresh['issues']:
                    status = 'audit_blocked'
                    break
                row = next(r for r in fresh['cases'] if r['case_id'] == evidence.case_id)
                if row['status'] == 'cached':
                    publish_cached(settings, config, cache, library, [evidence])
                    results.append({'case_id': evidence.case_id, 'status': 'published_existing'})
                    continue
                if row['status'] in ('blocked', 'published'):
                    results.append({'case_id': evidence.case_id, 'status': row['status'], 'reason': row['reason']})
                    continue
                if not budget.has_trial_capacity():
                    status = 'allowance_exhausted'
                    break
                result = await service.analyze(get_match(evidence.match_id), evidence.case_id,
                                               evidence.evidence_cutoff, allow_live=True)
                if result.source != 'live_ai':
                    results.append({'case_id': evidence.case_id, 'status': 'stopped',
                                    'api_attempts': result.api_attempts, 'error_category': result.error_category})
                    status = 'trial_failed_stop'  # No automatic next paid case after a failure.
                    break
                library.publish(result)
                results.append({'case_id': evidence.case_id, 'status': 'published', 'api_attempts': result.api_attempts})
            _, after = _usage_today(daily.path)
            return {'status': status, 'results': results, 'utc_day': today,
                    'daily_usage_before': used, 'daily_usage_after': after,
                    'daily_remaining': max(0, limits.daily_cap - after),
                    'batch_reservations': record['reservations'],
                    'reserved_estimated_usd': record['reserved_estimated_usd']}
    except CacheBusy:
        return {'status': 'batch_in_progress'}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, FoundryUnavailable, InvalidOperation):
        return {'status': 'records_or_configuration_unavailable'}


def publish_cached(settings, config, cache, library, cases=None):
    """Offline export only. Never infer and never write to the private cache."""
    count = 0
    for evidence in built_in_cases() if cases is None else cases:
        # A configuration change must not buy another trial for a case that
        # already has a valid completed result under an older cache identity.
        for path in sorted(cache.directory.glob('*.json')):
            record = json.loads(path.read_text())
            if (record.get('status') == 'completed'
                    and record.get('result', {}).get('evidence', {}).get('case_id') == evidence.case_id):
                result = validate_completed(record['result'], evidence)
                if result.cache_key != path.stem:
                    raise ValueError('Invalid private cache identity')
                count += int(library.publish(result))
                break
    return count


@contextmanager
def configuration(*, live=False, daily_cap=None):
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / '.env', interpolate=False)
    changes = {k: v for k, v in values.items() if v is not None
               and k.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'COURTROOM_'))}
    changes.update(FOUNDRY_LIVE_ENABLED='true' if live else 'false',
                   COURTROOM_LIVE_ENABLED='true' if live else 'false',
                   FOUNDRY_MAX_RETRIES='0', FOUNDRY_TIMEOUT_SECONDS='120', COURTROOM_MAX_MODEL_CALLS='4')
    if daily_cap is not None:
        changes['FOUNDRY_DAILY_REQUEST_CAP'] = str(daily_cap)
    previous = {k: os.environ.get(k) for k in changes}
    os.environ.update(changes)
    try:
        yield FoundrySettings.from_env(require_live=live), TrialConfig.from_env()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit', 'publish', 'generate'), nargs='?', default='audit')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--batch-id')
    parser.add_argument('--case', dest='case_ids', action='append')
    parser.add_argument('--max-requests', type=int)
    parser.add_argument('--daily-cap', type=int)
    parser.add_argument('--max-estimated-usd')
    parser.add_argument('--input-usd-per-million', default='0.44')
    parser.add_argument('--output-usd-per-million', default='1.76')
    args = parser.parse_args(argv)
    if args.command == 'generate' and not args.live:
        print(json.dumps({'status': 'disabled', 'api_attempts': 0}))
        return 0
    if args.live and args.command != 'generate':
        parser.error('--live is only valid with generate')
    if args.command == 'generate' and any(value is None for value in (
            args.batch_id, args.max_requests, args.daily_cap, args.max_estimated_usd)):
        parser.error('generate requires explicit batch ID, request cap, daily cap and cost allowance')
    previous_logging = logging.root.manager.disable
    logging.disable(sys.maxsize)
    try:
        with configuration(live=args.command == 'generate', daily_cap=args.daily_cap) as (settings, config):
            cache, library = TrialCache(), TrialLibrary()
            if args.command == 'audit':
                report = audit(settings, config, cache, library,
                               TrialCache(ROOT / '.logs' / 'evidence-diagnostics'))
                day, used = _usage_today(DailyRequestBudget().path)
                report.update(utc_day=day, daily_used=used, daily_cap=settings.daily_cap,
                              daily_remaining=max(0, settings.daily_cap - used),
                              missing_model_calls=4 * report['counts']['missing'])
            elif args.command == 'publish':
                report = {'status': 'published', 'new_artifacts': publish_cached(settings, config, cache, library),
                          'api_attempts': 0}
            else:
                limits = BatchLimits(args.max_requests, args.daily_cap, args.max_estimated_usd,
                                     args.input_usd_per_million, args.output_usd_per_million)
                report = asyncio.run(run_batch(settings, config, limits, args.batch_id,
                                               allow_live=True, case_ids=args.case_ids))
    except KeyboardInterrupt:
        report = {'status': 'interrupted_preserved', 'api_attempts': None}
    except Exception:
        report = {'status': 'configuration_or_records_unavailable', 'api_attempts': None}
    finally:
        logging.disable(previous_logging)
    print(json.dumps(report))
    return 0 if report.get('status') in (None, 'completed', 'published', 'allowance_exhausted') else 1


if __name__ == '__main__':
    raise SystemExit(main())
