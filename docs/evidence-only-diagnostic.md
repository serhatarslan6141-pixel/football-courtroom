# Isolated Evidence-only diagnostic

The original allocation below has since completed and remains consumed. A new,
separately prepared allocation for a different unblocked case is documented in
[Evidence schema diagnostic](evidence-schema-diagnostic.md). Its fixed
`--schema-check` selector does not reset or reuse the original record. Preparation
is complete; live execution still requires separate explicit approval.

This original harness was mock-tested, then executed once with explicit approval.
Its completed record remains consumed. The command examples below document that
original allocation; they do not authorize another run. The fresh schema-check
allocation has its own preparation guide above. Neither path starts a backend
server or uses the browser's four-agent Begin trial action.

## Exact scope

- Existing Microsoft Agent Framework Evidence Agent, corrected role instructions,
  `EvidenceSubmission` schema and unchanged grounding validator.
- Deployment name `gpt-4.1-mini`, using the saved project-root Azure configuration.
- `synthetic-101-missed_opportunity-away-3218`: the away missed opportunity at
  **53:38**, with completed evidence cutoff **55:08** (3308 seconds).
- Exact canonical input fingerprint:
  `731856a6c450ae9bf52e6a9867e51b7cf955dcb46160382d2d41ba43131ca409`.
  Changed facts fail closed before any request or diagnostic record.
- The one-node workflow creates only Evidence. It has no graph edges, no
  Prosecution, Defense or Judge instances, and no next handoff.

The normal trial and diagnostic share the same agent factory logic, response
hooks, schema parsing and grounding checks. `execute_trial` retains its original
four-node graph; `execute_evidence_diagnostic` uses only the terminal Evidence
node and hard-clamps the per-run call limit to one.

## Commands from the project root

Safe default (no model request, no `.env` read, no record or ledger write):

```bash
PYTHONPATH=backend .venv/phase4b/bin/python -m app.diagnose_evidence
```

**Later, only after explicit approval**, run this exact command once:

```bash
PYTHONPATH=backend .venv/phase4b/bin/python -m app.diagnose_evidence --live
```

There are no CLI switches for arbitrary cases, repeat/force/reset, arbitrary
prompts, credentials, endpoints or running the full trial. The fixed
`--schema-check` selector is the separately prepared allocation above. Do not substitute the
Phase 4A connection probe or the normal courtroom endpoint.

The live command privately reads the root `.env` without interpolation. Missing
saved credentials/configuration block execution rather than falling back to
inherited credentials. It requires the GPT-4.1 mini deployment name and validates
the existing Azure resource endpoint through `FoundrySettings`.

Only that short-lived CLI process gets:

- the dedicated `EVIDENCE_DIAGNOSTIC_LIVE_ENABLED=true` permission;
- `FOUNDRY_LIVE_ENABLED=true`, while **`COURTROOM_LIVE_ENABLED=false`**;
- a 120-second timeout and zero retries.

No `.env` edits or shell exports are needed. Environment overrides are restored
when `main` returns; a normal CLI invocation then exits. Importing modules or
running the default command never enables AI.

## Cost and duplicate protection

- Maximum **one Azure model attempt**, enforced before every physical send. A
  duplicate SDK/framework call is blocked before another send or reservation.
- The existing Evidence output budget is retained (currently 768 tokens).
  Smaller configured limits and a zero per-trial limit remain effective.
- Zero SDK retries, no tools/function calls, no background response, verified
  TLS, no redirects/proxy environment, and `store=false`.
- The existing shared `.logs/foundry-usage.json` is read to determine today's
  usage. The effective cap is the **minimum of the configured daily cap and
  current UTC-day usage plus one**. The original locked budget implementation
  reserves the attempt without resetting/deleting the ledger. At the previously
  observed count of four and configured cap of ten, this would permit one
  request with an effective cap of five. Usage is recalculated at execution.
- A separate `.logs/evidence-diagnostics/<hash>.json` record is written before
  any model call. Its identity is fixed for this evidence-only diagnostic and
  does not change with prompt/config settings. Existing completed, failed,
  in-progress or unreadable records block repeat generation. Nonblocking file
  locks prevent concurrent invocations from consuming another request.
- Cancellation/crash preserves an in-progress record. Its initial attempt count
  must not be treated as proof that Azure was never reached. The original
  ledger and the record's usage-before metadata remain available for review.
- The original `.logs/courtroom/` failed trial is never cleared or rewritten.
  This is a separately approved diagnostic of the same evidence, not a retry of
  the blocked four-agent trial, a cache migration or a production cache update.

Using the Global GPT-4.1 mini retail rates verified in the preceding review
($0.40 per million input tokens, $1.60 per million output tokens), roughly
12,000–14,000 input tokens and up to 768 output tokens cost about **$0.006–$0.007**.
Allow approximately **$0.005–$0.01** for this case, depending on actual output,
region/SKU and account pricing. This is an estimate, not a dollar-denominated
hard limit or a verified account-specific bill. Provider token usage is captured
when returned. Failed/filtered/incomplete generation may still be billable.

Pricing source: [Microsoft public retail API](https://prices.azure.com/api/retail/prices?$filter=productName%20eq%20%27Azure%20OpenAI%27%20and%20contains%28skuName%2C%20%274.1%20mini%27%29%20and%20armRegionName%20eq%20%27eastus2%27&currencyCode=USD).
No pricing or other Azure request was made while preparing this harness.

## Sanitized results

The command emits metadata-only JSON and writes a private atomic record. It
includes HTTP status, actual attempt count, completion/incomplete reason,
provider input/output/total token usage when available, failure stage and fixed
validation reason, byte counts, output limit, evidence/input/prompt fingerprints
and the Evidence execution trace. Successful structured output is validated in
memory and represented by a digest; its text is not printed or saved.

No raw or validated model prose, prompts, provider error messages, response
headers, credentials, endpoints or sensitive environment values are logged.
Dependency logging is suppressed during the live CLI branch. Unknown provider
metadata is reduced to fixed safe values. An unexpected interruption can leave
usage/status unknown; the report does not claim zero charges in that case.

Success means Evidence passed the existing schema and grounding checks. It does
not claim that the original failure is explained, that all prose is semantically
correct, or that the other three agents are ready for a paid retry. Invalid
citations, numeric prose, malformed output and truncation remain failures.

## Mocked validation

```bash
COURTROOM_LIVE_ENABLED=false FOUNDRY_LIVE_ENABLED=false PYTHONPATH=backend .venv/phase4b/bin/python -m pytest -q backend/tests/test_evidence_diagnostic.py backend/tests/test_courtroom.py
```

Tests use the real framework and SDK over MockTransport with fake credentials,
forbid real sockets and use temporary ledgers/cache directories. Coverage
includes valid output; malformed output; citation violations; truncation/usage;
DNS, timeout, authentication and provider failures; no extra agents or edges;
duplicate calls; concurrent runs; cancellation; daily limits; changed-evidence
blocking; default no-op; and private CLI configuration/restoration. Live-flag
parser tests replace the runner and use only a temporary fake `.env`.

Remaining risks are provider authentication/quota, latency, truncation and model
compliance. No live attempt has tested the corrected prompt. Keep all original
records intact and review the sanitized diagnostic before approving more work.
