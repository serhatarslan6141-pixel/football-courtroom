# Next controlled four-agent trial: preparation only

Prepared on 2026-10-19 after the separately approved Evidence-only diagnostic
succeeded (HTTP 200, validated output, 11,769 input / 239 output tokens).
This preparation makes no model request, starts no server, and leaves live mode
disabled. A new explicit approval is required before running the startup recipe.

## Selected case

- Fixture: **Mossfield United vs Riverside Athletic**, `synthetic-202` (built-in).
- Case: `synthetic-202-missed_opportunity-away-1910`, away missed chance at
  **31:50**, available at **33:20**.
- Fixed evidence window: **30:20–33:20** (1820–2000 seconds).
- 81 completed events, 33 server-verified facts; initial compact shared payload
  44,471 bytes. This is the smallest alternative among the built-in fixtures'
  cases after excluding the original blocked case. It is larger than the
  successful Evidence-only diagnostic's input; no context is silently removed.
- No production cache record exists for its saved configuration. Expected key:
  `0ae0e67e02ebad329b607e12de08226f25054a8672e878c4adf5c17ae0cff3c3`.
  Recheck before enabling; do not delete a record if one appears.
- The original `synthetic-101` failed record and isolated diagnostic remain
  untouched. Later replay cursors produce the same selected-case evidence/key.

## Mocked readiness checks

`backend/tests/test_courtroom.py` tests this exact case through the real Microsoft
Agent Framework and Responses SDK with MockTransport, fake credentials,
forbidden real sockets, and temporary cache/ledger files:

- Not eligible at 1999 seconds; eligible at 2000, with stable evidence thereafter.
- The HTTP preparation endpoint asks for confirmation and consumes no requests.
- Evidence → Prosecution → Defense → Judge: four calls, strict structured
  schemas, existing grounding validation, complete ordered handoffs, verified
  input/output digests, prior validated submissions and final cautious ruling.
- Existing output limits 768 / 1024 / 1024 / 1536; serialized mock requests fit
  the 128,000-byte ceiling. This verifies fixture compatibility, not the length
  or validity of future model-generated prose.
- Unknown/out-of-window citations in any agent stop the sequence, discard
  partial AI content, return recorded fallback and block repeat generation.
- Completed trials are reused without requests, including later replay cursors.
- An existing count of five reaches nine after four mocked sends, and the next
  reservation is blocked. Existing concurrency/duplicate/retry tests also apply.

Validation: **176 backend tests passed** across courtroom, isolated diagnostic
and Foundry suites; **128 frontend tests passed**. Six backend tests specifically
exercise this proposed case. `.env` and every pre-existing runtime file were
hash-checked unchanged after testing; the ledger remains at five and port 8000
has no listener. Only this document and the case-specific mocked tests changed.

## Budget and estimate

At preparation the UTC ledger day is 2026-10-19 and count is **5**. Saved daily cap
is 10; proposed process-only cap is **9**, permitting at most four additional
physical sends within this UTC day. No counters are reset. Recalculate immediately
before approved startup; if fewer than four remain under the saved cap, stop.

Maximum requests per trial: **4**, one per agent, zero SDK retries. Failure stops
the remaining handoffs. Failure can still be billable. Output ceilings total
4,352 tokens. Approximate total input across the four calls is **60,000–75,000
tokens**, including repeated evidence, schemas/instructions and prior outputs;
this is an estimate informed by the measured earlier diagnostic, not a tokenized
measurement of a future trial.

Microsoft's public retail API was checked during preparation (public pricing
only, no resource/deployment/inference requests). East US 2 GPT-4.1 mini lists
Global input/output at **$0.40 / $1.60 per million tokens**, and Data Zone/regional
at **$0.44 / $1.76**. Estimated trial cost at those rates is approximately
**$0.03–$0.04**; allow **$0.05** as an estimate, not a hard dollar cap. Actual
SKU, region, contract, output length and account charges are not verified.

Source: [Microsoft retail prices](https://prices.azure.com/api/retail/prices?$filter=productName%20eq%20%27Azure%20OpenAI%27%20and%20contains%28skuName%2C%20%274.1%20mini%27%29%20and%20armRegionName%20eq%20%27eastus2%27&currencyCode=USD).

## Future startup, only after new explicit approval

Run from the project root, in a dedicated foreground terminal. This recipe is
documentation only and was **not executed during preparation**. It reads saved
configuration privately, recomputes usage and uses process-only overrides.
It does not initiate a trial. No reload, multiple workers, connection probe, or
Evidence diagnostic should accompany this startup.

```bash
PYTHONPATH=backend .venv/phase4b/bin/python - <<'PY'
import os
from pathlib import Path
from dotenv import dotenv_values
from app.diagnose_evidence import _usage_today
from app.foundry import DailyRequestBudget

root = Path.cwd()
saved = dotenv_values(root / '.env', interpolate=False)
assert all(saved.get(k) for k in ('AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY'))
day, used = _usage_today(DailyRequestBudget().path)
saved_cap = int(saved.get('FOUNDRY_DAILY_REQUEST_CAP') or 10)
assert used + 4 <= saved_cap <= 100, 'Insufficient existing daily allowance'
env = os.environ.copy()
env.update({k: v for k, v in saved.items() if v is not None
            and k.startswith(('AZURE_OPENAI_', 'FOUNDRY_', 'COURTROOM_'))})
env.update(FOUNDRY_LIVE_ENABLED='true', COURTROOM_LIVE_ENABLED='true',
           EVIDENCE_DIAGNOSTIC_LIVE_ENABLED='false',
           FOUNDRY_TIMEOUT_SECONDS='120', FOUNDRY_MAX_RETRIES='0',
           COURTROOM_MAX_MODEL_CALLS='4', FOUNDRY_DAILY_REQUEST_CAP=str(used + 4))
python = str(root / '.venv/phase4b/bin/python')
print(f'UTC day {day}; used {used}; process cap {used + 4}. Stop after one trial.', flush=True)
os.execve(python, [python, '-m', 'uvicorn', 'app.main:app', '--app-dir',
                  str(root / 'backend'), '--host', '127.0.0.1', '--port', '8000'], env)
PY
```

The 120-second deadline is **per agent**, not a total four-agent deadline. Keep
the terminal running and allow several minutes without reloading or retrying.
The daily cap is shared, not a selected-case allowlist or lifetime process quota.
Use only the selected case in one browser tab, no other model tools/processes.
Stop the backend immediately after success **or failure**, even if unused
allowance remains. Stop before **00:00 UTC**: a UTC-day rollover renews the daily
allowance, so leaving a live server running overnight is outside this procedure.
Do not change cache-identifying settings to bypass any failed-case block.

## Browser steps after approved startup

1. In a separate terminal, run `cd frontend` then
   `npm run dev -- --host 127.0.0.1`. Open `http://127.0.0.1:5173` in a fresh tab.
2. Choose **Enter the match**, select **Mossfield United vs Riverside Athletic**
   (`synthetic-202`) and enter the replay. Do not create a new fixture.
3. Pause replay. Seek to **33:20 or later** using the replay timeline, then open
   **Cases**. Choose the away missed-opportunity case available at **33:20**
   (incident **31:50**). The case list labels availability, not incident time.
4. Optionally open DevTools Network first with Preserve log; inspect only
   sanitized response metadata afterward. Never copy headers/credentials.
5. Click **Begin Trial**. This makes only the non-billable preparation lookup.
   An uncached, eligible live case displays **Begin the four-agent trial?** and
   the up-to-four-request charge notice. If it shows fallback or unexpected
   content instead, stop and investigate rather than attempting another case.
6. Review the dialog and click **Confirm & begin trial** once. This is the sole
   billable action. Do not refresh, navigate away, use another tab, or retry.
7. Follow the existing five stages. Verified findings populate Evidence; opposing
   arguments use the existing panels; vote independently before the Judge's
   ruling is unsealed. Check **Behind the verdict** for real ordered handoffs.
   Evidence links stay inside the case window; leaving returns to the replay
   position saved on entry. Fallback must remain labeled as recorded analysis.
8. Stop the backend with Ctrl-C after the one outcome. Preserve logs/cache and
   ledger, and report sanitized status/attempts before considering any new run.

React invokes generation only from the explicit confirmation handler, with a
synchronous per-case submission guard. Preparation, navigation, rerenders and
replay do not trigger generation. Backend cache locks, failed/in-progress
tombstones, revalidation of cached outputs, per-role send guards and locked
daily reservations remain unchanged. A new browser can lose its in-memory
guard; the persistent backend protections remain the authority.

Mock success does not guarantee live validity, quota availability, latency or
success of the other three agents. The earlier Evidence success establishes
that the saved deployment/configuration worked for that approved request, not
that a complete trial has already succeeded.
