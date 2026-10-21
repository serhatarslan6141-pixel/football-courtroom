"""Read-only public courtroom. No AI imports, client, budget, or write path."""
from .courtroom_evidence import InvalidAgentOutput, build_evidence, fallback_parts
from .courtroom_models import TrialResult
from .trial_library import TrialLibrary, cached_view


class CachedOnlyTrialService:
    def __init__(self, library=None):
        self.library = library if library is not None else TrialLibrary()

    async def analyze(self, match, case_id, through_timestamp, *, allow_live=False):
        # Deliberately ignore allow_live. No request can authorize public AI.
        evidence = build_evidence(match, case_id, through_timestamp)
        reason = 'live_disabled'
        try:
            cached = self.library.read(evidence)
            if cached is not None:
                return cached_view(cached)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, InvalidAgentOutput):
            reason = 'cache_unavailable'
        prosecution, defense, judge = fallback_parts(evidence)
        return TrialResult(
            source='deterministic_fallback',
            disclosure='Recorded-evidence assessment. No AI ruling is presented.',
            evidence=evidence, evidence_agent=None, prosecution=prosecution,
            defense=defense, judge=judge, trace=[], api_attempts=0,
            original_api_attempts=0, error_category=reason, http_status=None,
            cache_key=None, configuration_version='public-cached-only-v1')

    async def prepare(self, match, case_id, through_timestamp):
        return await self.analyze(match, case_id, through_timestamp)
