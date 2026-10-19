# Phase 4C: one agent-powered courtroom

The synthetic match engine supplies the facts. Four Microsoft Agent Framework
agents interpret those facts. The existing purple/gold courtroom displays their
work in five stages: **The Case → Evidence → Both Sides → Your Verdict → The
Ruling**. There is one room, one pair of podium panels and one judge. The standalone
AI generation control and recorded-versus-AI chooser have been removed.

## What Begin trial does

Opening a case shows its introduction and **Begin trial**, without requesting
trial preparation or inference. Only clicking Begin trial starts this flow:

1. The frontend posts the integer replay entry position to
   `POST /api/matches/{match_id}/cases/{case_id}/courtroom/prepare`.
   This strict contract accepts only `through_timestamp`; it rejects `allow_live`
   and prompts. The preparation path cannot execute the model workflow, reserve
   daily budget or write an inference tombstone.
2. If either backend live switch is disabled, preparation returns deterministic
   fallback. The Evidence stage opens automatically, labeled **Deterministic
   fallback**. No confirmation or generation request is made.
3. With both live switches enabled and valid configuration, a completed matching
   cache record is validated and returned as **Cached AI analysis**, with zero
   new model attempts. Evidence opens directly without charge confirmation.
4. An enabled case without a cache record returns `confirmation_required`.
   A native modal explains that generation may incur a small Azure API charge,
   using up to four model requests. **Cancel** (or Escape) returns to the case
   without generation. Clicking Begin again reopens confirmation without
   repeating preparation.
5. Only **Confirm & begin trial** posts to the existing `/courtroom` endpoint
   with `allow_live: true`. While the agents work, Begin is disabled, generic
   progress is honest, and the trial remains at the introduction. The endpoint
   does not stream individual agent progress. On completion, Evidence opens
   with **Live AI analysis**; a backend cache race can instead return cached AI.
6. A disabled switch, failed/incomplete trial record, invalid cache, unavailable
   backend, network failure or invalid output uses the same deterministic
   proceeding. No partial AI ruling is presented and no automatic retry occurs.

The frontend never loads or enables backend live configuration. It sends neither
free-text prompts nor the user's vote. The backend rechecks both live switches
and all original limits when a confirmed request arrives. A switch changed after
preparation therefore still blocks generation. Disabled mode also respects the
existing kill-switch behavior of withholding cached AI.

## Content in the existing five stages

| Stage / area | Content |
| --- | --- |
| The Case | Existing cinematic case question, Begin trial, and the charge confirmation only when necessary |
| Evidence | Original pitch replay and match timestamps; verified Evidence Agent findings, with its interpretation separately labeled |
| Both Sides | The existing prosecution and defense podiums select the respective agents' arguments, uncertainty and clickable supporting facts |
| Your Verdict | Independent user choice; the judge's finding remains absent from rendered content |
| The Ruling | One judge component presents the agent ruling, reasoning, findings, confidence and uncertainty after the user records a vote |
| Behind the verdict | Small initially closed disclosure: actual execution status, ordered handoffs, validated evidence references, fingerprints and attempt counts |

Fallback uses the same components with deterministic recorded submissions and an
explicitly disclosed inconclusive assessment. Provenance is a compact label,
not another trial or mode selector. Session reuse retains original provenance;
only a backend cache response receives the cached label.

The trace never invents completed agents. Without a trace it labels roles as a
planned workflow. Partial failed outputs and their references remain withheld.
Judge reasoning and judge-specific evidence references remain sealed before the
user votes, including inside Behind the verdict. Input/output fingerprints
identify handoffs without displaying prompts or raw model output.

## Cost and state safeguards

`MatchSessionProvider.beginTrial` and `confirmTrial` are event handlers, never
effects. Separate synchronous per-case locks protect preparation and confirmed
generation before React can disable buttons. State records preparation,
confirmation, cancellation, generation, ready, fallback and error, keyed by
match, case, seed and evidence bounds. Navigation, StrictMode, rerenders and
replay cannot submit work. Returning to a case reuses its session result; failed
requests are not retried in that session.

The backend's durable cache, single-flight locks, incomplete/failed tombstones,
daily ledger, conservative role budgets and per-trial limit remain authoritative.
Preparation does not consume model allowance. Confirmed generation still has
zero SDK retries. A fresh complete trial normally makes four model calls; a
cached trial makes none. A browser timeout may have reached Azure, so the UI
does not infer zero usage from a network error.

Trial results stay scoped to the original case. A late response cannot advance
another case or reset an ongoing stage, evidence cursor or vote. The source
adapter supplies one assessment to the existing judge; it never overwrites the
user's opinion or bypasses vote gating.

## Evidence and replay boundaries

`domain/aiCourtroom.js` checks match/case identity, seed, incident time and exact
window; the complete event file against local records; fact values and their
references; supporting references for agent interpretations; actual trace order,
source/attempt metadata, opposing stances and uncertainty fields.

Invalid references reject the whole response. The backend computes match facts;
the frontend verifies their relationship to the authorized local record. Neither
layer proves every natural-language interpretation semantically correct.

Citation buttons in arguments, evidence, the unsealed ruling and the trace seek
the bounded Evidence replay to the completed event. They never seek outside the
case window or replace the synthetic log. Leaving court restores the exact
original match replay position, paused. The simulator is unchanged.

## Local testing without Azure charges

Prepare dependencies as described in the README, then run from the project root:

```bash
./scripts/start-dev.sh
```

Alternatively run `./scripts/start-backend.sh` and `npm run dev` in `frontend/`
in separate terminals. Scripts use the Python 3.12 framework environment and do
not load `.env` or enable AI. Keep `FOUNDRY_LIVE_ENABLED` and
`COURTROOM_LIVE_ENABLED` disabled for normal development. Existing `/api` proxy
and `VITE_API_BASE_URL` conventions remain. Never put Azure credentials in
frontend variables.

Seek until a case is eligible, open it and click Begin trial. With switches
disabled, verify automatic fallback, the five stages, independent voting,
clickable citations and exact paused return position. Confirmation, live/cached
content and failures are tested with mocked responses, never Azure:

```bash
cd frontend
npm test
npm run lint
npm run build
cd ..
COURTROOM_LIVE_ENABLED=false FOUNDRY_LIVE_ENABLED=false PYTHONPATH=backend .venv/phase4b/bin/python -m pytest -q backend/tests
```

Frontend tests cover explicit Begin/confirmation, cancellation, duplicate clicks,
StrictMode, cache reuse, disabled/failed preparation, grounding, source labels,
traces, sealed judging, voting, replay and late responses. Backend tests run the
actual framework with MockTransport and forbid real sockets. They verify that
preparation cannot invoke the workflow or reserve budget, and test cache,
kill-switch, API validation and duplicate/budget protections. Mocked Chrome
journeys cover desktop/mobile, native dialog focus/Escape, all five stages and
replay preservation with nonlocal requests blocked.

## Safest later controlled live trial

No live inference was run during this implementation or its tests. After separate
explicit approval:

1. Follow [Phase 4B](phase4b.md#controlled-live-trial-later) to load credentials
   privately into only the backend process. Enable both switches only there.
2. Verify deployment, role budgets, zero retries, maximum four model calls and
   remaining daily allowance. Select one eligible case.
3. Click Begin trial. A cache hit costs no new requests; otherwise review the
   charge dialog and explicitly choose Confirm & begin trial once.
4. Do not refresh, duplicate tabs or reset cache/ledger while pending. Inspect
   source, citations and actual trace. Stop on failure before authorizing more.
5. Stop the enabled backend afterward. No `.env` edit is needed.

## Remaining limitations

- No streaming or cancellation of an already confirmed workflow. Navigating away
  may leave it running; navigation never resubmits it.
- Frontend votes and locks last for the mounted session, not across tabs/reloads.
  Backend records remain authoritative; every new uncached billable generation
  still requires confirmation in the UI.
- Failed/disabled cases are not regenerated in the same mounted session.
- Live four-agent quality remains unverified. Truncation or invalid grounding can
  still produce fallback.
- This remains a local demo using POSIX locks, without public billable-service
  authentication/rate limiting. Public live hosting needs a separate review.
