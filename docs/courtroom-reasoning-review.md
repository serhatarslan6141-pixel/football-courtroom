# Case-specific judging and courtroom writing

Offline review after the successful synthetic-303 home missed-chance trial at
18:02, available at 19:32. No Azure requests or live servers were used.

## What encouraged excessive caution

The common prompt supplied a stock uncertainty sentence for every role to copy.
Prosecution was asked to explain match influence, while the actual allegation
asked whether the missed chance was significant. The Judge was not given
explicit case-specific standards separating an observable allegation from a
claim about a different final score. The successful response repeated causal
disclaimers and treated absent later attacking pressure as a reason to doubt
the significance of the original good-quality chance.

The UI compounded this by showing `judge.uncertainty` as the main ruling
explanation and attaching a causal-proof disclaimer to confidence. A substantive
finding appeared further down. This review does not establish the model's
internal reasoning; it identifies instructions and presentation that encouraged
the observed behavior.

## Revised decision criteria

| Case | Question to decide | Evidence and limits |
| --- | --- | --- |
| Missed opportunity | Was this a significant missed chance? | Recorded shot quality/outcome, buildup, and documented defensive pressure. A missed finish or lack of follow-up pressure does not erase the chance's quality. Missing pressure/angle information stays unknown. No final-score counterfactual is required. |
| Momentum shift | Does the window show a meaningful change in activity and control? | Both teams' shots, threats, forward moves, passing and documented possession changes. Account for unequal window lengths and contrary indicators. Passing counts do not measure possession time; a brief burst does not establish sustained dominance. |
| Substitution impact | What observable change followed the switch? | Before/after attacking activity, passing, threats, opponent activity and documented involvement of the incoming player. Account for unequal windows. Timing alone does not establish impact; an observed change does not establish that the substitute caused it. |

Every role receives the relevant criteria through its serialized instructions.
The Judge must select `prosecution_supported` when the allegation is better
supported, `defense_supported` when stronger contrary evidence or rebuttal
undermines it, and `inconclusive` for genuinely insufficient or balanced evidence.
No result is preferred in advance. Confidence and causal certainty are separate
from that decision; `causation_established=false` and
`counterfactual_outcome="unknown"` remain required for every verdict.

## Writing and presentation

- Evidence is a neutral analyst selecting up to three complementary facts and
  explaining their relevance. It may select the incident plus useful context
  rather than returning only the incident type.
- Prosecution leads with a concrete reason the allegation matters, connects it
  to selected facts, and acknowledges a precise weakness when needed.
- Defense challenges the prosecution's weakest inference and concedes strong
  observations honestly. Missing causal proof is not a universal rebuttal.
- Judge gives the decisive case-specific reason, weighs each side's strongest
  actual point, and separates the remaining limitation from the ruling.

Prompts no longer supply a stock uncertainty sentence. They ask each role for a
relevant gap, competing reading or scope limit without copying earlier wording.
Natural football terms replace instructions to say “the recorded player” or
talk about “threat metrics.” Generated prose still cannot invent numbers,
names, positioning, pressure, scoring probabilities or future evidence. Match
identity, exact facts and statistics remain deterministic presentation data.

The existing ruling stage now leads with the first validated Judge finding and
its clickable citations, displaying it once. Additional findings retain their
citations. Uncertainty and canonical limitations remain in the expandable
limits section. Confidence describes confidence in the ruling. The defense
support label now says “The case against the allegation,” avoiding an implied
criminal-proof standard. The five stages, sealed ruling, independent user
vote, visual design and replay behavior are unchanged.

## Validation and preservation

**462 backend tests and 135 frontend tests passed**, plus frontend lint and a
production build to a temporary directory. New mocked full-chain tests cover
each case type and every verdict, checking the actual serialized criteria,
unchanged schemas/budgets, deterministic citations, grounding, handoffs and
cache reuse. These prove the contracts allow decisive and open rulings without
causal claims; mocked verdicts are not evidence of a live model's judgment.
UI tests verify the lead finding appears once with citations, additional
findings remain visible, uncertainty is separate, and the user's vote remains
independent. Existing end-to-end, failure and cost-protection tests also pass.
The existing Starlette/AnyIO deprecation warning remains nonblocking.

No canonical facts, public schemas, validators, token ceilings, request limits,
cache version or failed-case identities changed. All 74 protected files,
including `.env` and every existing runtime record, passed hash preservation
checks. The ledger remains six attempts on 2026-10-21 UTC.

The successful demo cache was revalidated through the backend with sockets,
budget reservation and record writes forbidden, then through the updated
frontend adapter. It remains `cached_ai` with zero new attempts. Its original
text and **inconclusive** ruling are preserved; new prompts do not rewrite or
regenerate cached trials. Improved model writing applies to future separately
approved generations. Live instruction compliance and writing quality have not
been tested by this offline pass. No billable run or new diagnostic was prepared.
