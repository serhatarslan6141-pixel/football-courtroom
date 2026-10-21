# Complete offline pipeline stabilization

2026-10-20 local / 2026-10-21 UTC. No Azure requests or live servers.

## Findings and changes

The preserved synthetic-303 failure confirms Evidence completed and Prosecution
received HTTP 200 with a completed response, then failed grounding with
`event_not_supported_by_fact`. Prosecution consumed 8,921 input and 118 output
tokens, below its 1,024-token ceiling. This was a reference relationship failure,
not truncation. The rejected raw response was not retained.

The implemented citation fix applies the same division of responsibilities to
all agents. Evidence selects up to three existing facts and explains relevance.
Prosecution, Defense and Judge select authorized fact IDs for their reasoning.
Python constructs exact values and event citations from the immutable case
catalog. Model-supplied event lists, unknown or duplicate fact selections, future
references and unsupported prose fail closed. No reference is silently repaired.
The independent canonical grounding validator still runs after construction.

This review found and corrected additional shared issues:

- Azure-compatible serialized schemas omit unsupported length/array keywords,
  leaving local limits invisible to the model. Every role now receives explicit
  field limits, concise output guidance and its actual token ceiling in its
  instructions. All local bounds remain enforced.
- Prosecution and Defense previously advertised both stances on the wire.
  Their outbound schemas now each advertise only the appropriate stance. The
  independent local stance validator continues rejecting a noncompliant response.
- Trial records previously retained only the last agent's provider metrics.
  New records retain allowlisted per-agent metadata on success and failure:
  HTTP/completion status, available token usage, request/payload sizes, prompt
  fingerprints, limits and sanitized failure stage/reason. No raw response,
  headers, credentials or sensitive settings are added. Historical records are
  untouched; their missing metrics cannot be recovered.
- HTTP status is cleared at each role boundary so a subsequent DNS/timeout or
  pre-send failure cannot incorrectly inherit an earlier agent's HTTP 200.
- The planned Evidence role label now accurately says “Prioritize verified
  facts”; the cinematic design and public API contract are unchanged.

## Budgets and contracts

All four exact outbound schemas were intercepted after real Microsoft Agent
Framework and OpenAI SDK serialization. Strict output, closed objects, required
fields, supported schema keywords, case-specific fact-ID enums and the Judge's
literal safeguards remain intact. Tests reject model-supplied citations, unknown
facts, incorrect stances, locally excessive arrays/text and disallowed prose.
The normalization changes only provider serialization, never canonical models.

Representative synthetic-303 rehearsal with three selected facts and short
opposing arguments, using the real framework and MockTransport:

| Agent | Input payload bytes | Complete request bytes | Mock output bytes | Output-token ceiling |
| --- | ---: | ---: | ---: | ---: |
| Evidence | 4,510 | 8,650 | 264 | 768 |
| Prosecution | 30,054 | 37,695 | 241 | 1,024 |
| Defense | 30,349 | 37,994 | 260 | 1,024 |
| Judge | 30,659 | 39,180 | 519 | 1,536 |

Bytes are measured; they are not model token usage. Actual generation length
and tokenizer counts remain unverified live. These short selections/arguments
should fit comfortably, but the schema's largest locally valid output can
still exceed a token ceiling. Concision instructions reduce this risk without
increasing budgets. Incomplete responses still stop safely, without repair.
Downstream roles retain the complete lossless case view for counterevidence;
Evidence receives the compact complete fact catalog and trigger records.

## Validation

- **452 backend tests passed**, including real-framework mocked full trials,
  every cautious Judge outcome, all role schemas, per-role local bounds,
  canonical grounding, truncation/network/provider failures, partial daily
  exhaustion, per-trial limits, physical duplicate sends, concurrent requests,
  cache revalidation/reuse and permanent failed-case blocks.
- **131 frontend tests passed**, including three new complete cross-stack tests.
  `backend/tests/export_courtroom.py` runs the actual framework over a mocked
  transport, exports real FastAPI success/cached/failure responses and forbids
  sockets. React consumes these in StrictMode through the five-stage courtroom.
  Tests verify evidence, both existing podiums, a sealed ruling until the vote,
  a defense vote independent of a prosecution-supported ruling, real handoffs,
  citation navigation within the evidence window, original replay-position
  restoration, no automatic generation and no generation on cache reuse.
  A rejected Defense response renders recorded fallback with no partial AI
  arguments or competing Judge ruling.
- Frontend lint and production build passed. Build output was written to a
  temporary directory, preserving existing generated artifacts.
- The existing Starlette/AnyIO deprecation warning remains nonblocking.

Run locally with no charges:

```sh
COURTROOM_LIVE_ENABLED=false FOUNDRY_LIVE_ENABLED=false PYTHONPATH=backend .venv/phase4b/bin/python -m pytest -q backend/tests
cd frontend
npm test
npm run lint
npm run build
```

The cross-stack test needs the documented Python 3.12 environment; frontend-only
installations skip that group if it is absent. It ran and passed here. Its fake
live flags exist only inside a socket-blocked fixture subprocess with temporary
ledgers/caches; it neither loads `.env` nor starts an HTTP server.

## Readiness and remaining risks

The complete offline pipeline is ready for a separately approved controlled
live trial. There is no remaining identified integration blocker. Mocks cannot
prove a live model will obey brevity/prose instructions or produce persuasive,
semantically correct reasoning; strict reference grounding does not establish
causation or semantic proof. Provider availability/quota are unverified in this
offline pass.

Before any future approval, choose a fresh eligible case, check the current UTC
ledger and cap that process at existing usage plus four, with retries zero,
bounded timeouts and the existing browser confirmation. Do not reuse or unblock
the failed synthetic-303 case. Maximum four physical attempts; any rejection
stops subsequent agents and produces recorded fallback. No automatic retry.

The current ledger remains **2 attempts on 2026-10-21 UTC**; no allowance was
changed or new trial allocated. Hash verification confirms `.env` and all
previous runtime files unchanged. No configuration-version bump, cache reset,
failed-case unblock, live restart, commit, push or deployment occurred.
