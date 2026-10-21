# Prepared complete trial with the simplified agent architecture

**Historical, now failed and blocked.** The approved run completed Evidence and
stopped at Prosecution grounding validation after two model attempts. Do not
rerun these startup steps for this case. See [the offline failure investigation](prosecution-failure-investigation.md).

**Preparation only. No Azure requests and no live process started.** Separate
explicit approval is required before executing the startup command below.

## Selected fresh case

- Match `synthetic-303`: **Northbridge City vs Harbor Athletic**.
- Case `synthetic-303-missed_opportunity-home-2412`: home missed chance at
  **40:12**, available at **41:42**.
- Closed window **38:42–41:42** (2322–2502 seconds), 105 events and 33 verified
  facts. This is the smallest remaining built-in case by compact downstream
  evidence size, excluding every previously attempted trial/diagnostic case.
- Evidence selection payload: 4,510 bytes. Complete mocked Evidence request:
  8,301 bytes. With three selected facts, complete downstream requests measured
  36,333 / 36,628 / 37,576 bytes for Prosecution / Defense / Judge.
- Current configuration's cache identity:
  `1bdfe23f37a8281431fd794ee55ef6f6662d5cb51eaf225c8a2093e64f774034`.
  No matching record exists. Do not remove a record if one appears later.

The exact case passes the installed Agent Framework → Responses SDK → mocked
transport → FastAPI API path, then the actual frontend presentation adapter.
Evidence selects three existing facts; Python constructs exact observations and
citations. Prosecution, Defense and Judge pass independent schema/grounding
checks and ordered handoffs. All four wire schemas satisfy the documented
Azure subset. The public response retains evidence, opposing panels, ruling
and four-agent trace; cached preparation adds no requests. The existing UI
keeps voting independent and seals the ruling until the vote stage.

Two regression additions cover this case's complete three-fact pipeline,
eligibility at 2502 (not 2501), stable later cutoffs, non-billable preparation,
four-attempt cap and cached reuse. The 26-test architecture suite passes.
Final regression validation: **411 backend tests and 128 frontend tests passed**.
Only the existing Starlette/AnyIO deprecation warning remains. The backend
launcher check selected Python 3.12.15 without starting a service. Preservation
hashes confirm `.env` and every pre-existing runtime file unchanged.

## Local configuration, quota and allowance

The saved resource hostname matches the previously approved resource; endpoint
format, API-key presence (value never printed), deployment name `gpt-4.1-mini`,
Python 3.12.15 and pinned Agent Framework/SDK versions were checked locally.
Both saved live flags remain disabled. No Azure CLI, token refresh, HTTP/DNS,
pricing, management or inference requests were made during preparation.

**Azure-side deployment state and available TPM/RPM quota remain unverified.**
The saved deployment name and previous successful requests are not a current
quota check. No authoritative local quota snapshot is available. A future
read-only portal/management check requires permission to contact Azure; it need
not make an inference request. Local request counters are separate from Azure
quota and billing.

The current **UTC day is 2026-10-21** (October 20 in the user's local time).
Effective usage for this UTC day is **0 / 10**, leaving **10**. The ledger still
contains its original `2026-10-19, count: 7` record; it has not been reset or
rewritten. The existing budget code interprets a previous-day record as zero
current-day usage and updates it only on the next reserved physical send.

Proposed process cap: **4** now, recomputed as current usage plus four at approved
startup, never exceeding the saved cap. Per-trial max calls **4**, zero retries,
120-second **per-agent** timeout. Output budgets remain 768 / 1024 / 1024 / 1536
(4,352 combined). Preserve every cache, failed record and consumed diagnostic.

## Estimated maximum cost

Allow roughly **30,000–45,000 input tokens** across four calls and up to **4,352
output tokens**. This is an input estimate based on intercepted request sizes,
not an exact tokenizer measurement or live usage.

At the previously checked reference rates (Global $0.40/M input, $1.60/M output;
Data Zone $0.44/M and $1.76/M), this is approximately **$0.019–$0.028** at the
output ceilings. Budget about **$0.03** as an estimated upper end for this case.
Rates were not refreshed because preparation permits no Azure requests. Actual
region/SKU/account pricing is not verified; this is **not a guaranteed USD
cap**. The enforced cap is four physical attempts. Failed or incomplete model
execution may still be billable.

## Exact future startup: execute only after separate approval

First review any desired non-inference deployment/quota check and obtain
approval for live enabling. Ensure ports 8000 and 5173 are free and no other
live process is using the shared allowance. Run from the project root:

```bash
PYTHONPATH=backend .venv/phase4b/bin/python - <<'PY'
import os
from pathlib import Path
from dotenv import dotenv_values
from app.courtroom import TrialCache, TrialConfig, trial_cache_key
from app.courtroom_evidence import build_evidence
from app.diagnose_evidence import _usage_today
from app.foundry import DailyRequestBudget, FoundrySettings
from app.synthetic_match import get_match

root = Path.cwd()
saved = dotenv_values(root / '.env', interpolate=False)
assert all(saved.get(k) for k in ('AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY'))
day, used = _usage_today(DailyRequestBudget().path)
saved_cap = int(saved.get('FOUNDRY_DAILY_REQUEST_CAP') or 10)
assert 0 <= used and used + 4 <= saved_cap <= 100, 'Insufficient daily allowance'
env = os.environ.copy()
env.update({k: v for k, v in saved.items() if v is not None
            and k.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'COURTROOM_'))})
env.update(FOUNDRY_LIVE_ENABLED='true', COURTROOM_LIVE_ENABLED='true',
           EVIDENCE_DIAGNOSTIC_LIVE_ENABLED='false',
           FOUNDRY_TIMEOUT_SECONDS='120', FOUNDRY_MAX_RETRIES='0',
           COURTROOM_MAX_MODEL_CALLS='4', FOUNDRY_DAILY_REQUEST_CAP=str(used + 4))
# This future, short-lived launcher process gets the overrides, then execs the
# server. The shell, saved .env and all other processes remain unchanged.
os.environ.update(env)
settings, config = FoundrySettings.from_env(), TrialConfig.from_env()
assert settings.deployment == 'gpt-4.1-mini'
assert [config.output_tokens_for(r) for r in ('evidence', 'prosecution', 'defense', 'judge')] == [768, 1024, 1024, 1536]
evidence = build_evidence(get_match('synthetic-303'),
                         'synthetic-303-missed_opportunity-home-2412', 2502)
key = trial_cache_key(evidence, settings, config)
assert key == '1bdfe23f37a8281431fd794ee55ef6f6662d5cb51eaf225c8a2093e64f774034', 'Evidence/configuration changed; stop'
assert TrialCache().read(key) is None, 'Case already recorded; stop'
python = str(root / '.venv/phase4b/bin/python')
print(f'UTC day {day}; used {used}; process cap {used + 4}. Stop after one trial.', flush=True)
os.execve(python, [python, '-m', 'uvicorn', 'app.main:app', '--app-dir',
                  str(root / 'backend'), '--host', '127.0.0.1', '--port', '8000'], env)
PY
```

This command was not executed during preparation. No reload/multiple workers,
probe or Evidence diagnostic accompanies it. Starting the server itself does
not invoke inference. A busy/corrupt cache, changed configuration or insufficient
allowance must be investigated without clearing records or retrying a trial.

In another terminal, from the project root:

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

## Browser action and shutdown

1. Open `http://127.0.0.1:5173` in one fresh tab. Optionally open DevTools Network
   with Preserve log first; never copy request headers/credentials.
2. Choose **Enter the match**, then **Northbridge City vs Harbor Athletic**
   (`synthetic-303`). Do not generate another fixture.
3. Pause replay and seek to **41:42 or later**. Open **Cases**, then the home
   missed-chance case available at **41:42**, incident **40:12**. The case card
   shows availability rather than the original incident time.
4. Click **Begin Trial**. This is a non-billable preparation lookup. Verify the
   four-agent charge confirmation appears; stop if you see unexpected fallback.
5. Review the confirmation and click **Confirm & begin trial** yourself once.
   Do not refresh, retry, change case or open another tab while generating.
6. Follow Evidence → Both Sides → Your Verdict → The Ruling. The judge remains
   sealed until your vote; **Behind the verdict** shows actual validated traces.
7. Stop the backend immediately after this one outcome, successful or failed,
   even if unused allowance remains. Preserve records and inspect sanitized
   status/usage before considering another request. Stop the frontend afterward.

The cap is shared and UTC-day based, not a per-case/lifetime process allowlist.
Never leave this backend running across **00:00 UTC**, which renews the daily
allowance. Use foreground supervision and a local completion/deadline shutdown
watcher when the approved run is actually started. No watcher is started now.

The simplified architecture has not completed a live full trial. Model brevity,
grounded reference choices, token budgets, provider latency and quota remain
risks despite successful mocks. No automatic retry or validation relaxation is
permitted. Existing failed cases and diagnostics remain blocked.
