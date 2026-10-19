# Phase 4C: the AI courtroom experience

The existing purple/gold courtroom now consumes the Phase 4B trial response.
Its five stages remain: The case → Evidence → Both sides → Your verdict → The
ruling. The match engine and backend inference implementation are unchanged.
No live inference was used to implement or test this phase.

## Explicit generation and cost protection

Open an eligible case and choose **Generate AI Trial**. This is the only frontend
action that calls `POST /api/matches/{match_id}/cases/{case_id}/courtroom` with
`allow_live: true` and the integer replay position at courtroom entry. It sends
neither a free-text prompt nor the user's vote. It cannot enable backend live
switches. With the usual disabled configuration, this returns a recorded-evidence
fallback with no Azure request.

`MatchSessionProvider.generateAiTrial` runs directly from the click handler,
never an effect. A synchronous ref locks before React renders a disabled button.
Reducer state tracks loading, ready, fallback and error, keyed by match, case,
seed and evidence bounds. Rerenders, StrictMode effect replay, navigation and
evidence playback cannot generate automatically. Returning to the same case
reuses its session result. Late responses stay scoped to their original case.

There is only one generation submission per case identity in the mounted browser
session, including failed submissions. A network failure may have reached Azure,
so there is no automatic retry, polling or regeneration button. Reloading resets
browser state; the backend's durable cache, locks, failed/incomplete records and
daily budget remain the final protection against duplicate model calls.

While loading, users can continue the recorded trial. The endpoint does not
stream individual progress, so the UI shows only honest generic progress. No
timers or invented agent completions are used.

## Presentation and independent voting

| Area | Behavior |
| --- | --- |
| Header | Generation action, source badge and planned four-agent order |
| Evidence | Existing replay, verified fact/value cards and a separately labeled Evidence-agent interpretation |
| Both sides | Opposing submissions, uncertainty, verified quantities and clickable citations |
| Your verdict | Existing session vote, independent of AI generation and judgment |
| The ruling | Findings, assessments of both sides, confidence and uncertainty, shown after a recorded vote |
| How the AI reached this decision | Collapsible actual trace, handoffs, validation status, fingerprints and request counts |

Source labels come from the response: `live_ai` → **Live AI trial**, `cached_ai`
→ **Cached AI trial**, and `deterministic_fallback` → **Recorded-evidence
fallback**. Session reuse retains the original source; the browser does not
relabel it as a backend cache hit. Cached traces describe original generation
and explicitly show zero new model attempts. Failures retain the existing
deterministic arguments and inconclusive assessment. Partial AI outputs are
never presented as the ruling.

Generation does not change the trial stage, unlock the ruling, reset a vote or
send that vote to a model. Generating after voting retains the opinion even if
the AI judge disagrees. Before voting, neither the AI judge's result nor its
reasoning is rendered, including inside trace details.

## Evidence boundary and citations

`domain/aiCourtroom.js` adapts responses to the existing presentation model. It
checks match/case identity, available seed, incident time and exact window; a
complete unique event file against the local log; fact references and selected
values; event references belonging to cited facts; trace order, source/attempt
metadata, opposing stances and the ruling's uncertainty fields.

An invalid reference rejects the response rather than trimming citations while
retaining an unsupported claim. The backend computes statistical facts; the
frontend checks their connection to the local case record. Neither layer proves
all natural-language reasoning semantically correct. Raw JSON, internal IDs,
prompts and credentials are not used as courtroom copy.

Citation buttons show event type and match time. Selecting one opens the existing
Evidence stage at that completed event, pauses its playback and identifies the
cited moment. Both the adapter and component enforce case bounds. Larger lists
are expandable. The pitch uses the original event log; model text never replaces
it. The evidence cursor remains separate from the match cursor, so leaving court
restores the exact original replay position, paused.

## Local testing without Azure charges

After preparing the Python 3.12 environment and frontend dependencies described
in the README, run from the project root:

```bash
./scripts/start-dev.sh
```

Alternatively, run `./scripts/start-backend.sh` and `npm run dev` from `frontend/`
in separate terminals. The scripts do not load `.env` or enable AI. Keep both
backend live switches disabled for ordinary manual testing. Existing `/api`
proxy and `VITE_API_BASE_URL` conventions are reused. Never put Azure credentials
in `VITE_` variables or send them from the browser.

Seek until a case is eligible, open it, and try Generate AI Trial with the backend
disabled. Verify fallback labeling, the five-stage journey, clickable citations,
separate voting and exact paused return position. Loading, success, cached and
error states can all be tested with mocked responses:

```bash
cd frontend
npm test
npm run lint
npm run build
cd ..
PYTHONPATH=backend .venv/phase4b/bin/python -m pytest -q backend/tests
```

New frontend tests mock every AI request. They cover explicit generation, rapid
duplicate clicks, StrictMode, source attribution, grounding, trace order, voting,
replay preservation, citations, late responses, fallback and sanitized errors.
Existing replay regressions use the local deterministic backend without
inference. Interaction tests and mocked desktop/mobile browser journeys cover
keyboard behavior, overflow and the complete flow. The production bundle has no
Azure credential fields or provider SDK.

## Safest later controlled live trial

No live trial was run here. After separate explicit approval:

1. Use the backend-only setup in [Phase 4B](phase4b.md#controlled-live-trial-later)
   to load credentials privately and enable both live switches only for that
   process. Keep frontend processes free of backend credentials.
2. Verify deployment, conservative role budgets, zero retries, a maximum of four
   calls and enough remaining daily allowance. Select one eligible match/case.
3. Click Generate AI Trial once. Do not refresh, duplicate tabs, resubmit or
   reset cache/ledger files while pending.
4. Inspect source, citations and trace. A fresh complete trial uses four model
   attempts; cached AI uses zero new attempts. On failure, stop and investigate
   the sanitized category before authorizing more generation.
5. Stop the enabled backend process afterward. No `.env` edits are required.

## Remaining limitations

- No streaming or cancellation/resume UI. Generation may continue after
  navigation; navigating never silently resubmits it.
- Votes, frontend locks and results last for the mounted browser session, not
  across tabs or reloads. The backend cache remains authoritative.
- A failed/disabled submission cannot be retried in the same case/session. This
  favors avoiding duplicate charges over one-click recovery.
- Live four-agent quality remains unverified. Truncation, invalid grounding or
  conservative wording checks may still produce fallback.
- The backend remains a local demo with POSIX file locking and no public
  billable-service authentication/rate-limiting layer. Public live hosting needs
  a separate security review.
