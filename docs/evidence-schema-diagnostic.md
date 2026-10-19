# Prepared one-shot Evidence schema diagnostic

**Historical allocation: now consumed.** The approved execution returned HTTP
200, `incomplete/max_output_tokens`, 19,213 input and 768 output tokens. Its
failed diagnostic record remains blocked. The preparation instructions below
are historical and must not be treated as permission or a fresh allocation.
See [the offline pipeline review](agent-pipeline-review.md) for the subsequent
architecture changes. No replacement diagnostic is prepared.

**Preparation only. Not executed against Azure.** A separate explicit approval
is required before using `--live`. No server/browser trial is involved.

## Fixed allocation and verified input

- Allocation: `evidence-schema-compatibility-v1`.
- Match: `synthetic-202`, Mossfield United vs Riverside Athletic.
- Case: `synthetic-202-missed_opportunity-home-4555`, home missed chance at
  **75:55**. Eligible at **77:25**.
- Closed evidence window: **74:25–77:25** (4465–4645 seconds).
- 101 events, 33 authorized server-built facts; compact initial payload 54,122
  bytes. Smallest remaining built-in controversy after excluding both failed
  trial cases. Fact support stays within the authorized window.
- Exact input fingerprint:
  `91469d18f2cb1eeaf02fb7928316d9c1c64b537c186d7648f940721356294e11`.
- At preparation no trial/diagnostic record exists for this case/allocation.
  The future command checks the full-trial identity before reserving a request
  and blocks if a trial record exists. It never clears or rewrites it.

The original diagnostic identity, both original failed-case records, caches and
ledger are unchanged. This is one new named allocation for a different eligible
case, not a retry, record migration, new prompt-based cache key, or reset. The
old command without `--schema-check` continues to address the original consumed
allocation and remains blocked. No arbitrary case/identity/force/reset arguments
are exposed by the CLI.

## Exact commands from the project root

Disabled default (tested; zero inference, no `.env` read or record reservation):

```bash
PYTHONPATH=backend .venv/phase4b/bin/python -m app.diagnose_evidence --schema-check
```

**Only after separate explicit approval**, execute once:

```bash
PYTHONPATH=backend .venv/phase4b/bin/python -m app.diagnose_evidence --schema-check --live
```

The future live command privately reads the saved project-root `.env`, uses
process-only live permission for this isolated CLI, keeps the full courtroom
live gate false, and sets a **120-second timeout and zero retries**. Only the
existing Microsoft Agent Framework Evidence Agent is constructed. Its request
uses the normalized Azure-compatible schema, both current-case fact-ID enums,
strict output and **768 output tokens**. A different saved Evidence budget
blocks this allocation instead of silently increasing it. All canonical local
Pydantic bounds, exact values, grounding and cutoff checks remain mandatory.

## Cost and allocation guards

On **2026-10-19 UTC**, the preserved ledger shows **6 used**, saved cap **10**,
and **4 remaining**. Capacity was checked before preparation. Execution reads
the ledger again and clamps this process's cap to `min(saved cap, used + 1)`
(currently **7**). No counter reset is needed. An exhausted budget blocks before
consuming this fresh diagnostic record. The ledger reserves each physical send
under its existing cross-process lock.

Maximum **one model attempt**; zero retries and no other agent/tool calls.
Before sending, a separate fixed diagnostic record is written under
`.logs/evidence-diagnostics/`. Any completed/failed/in-progress record blocks
another run, even after a prompt/schema change. Concurrent invocation is
blocked; a cancelled/crashed attempt leaves its allocation consumed for review.
Duplicate SDK sends are blocked before another reservation/network send.

Estimate: roughly **18,000–22,000 input tokens**, up to **768 output tokens**.
Using the previously checked Global rates of $0.40/M input and $1.60/M output,
approximately **$0.008–$0.010**; allow **$0.01–$0.02** depending on actual usage
and deployment/account pricing. This is an estimate, not a dollar hard cap.
No Azure pricing, resource, quota or inference request was made during this
preparation. Failed/filtered/incomplete model execution may still be billable.

## Sanitized evidence and offline verification

The command prints/preserves only sanitized HTTP status, provider completion or
incomplete reason, input/output/total token usage when returned, validation
stage/reason/field, execution fingerprints, one-agent trace and attempt counts.
Unknown references remain withheld. Raw response text, model reasoning,
credentials, headers, endpoint and sensitive `.env` values are not logged.

The exact new CLI branch is tested with a temporary fake `.env`, injected
MockTransport, forbidden real sockets, and temporary cache/ledger files.
Coverage includes successful output and normalized wire schema/enums; unknown
fact/event references; length violations, malformed/truncated output, DNS and
timeouts; no Prosecution/Defense/Judge creation or handoff; original-record
preservation; existing-trial blocking; exhausted budget; duplicate SDK sends;
concurrency; and blocked repeat execution. Shared original diagnostic tests
cover cancellation tombstones and bounded timeout behavior as well.

Validation: **17 new-allocation tests**, **22 original-allocation tests**, and
the **full 395-test backend suite** passed. The disabled default CLI was checked
without loading saved configuration. Hash verification confirms `.env`, ledger,
all pre-existing logs/caches and consumed records are unchanged; no backend was
started and no new production diagnostic record was created.

Remaining risks: the context is larger than the previous diagnostic, actual
model validity and server acceptance remain unverified, and this validates only
Evidence. A successful diagnostic does not establish compatibility or live
readiness of the other agents' schemas. Do not use the browser to run this
diagnostic or restart a live courtroom backend.
