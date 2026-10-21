# synthetic-303 Prosecution failure: investigation and offline correction

No additional Azure request, retry, cache unblock, counter reset, `.env` edit or
live restart was performed. The completion watcher had already stopped backend
PID 19234; its log confirms completed shutdown. Frontend PID 19259 was stopped
with SIGTERM after project ownership was checked.

## Confirmed record

Case `synthetic-303-missed_opportunity-home-2412`, incident 40:12, evidence cutoff
41:42. The Evidence input fingerprint reconstructed from canonical facts equals
the recorded `2c87660655a0…`, confirming the simplified case/context path.

| Stage | Result |
| --- | --- |
| Evidence | Completed schema and grounding validation; handed to Prosecution |
| Prosecution | Schema parsing passed; grounding validation rejected the output |
| Defense / Judge | Not executed |

The failed record retains Prosecution's provider HTTP **200**, response status
**completed**, **8,921 input / 118 output / 9,039 total tokens**, and output limit
**1,024**. There was **no truncation**. Failure stage `grounding_validation`,
category `invalid_agent_output`, reason **`event_not_supported_by_fact`**.
Two total physical model attempts were reserved, with no retries. The ledger
remains `2026-10-21, count: 2` (eight under the saved cap ten, two under the
approved process cap four; unused allowance is not permission to retry).

The validator checks fact membership, then event membership, then the support
relationship. This reason therefore confirms that individually authorized IDs
were paired incorrectly: a cited event was not in the union of supporting
events for the point's selected facts. It is not a network/authentication,
provider-completion, output-budget or Pydantic schema failure. It is the first
recorded rejection; other unvalidated aspects of that model response are unknown.

The raw response and rejected IDs were not retained, so the exact point, IDs and
whether support-group indirection caused confusion cannot be recovered. The
Evidence token usage and exact provider HTTP status are also not retained:
the failure record stores only the active agent's sanitized provider metadata.
Do not sum the Prosecution token counts and present them as full-trial usage.
The local courtroom endpoint's HTTP 200 delivered fallback; the provider HTTP
200 is separately established by the diagnostic record.

## Why the contract was fragile

Prosecution had to generate both fact IDs and event IDs, resolving compact
support-group lists and preserving their relationship. It could produce valid
individual IDs with an invalid pairing. Its prompt asked for grounded support
but left reference reconstruction to the model. Defense's points and Judge's
findings used the same GroundedPoint contract and validator, so they had the
same latent risk; neither has a live failure recorded for this trial.

The old response contract also allowed multiple points and repeated reference
lists. However, this actual response was just 118 tokens. There is no evidence
of excessive generation, a need for more tokens, or a framework verbosity bug.
Input was 29,379 payload bytes / 35,617 full request bytes, below the input cap.
This fix does not trim case context or increase any output budget.

## Focused offline fix

- New private FactSelectedPoint contains interpretation and fact_ids, retaining
  the existing text and fact-array limits. ArgumentSelection/RulingSelection
  retain the existing stance, argument count, finding count, assessments,
  uncertainty, result, confidence and literal causation/counterfactual checks.
- Prosecution, Defense and Judge select authorized fact IDs (case-specific wire
  enums) and write reasoning. Their private schemas prohibit event_ids; prompts
  explicitly tell them not to copy event IDs from prior agent submissions.
- The same deterministic citation sampler used by Evidence constructs bounded
  supporting event references from those exact selected facts. Unknown or
  duplicate fact selections and empty support fail closed. No aliases, closest
  matches, record repair or replacement of model-supplied events is performed.
- Supplying event_ids in a private reasoning response is a schema failure,
  even if those IDs are individually known. This prevents silently repairing
  the confirmed failure pattern. The public canonical validator independently
  continues rejecting unsupported fact/event pairs.
- Public Argument/Ruling models, UI response shape, validated handoffs, complete
  compact case context, cutoff, cache identities, failed blocks, limits and
  fallback remain unchanged. All four wire schemas stay Azure-compatible.
- Output budgets remain Evidence 768, Prosecution 1024, Defense 1024, Judge 1536;
  zero retries, existing timeout and physical-send/daily guards are untouched.

## Offline evidence and next step

Twenty new regressions use the exact case with fake credentials, forbidden real
sockets, MockTransport and temporary records. A representative canonical output
reproduces the recorded grounding reason with individually known IDs; it is not
claimed to be the original missing response. Tests then verify deterministic
citations for all reasoning roles, private schema rejection of supplied events,
unknown/duplicate selections, numeric prose rejection, stopped handoffs, blocked
repeats and complete validated four-agent execution. The actual new mocked
FastAPI response passes the frontend presentation adapter with citations intact.

Validation completed: **431 backend tests and 128 frontend tests passed**,
including the 20 new regressions. The exact new mocked FastAPI response also
passes the frontend adapter with opposing arguments, ruling and citations.
Only the existing Starlette/AnyIO deprecation warning remains. Hash checks
confirm `.env`, the ledger, original logs, caches and failed/consumed records
unchanged. Ports 5173 and 8000 have no listeners.

We can continue development and review entirely offline without a full-trial
retry. These tests establish citation provenance by construction, not the live
model's interpretation quality or compliance with every other bound. No new
billable diagnostic or retry is prepared. The original failed case stays blocked;
any future paid verification requires a separately reviewed plan and approval.
