# Built-in trial coverage and controlled batches

Offline audit, 2026-10-21 UTC: **11 cases, one complete AI trial, six untried,
four blocked**. The existing successful result was revalidated and exported
without inference. Evidence-only success is not counted as a four-agent trial.

| Case ID | Type | Evidence cutoff | Status |
| --- | --- | --- | --- |
| synthetic-101-missed_opportunity-away-3218 | Missed opportunity | 55:08 | Blocked: failed trial |
| synthetic-202-missed_opportunity-away-1910 | Missed opportunity | 33:20 | Blocked: failed trial |
| synthetic-202-momentum_shift-home-2917 | Momentum shift | 51:37 | Missing |
| synthetic-202-substitution_impact-away-4027 | Substitution impact | 70:37 | Missing |
| synthetic-202-momentum_shift-home-4473 | Momentum shift | 77:33 | Missing |
| synthetic-202-missed_opportunity-home-4555 | Missed opportunity | 77:25 | Blocked: failed Evidence diagnostic |
| synthetic-303-momentum_shift-home-583 | Momentum shift | 12:43 | Missing |
| synthetic-303-missed_opportunity-home-1082 | Missed opportunity | 19:32 | Published successful AI trial |
| synthetic-303-momentum_shift-away-1157 | Momentum shift | 22:17 | Missing |
| synthetic-303-missed_opportunity-home-2412 | Missed opportunity | 41:42 | Blocked: failed trial |
| synthetic-303-substitution_impact-away-4187 | Substitution impact | 73:17 | Missing |

## Offline commands (project root)

```sh
PYTHONPATH=backend .venv/phase4b/bin/python -m app.batch_trials audit
PYTHONPATH=backend .venv/phase4b/bin/python -m app.batch_trials publish
```

Audit is read-only. Publish copies only fully validated completed four-agent
results to `backend/data/courtroom-trials/`, never overwriting artifacts or
changing the private cache. Missing/corrupt/failed records cannot become AI
results. `generate` without `--live` is disabled and does not load credentials.

## Later, only after explicit paid-generation approval

The smallest batch is one case / four attempts. Re-audit the UTC ledger first.
At preparation time it contains **6/10 attempts, four remaining**. Example for
that allowance (NOT executed during this milestone):

```sh
PYTHONPATH=backend .venv/phase4b/bin/python -m app.batch_trials generate --live \
  --batch-id builtin-coverage-01 \
  --case synthetic-303-momentum_shift-home-583 \
  --max-requests 4 --daily-cap 10 --max-estimated-usd 0.30
```

The CLI alone receives process-only live flags, a 120-second per-agent timeout,
four calls per trial, existing role output limits and zero retries. No live
server is needed. Settings come from the project-root `.env`, which is never
written. The CLI suppresses dependency logging and prints sanitized summaries.

Batch reservations are durable in `.logs/trial-batches/`; the global ledger
remains `.logs/foundry-usage.json`. Reusing the same batch ID requires identical
scope and ceilings on the same UTC day. Completed cases are skipped; interrupted
and failed cases stay blocked. A new failure stops the batch immediately. Resume
can publish a privately completed result without another call. New batches need
their own approval and enough existing daily allowance; no counters are reset.
Unmapped legacy records block generation instead of being ignored.

The cost allowance uses explicit planning rates (default **$0.44/M input,
$1.76/M output**, a previous Data Zone reference, NOT newly verified pricing).
It reserves one input token per permitted request byte plus a framing margin,
and the largest role output limit: **$0.250512 per four-call trial** at defaults.
It refuses a trial unless four full reservations fit. This is a conservative
estimate cap, not an Azure billing guarantee; verify actual region/SKU rates
before approval and pass higher rates if needed. Hard physical request and
daily ceilings remain independent. Typical cost should be substantially lower:
the prior complete trial used 30,996 input / 397 output tokens (~$0.013 at the
previous $0.40/$1.60 global reference). Six unblocked trials require up to **24
calls**, roughly **$0.10–$0.25** in total as a planning estimate. Failures stop
early and can still be billable. The other four cases cannot be completed under
the current failed-case restrictions (another 16 calls if separately authorized
and legitimately made eligible in future; no bypass is provided here).

## Visitor playback / eventual deployment

Ship `backend/data/courtroom-trials/` with the backend, or set
`COURTROOM_TRIAL_LIBRARY_DIR` to a persistent read-only directory. Keep
`FOUNDRY_LIVE_ENABLED=false` and `COURTROOM_LIVE_ENABLED=false` for public servers;
Azure keys are unnecessary for published playback. Restart an already-running
backend once to load the new code. Begin Trial returns the same cached API shape
inside the existing five stages; missing cases use recorded fallback. No new
frontend indicators or automatic generation were added.

Every read revalidates canonical evidence/cutoff, all submissions and four
handoffs/output fingerprints. Preserve private `.logs` on any generator host;
never ship credentials or private ledgers as public assets. Library JSON is
public synthetic content only, not a public raw-response/log export.
