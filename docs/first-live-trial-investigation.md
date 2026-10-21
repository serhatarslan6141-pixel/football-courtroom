# First controlled live trial: failure investigation

Latest follow-up: the simplified synthetic-303 trial validated Evidence, then
Prosecution failed with `event_not_supported_by_fact` after HTTP 200 and a
completed 118-token response. Both servers are stopped. The [Prosecution
investigation](prosecution-failure-investigation.md) records the confirmed cause
and the offline-only extension of deterministic citations to opposing arguments
and Judge findings. No further Azure requests or failed-case unblocks occurred.

Latest: the second Evidence diagnostic hit its 768-token output ceiling. The
subsequent **offline-only architecture review** replaces model reconstruction
with fact selection and deterministic Python assembly, reduces context, and
normalizes outbound schemas for all agents. See [the review and size
measurements](agent-pipeline-review.md). No new paid diagnostic is prepared;
all existing failed/consumed records remain blocked.

A fresh, fixed Evidence-only schema diagnostic is now **prepared, not executed**
for the untried home missed chance in `synthetic-202` at 75:55. See
[the new diagnostic guide](evidence-schema-diagnostic.md) for the exact future
command, allocation, safeguards and 395-test backend verification. Existing
consumed diagnostic and failed-trial records remain unchanged. Execution still
requires separate explicit approval.

## Outbound Evidence schema compatibility correction (offline only)

Mock request interception confirmed that the case-specific fact-ID enums survive
Microsoft Agent Framework and SDK serialization. It also found `minLength`,
`maxLength`, `minItems` and `maxItems` on the wire. Microsoft lists these as
unsupported in Azure's structured-output subset. Earlier HTTP 200 responses do
not establish universal support for those keywords.

`evidence_wire_response_schema` now wraps the bounded Evidence response model
and normalizes only its `model_json_schema` serialization. A deep-copy transform
removes Azure's documented unsupported type-specific keywords from schema nodes,
including nested definitions/items. It does not edit property names or enum
values that happen to resemble keywords. The canonical local models are not
mutated, and the wrapper inherits their original Pydantic validation rules.

This applies only to Evidence in the full workflow and the isolated diagnostic;
the other agents' outbound schemas are outside this focused correction. It
retains both case-specific fact-ID enums, `strict: true`, all required fields,
types, `$defs`/`$ref`, and `additionalProperties: false`. Independent grounding,
cutoff, exact observation values, 768-token output limit and all cost/cache
protections remain unchanged. This correction alone is not a compatibility
sign-off for a complete four-agent trial.

Tests inspect the actual JSON under `text.format.schema` at MockTransport,
after framework/SDK serialization, rather than only checking a model-generated
schema. The Evidence request contains only the documented supported schema
keywords, has nine object properties and stays within the nesting limit.
Tests also cover nonmutation/idempotence, data values resembling keywords,
both enum fields, cross-case isolation, unknown-reference rejection and
twelve minimum/maximum string/array violations. Locally invalid responses still
fail at structured-output parsing before any handoff, despite the omitted
provider-side length/size keywords. The fixed diagnostic CLI is exercised only
with temporary records and a mocked transport; its existing production block
is never bypassed.

Validation passed **17 focused tests** and the **full 378-test backend suite**.
Only the existing Starlette/AnyIO deprecation warning was reported. Hash checks
confirmed `.env`, ledger, logs, caches and all preserved records unchanged;
today's usage remains six and no backend is listening on port 8000.
No live Azure request is needed to
verify serialization or local rejection. A new Evidence-only diagnostic still
requires its own prepared one-attempt identity and separate explicit approval;
the existing completed diagnostic cannot be reused or unblocked.

Reference: [Azure structured-output JSON Schema support and limitations](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs#json-schema-support-and-limitations).

## Latest follow-up: fact-reference reliability (offline only)

The separately approved `synthetic-202-missed_opportunity-away-1910` trial later
failed at Evidence grounding validation: HTTP 200, response `completed`,
15,298 input / 256 output tokens, `unknown_fact_reference`, one attempt and no
handoff. It was not truncated. The original `synthetic-101` failure remains a
separate incident with insufficient original metadata. Neither failed record
was reset or rewritten. The shared ledger remains at six for 2026-10-19.

The newest failure's exact rejected string and field were not retained. An ID
copying mistake or event/fact namespace confusion is plausible, not established.
The confirmed design weakness is that the previous provider schema allowed any
string in both fact-reference fields, leaving all membership checks until after
generation. Existing prompt instructions already required exact catalog IDs.

Targeted changes:

- Evidence's provider response schema now lists the current case's exact
  authorized fact IDs as JSON Schema enums in `observations[].fact_id` and
  `interpretation.fact_ids` items. Per-case schema creation does not mutate the
  shared models or another case's choices. Other agents' schemas are unchanged.
- The prompt explicitly distinguishes complete fact IDs from event IDs and
  labels, including the required catalog prefix on trigger facts.
- The runtime grounding validator remains authoritative. Invalid references
  are never repaired, substituted or mapped to a closest match. Even a mocked
  provider that violates its advertised enum still fails closed. The existing
  public schema, exact value checks, event/fact support checks, evidence cutoff,
  numeric-prose restrictions and 768-token budget are retained.
- Safe diagnostics retain the existing reason `unknown_fact_reference` and add
  an allowlisted `field`: `observations[].fact_id` versus
  `interpretation.fact_ids` (also argument/finding fields for other agents).
  `reference_kind` is only `event_id` when every unknown fact selection is a
  known event ID, otherwise `unknown`. No rejected IDs, raw prose, headers,
  prompts or sensitive configuration are recorded. Old records stay unchanged.

Context review: the selected case includes 81 events and 33 facts. The fact
catalog repeats five distinct supporting-event lists across those 33 facts:
16,858 serialized bytes versus 2,130 bytes for distinct lists. Events include
386 null fields. This redundancy may increase copying difficulty, but the
failure record cannot establish that it caused the rejection. No evidence is
removed or compacted in this fix. Local response-schema size rises from 1,268
to 3,167 bytes for authorized choices; no larger evidence catalog is added.

A selection-only Evidence contract could let the model select authorized fact
IDs and have the backend construct exact observations and bounded supporting
citations from the verified catalog. That avoids asking the model to reproduce
values and event IDs. It would require an explicit internal schema/adapter and
careful citation-bound tests. It is not implemented here: enum-constrained
selection within the existing contract is the smaller correction. Unknown IDs
must be rejected before any deterministic lookup in either design.

The cache configuration identity is intentionally retained: accepted grounded
content and public output shape are unchanged; generation choices are narrowed
to what validation already required. Existing completed caches are revalidated,
and both failed-case blocks remain effective. No ledger, daily/per-trial limits,
send hooks, timeout, retries, duplicate guards or live gates are changed.

Exact-case mocked regressions cover both bad-reference fields, mistyped IDs,
event IDs used as fact IDs, an actual other case's trigger fact, metadata
allowlisting, correct wire enums, case isolation, full validated handoffs,
blocked repeat generation and a terminal Evidence-only framework execution.
They use fake credentials, forbidden real sockets and temporary runtime files.

Validation for this correction: **364 backend tests passed**, **128 frontend
tests passed**, and **20 focused exact-case/reference-diagnostic tests passed**
after the final edits. Only the existing Starlette/AnyIO deprecation warning
was reported by backend pytest. Hash checks confirm `.env`, the ledger, both
failed-case records and all pre-existing runtime files remain unchanged. No
backend is listening on port 8000. No frontend source was modified.

Safest next verification is offline Evidence-only and full-workflow tests.
A future paid check should be a separately prepared, explicitly approved,
one-attempt Evidence-only diagnostic with a fresh diagnostic identity and the
same validation path. The existing diagnostic CLI is fixed to the already
completed `synthetic-101` diagnostic and must not be rerun/unblocked or presented
as a new `synthetic-202` harness. No live verification was performed for this fix.

Investigated on 2026-10-19. The controlled backend was stopped safely; its log
records a completed shutdown. No retry, Azure inference, `.env` edit, ledger
reset, cache deletion, deployment or live restart was performed during this
investigation.

## Confirmed evidence

- Match `synthetic-101`, missed opportunity for the away team at 53:38,
  available at 55:08. Exact case:
  `synthetic-101-missed_opportunity-away-3218`.
- The existing failed cache identity begins `a9ba95f5129d`. Reconstructing the
  canonical evidence and original configuration produces this same identity.
- The Evidence handoff input fingerprint begins `731856a6c450`, matching the
  user's original browser trace. Its validated output is withheld and there is
  no next handoff. This identifies the input; it does not preserve model text.
- The persisted record contains only `status: failed`,
  `error_category: invalid_agent_output`, and `api_attempts: 1`.
- Backend logs show one generation POST and HTTP 200 **from the local API**.
  This is the successful delivery of a fallback response, not proof of Azure's
  HTTP status. There is no retained provider traceback or response body.
- The live launch used Python 3.12.15, a 120-second timeout, zero retries, a
  four-call trial limit and a daily cap of seven. Usage increased from three to
  four attempts. The other agents did not run.
- The exact Evidence input contains 59 completed events and 33 verified facts.
  Its compact payload is 33,591 bytes. The reviewed equivalent serialized SDK
  request was approximately 40 KB, below the 128,000-byte ceiling. Since an
  attempt was reserved, the live request passed the HTTP-boundary size checks.

## What can and cannot be concluded

The Evidence rejection path is confirmed. Its exact cause remains **unknown**.
The old implementation maps provider incomplete/refusal responses, JSON/schema
parsing failures, and grounded-output validation failures to the same public
category. Agent Framework's structured `.value` parsing uses Pydantic; schema
failure therefore also appears under that category.

A provider response is likely given this classification, but its HTTP status
was not persisted. Normal DNS, authentication, timeout and API-error paths have
different categories. The available record cannot conclusively prove which
provider response arrived or establish authentication/model completion for this
attempt. The earlier successful metadata request does not prove that this
particular generation completed.

The original Evidence output ceiling was 768 tokens. Neither response usage nor
`incomplete_details` was retained, so truncation and sufficiency for the actual
answer cannot be established. Short valid mocked submissions fit; this is not
proof that the live answer fit. There is insufficient evidence to raise the
limit or alter prompts/grounding rules.

The request **may have been billable**. A local reservation is not a billing
receipt. Actual charging requires Azure usage/billing information; fallback does
not imply zero cost.

## Small diagnostic fix

Future failed records now retain:

- provider HTTP status and existing ordered trace/input fingerprints;
- failure stage and fixed validation-reason code;
- payload/request byte counts and configured output ceiling;
- allowlisted provider completion/incomplete reason and numeric token usage,
  when returned.

No prompts, raw model text, provider error messages, headers, credentials,
endpoints or Pydantic input values are added to records. Unrecognized provider
strings are reduced to `unknown`; malformed token counts are discarded. The
public response and frontend are unchanged. Invalid outputs remain withheld.

The cache configuration version is unchanged because this change only improves
diagnostics: prompts, schemas, token budgets, accepted content and cost guards
are unchanged. The original failed record remains in place and blocks a repeat
of the same trial identity. Legacy failure records remain readable and are never
rewritten merely to add unavailable diagnostics.

## Validation and future approval

Mocked regressions reproduce the observed one-attempt Evidence-only failure
pattern for several distinct causes; they do not claim to reproduce the missing
original model response. They distinguish truncation, refusal, schema failure,
citation/value rejection, numeric prose, authentication, DNS and timeout. They
also verify safe metadata allowlisting, one attempt/no handoff, blocked repeats,
legacy failure preservation and the original handoff fingerprint. Real model
sockets are forbidden and all test ledgers/caches are temporary.

A routine repeat live trial is not advisable yet. If original DevTools response
metadata is still available, inspect only its `http_status`, attempt count and
trace. Otherwise a separately approved diagnostic attempt would be needed to
learn the exact rejection reason. The updated response hook will capture safe
status/usage/incomplete metadata and the local validator will record its fixed
reason. Do not enable SDK debug/body logging to obtain these details.

## Follow-up: original browser metadata unavailable

The user checked the original tab's Fetch/XHR list after the failure. It contains
only failed match-list requests; the original courtroom response is absent.
Those later match-list failures are consistent with the backend being stopped
and cannot explain the earlier Evidence rejection. Do not refresh or retry the
trial to try to recreate the missing Network entry.

Further zero-cost tests use the exact 53:38 case, the real installed Microsoft
Agent Framework and Responses SDK, fake credentials, MockTransport and temporary
cache/ledger files. Real sockets are forbidden. Additional cases check:

- valid exact numeric values in typed observations are accepted and hand off;
- missing trigger references, future-event references and citations unsupported
  by their claimed facts are rejected before prosecution;
- incorrect value types, missing required fields, malformed JSON and overlong
  interpretations are rejected by structured parsing/schema validation;
- numeric words in prose are rejected by the existing explicit prose policy.

These tests leave production validation, prompts and the 768-token Evidence
budget unchanged. They establish that multiple distinct causes can produce the
same original browser symptoms; they cannot select the original cause without
its response metadata.

The safest immediate step is this mocked validation work. If a paid diagnostic
is later desired, propose and mock-test an isolated **Evidence-only, one-request**
diagnostic before seeking approval to execute it. It should have an explicitly
identified fresh diagnostic case/record, zero retries, a one-request allowance
above the then-current ledger usage and the sanitized diagnostics described
above. The normal Begin trial flow still runs the four-agent workflow; do not
use it as an automatic diagnostic retry. Never silently change configuration or
clear the original failed record to bypass its duplicate protection.

At investigation time the UTC ledger count is four. Three attempts remain under
the stopped controlled process's cap of seven; six remain under the saved cap of
ten. No live backend is running. A later complete four-agent trial needs a new
approved allowance calculated from the then-current ledger. Do not reset it or
remove the original tombstone to make another trial possible without approval.

## Focused Evidence prompt/schema/validator compatibility review

The original failure's exact cause is still unknown. A compatible output is
possible; there is no unavoidable contradiction that makes every Evidence
submission invalid. The review did identify concrete instruction gaps that
allowed reasonable readings of the prompt to produce rejected output:

| Area | Earlier instruction / gap | Actual contract and correction |
| --- | --- | --- |
| Output scope | "Build the evidence file" could invite a new event log or fact catalog | The server already builds `VerifiedEvidence`; the agent returns only `observations`, `event_ids`, `interpretation`, `uncertainty`. The prompt now names those fields and forbids rebuilding the file. |
| Values and statistics | "All free text is interpretation" did not identify the typed-data exception clearly | Observations copy an existing fact ID and its exact string value from the same entry, without recomputation or formatting. Only interpretation narrative and uncertainty are generated prose. |
| Trigger citations | "Cite the trigger event_ids" did not name their required location | Every trigger must appear in the **top-level** `event_ids`; an interpretation-only citation does not satisfy this rule. |
| Citation support | Valid IDs were described as authoritative without spelling out the cross-reference check | Interpretation event IDs must belong to the union of event IDs attached to its cited facts. Independent membership in the case is insufficient. This rule is now explicit. |
| Numeric prose | Numeric words were prohibited, but ordinary hedges can still contain them | The prompt now explicitly warns against phrases such as "one possible explanation" and gives an accepted uncertainty example. Validation is unchanged. |
| Uncertainty | "Include meaningful uncertainty" can lead to "causation cannot be proved" | The existing literal filter rejects `proved` even when negated. The prompt now lists its prohibited certainty words and supplies compatible wording. The filter was not weakened. |
| Cutoff / list size | Generic closed-window instructions did not distinguish a few citations from copying the event log | The prompt now names the supplied boundaries, requires existing supporting events, and says not to return the entire event log. The original case contains 59 events, while the top-level citation list permits at most 20. |

All Pydantic field/type/length requirements remain unchanged. The schema requires
1–8 observations, 1–20 top-level event IDs, a single interpretation object with
1–8 fact IDs and 1–12 event IDs, interpretation text of 8–600 characters, and
uncertainty of 12–500 characters. Extra keys are rejected. The prompt prefers a
single concise observation to fit the existing 768-token budget; it does not
change the allowed schema or increase that budget.

The prompt also prohibits names and causal claims in narrative. The current
lexical validator does not prove those semantic properties or establish that
all prose follows from the citations. Typed values and reference relationships
are checked exactly; narrative remains labeled interpretation. This limitation
does not identify why the original submission was rejected, and no speculative
semantic validator was added in this focused review.

The server constructs completed event records, timestamps, both-team window
statistics, exact fact values, fact-to-event relationships, trigger references
and limitations deterministically. The Evidence Agent selects relevant facts
and interprets them; it should not generate those underlying facts again.
Constructing its copied values and trigger list server-side is possible, but
changing the response contract to make the agent return only selections and
interpretation would be a larger follow-up. That refactor was not made here.

### Context size

The exact case payload remains 33,591 bytes: approximately 16.6 KB of event
records and 16.3 KB of facts. Its 33 fact-reference lists contain only five
distinct lists; repeated lists account for about 10,878 bytes. Event records
also contain 280 null fields. Names are present as verified data even though
they must not appear in generated prose. This is measurable redundancy and a
candidate for future lossless context compaction. It increases input cost and
copying burden, but it does not establish the cause of the original failure or
exceed the current request ceiling. Context was deliberately not restructured
as part of this prompt-only clarification.

### Cache and diagnostic safety

The cache namespace remains unchanged. The output contract and accepted
validation rules are unchanged, so already validated cached results remain
usable and existing failed identities stay blocked. No version rollover is
used to bypass the original failure record. Future failure diagnostics include
a hash of the exact role instructions, allowing prompt identification without
storing their text. Substantive future acceptance-policy changes need a separate
cache/version and retry-safety review.

New mocked regressions show that the recommended uncertainty wording and exact
numeric observation strings pass through all handoffs and cache reuse. They
also confirm that negated banned certainty words, numeric words in prose and
missing top-level trigger citations remain rejected. These tests verify prompt
example compatibility, not the likelihood that a live model follows it.

A single Evidence-only diagnostic is now a reasonable **next proposed paid
experiment**, provided an isolated one-request harness is first prepared and
mock-tested and then explicitly approved. It should use an explicitly approved
fresh diagnostic case/record, retain safe diagnostics, and never retry the
blocked original case or silently invoke the normal four-agent browser flow.
No such live request or harness startup was performed in this review.

## Evidence-only harness prepared

The isolated [Evidence-only diagnostic](evidence-only-diagnostic.md) is now
implemented with the same exact case/facts, corrected prompt, schema and
validator. It uses a one-node workflow and a separate durable diagnostic record;
the original failed trial remains blocked. The default command is a no-op, and
only a later explicitly approved `--live` invocation can permit one Evidence
request. Mocked tests cover isolation, successful output, parsing/grounding
failure, truncation, network failures, duplicate/concurrent calls, cancellation
and budget guards. No live diagnostic or live backend restart was performed.
