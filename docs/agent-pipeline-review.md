# Offline agent pipeline reliability review

2026-10-19. No Azure/resource/pricing requests, live server, new diagnostic
allocation, ledger reset, failed-case unblock, deployment or `.env` change.

## Evidence from the attempts

The original isolated Evidence submission completed and validated. A later
four-agent attempt stopped at an unknown fact reference. The newest diagnostic
received HTTP 200 but `incomplete/max_output_tokens`: 19,213 input and 768 output
tokens. Its record contains no raw output, so the precise content causing that
verbosity cannot be reconstructed. Truncation is confirmed; a framework bug or
full-catalog echo is not established.

The old model task copied data that Python already knew: up to eight exact
observations, top-level event references, and another set of fact/event
references inside the interpretation. These limits permitted output much larger
than the token ceiling. The provider schema cannot enforce Azure-unsupported
length/array bounds, even though local validation enforces them after response.
Giving the model a large, repetitive catalog and asking it to copy references
in several places created unnecessary copying and generation work.

Inspection and mocked interception show one model request per role, no tools,
no SDK retries and no hidden repair loop. The framework serializes the schema
and parses a structured response; there is no evidence it appends a verbose
Evidence essay. The prior per-role physical-send guard remains in place.

## Revised responsibilities

Python continues to build the immutable VerifiedEvidence using closed case
windows. No original fact, cutoff, event or statistic changes.

Evidence now receives **every verified fact's ID, label and exact value**, all
complete trigger records (omitting only null fields), case metadata and cutoff,
and limitations. It does not need the entire replay to prioritize this catalog.
Supporting references stay authoritative in Python. Its explicit role is
selection and explanation, not a claim to independently audit every event.

The private `EvidenceSelection` contract contains:

- `fact_ids`: one to three existing IDs, in priority order (prefer one).
- `explanation`: 8–240 characters, preferably a short sentence.
- `uncertainty`: 12–180 characters, preferably a short cautious sentence.

Python rejects unknown or duplicate selections before lookup. It constructs
the existing public EvidenceSubmission using exact values, mandatory trigger
references and bounded authorized support citations. The deterministic citation
sample includes a representative reference from each selected nonempty fact,
then further support in catalog order, up to twelve interpretation citations.
It does not alter the underlying facts' complete supporting-event lists.
No-support selections fail closed. Unknown IDs are never repaired, aliased or
substituted. The unchanged canonical Pydantic and grounding validator validate
the constructed submission, including narrative restrictions and exact values.

Prosecution, Defense and Judge receive a **lossless compact view** of the same
canonical file: repeated fact support lists are stored once in support_groups;
facts reference the group; null event fields are omitted. Tests reconstruct the
original VerifiedEvidence exactly for every built-in case. All events, fact
values, labels, support IDs, cutoff and limitations remain available to them.
Defense still receives prosecution; Judge receives both opposing arguments and
the validated Evidence submission. No raw model response is used as a handoff.

The public API, five-stage cinematic UI, voting and evidence citations keep the
same shape. Evidence remains a real model-backed prioritization/explanation
agent; its output influences all subsequent arguments and ruling. There is no
second judge, frontend redesign or synthetic-engine change.

## Measured size changes

Captured with the installed real Agent Framework and SDK over MockTransport,
fake credentials and temporary runtime records. Bytes are UTF-8 compact JSON;
the complete request includes instructions and the serialized response schema.

| Case | Evidence payload before → after | Full Evidence request before → after | Reduction |
| --- | ---: | ---: | ---: |
| synthetic-101 away, 53:38 | 33,591 → 4,492 | 43,674 → 8,283 | 81.0% |
| synthetic-202 away, 31:50 | 44,471 → 4,561 | 55,794 → 8,352 | 85.0% |
| synthetic-202 home, 75:55 | 54,122 → 4,554 | 66,589 → 8,345 | 87.5% |

For the most recent case, all four mocked requests together fall from 257,114
to 113,785 bytes (55.7%). Downstream output lengths will affect their actual
request sizes. Evidence previously received 101 events, 33 facts with heavily
repeated support lists, and hundreds of null event fields. None of that
reference-copying work remains in its model task.

The short mocked selection is 206 bytes. A reasonable expected English
selection is roughly 100–250 output tokens; this is an estimate, not a model
measurement or a token guarantee. Using the last actual provider input count
and byte ratio suggests roughly 2,000–3,000 input tokens for the new Evidence
request; no tokenizer is installed and no download/request was made, so only
the byte reduction is directly measured. The ceiling stays **768 tokens**.
Three long IDs, less concise text, Unicode or a nonconforming response can
still hit a budget or fail local bounds. No automatic retries are introduced.

## Schema and cost safeguards

All four agents now use the outbound-only Azure schema normalizer, not just
Evidence. Unsupported string/array bounds are omitted only from advertised
schemas; local model validators retain them. Single-value `const` constraints
on the Judge's literal fields become equivalent single-value enums on the wire.
Strict mode, required fields, closed objects, types and references remain.
Evidence advertises the current case's authorized IDs as an enum once in its
selection field. Intercepted requests for every role are tested against the
documented supported keyword set, object/property/nesting requirements.

No daily caps, request counters, timeouts, per-trial call limits, duplicate-send
guards, live gates or fallback rules change. The shared ledger is preserved.
Canonical public evidence/output acceptance remains compatible, so existing
completed caches remain revalidated and failed/in-progress records stay
blocked under their original identities; no cache-version bump bypasses them.
Trace input fingerprints now identify actual compact role payloads. Historical
diagnostic input guards still identify canonical evidence, not a newly granted
allocation. Both consumed diagnostics remain consumed.

## Risks and next steps

Validation: **409 backend tests and 128 frontend tests passed**. Complete mocked
trials cover all three previously attempted cases plus a substitution case.
Additional tests cover lossless downstream context for every built-in case,
all four outbound schemas, exact values/cutoffs, invalid and duplicate
selections, unsupported model-supplied record fields, unchanged public
string/array bounds, local prose/grounding rejection, and cache reuse. The
previous direct model-copy tests now exercise canonical validation separately
from the new private selection contract; the protections were not deleted.
Only the existing Starlette/AnyIO deprecation warning remains.

Hash checks confirm `.env`, existing logs/caches, consumed diagnostic records,
failed-case records and ledger unchanged. Usage remains seven on 2026-10-19;
no backend is listening on port 8000. Frontend source remains unchanged.

Offline mocks establish contracts, serialization and validation, not whether a
live model selects persuasive facts or follows brevity instructions. Grounding
establishes reference membership and exact values, not semantic proof of every
natural-language interpretation. Evidence intentionally relies on verified
aggregates and trigger records; subsequent agents retain the entire case.

Do not run or prepare another paid diagnostic as part of this review. First
review this architecture and its mocked complete-trial behavior. No fresh
diagnostic identity, command, live permission or runtime allocation is added.
