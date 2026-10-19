# Interactive courtroom — Step 3 and Phase 4C

[Phase 4C](phase4c.md) adds explicit four-agent generation to the flow below.
The recorded-evidence experience remains the default. A validated backend
response can supply AI interpretations and a judge ruling, with visible source
labels, clickable citations and an inspectable trace. The original replay and
independent voting rules are preserved.

The courtroom presents one eligible case as a five-stage trial: introduction → evidence → opposing submissions → user vote → preliminary ruling. Its room, bench and lecterns are SVG/CSS, with responsive layouts and reduced-motion support. The football simulator, API and case detectors are unchanged.

## Components and state

`CourtroomScene` composes reusable components in `frontend/src/components/courtroom`:

| Component | Responsibility |
| --- | --- |
| `CourtroomSet`, `JudgeBench`, `CounselPodium` | Physical room, central bench, opposing sides and the active speaker |
| `CaseIntroduction` | API case question, incident description and Begin trial |
| `TrialProgress` | Current stage and navigation to reached stages |
| `EvidencePlayer` | Recorded pitch replay, build-up/incident/aftermath clips, play/pause, restart, seeking and slow motion |
| `ArgumentHearing` | One case submission at a time; switch sides, advance submissions or inspect the incident |
| `UserVerdict` | Choose prosecution, defense or insufficient evidence, then explicitly record the vote |
| `JudgeVerdict` | Preliminary assessment, supporting findings, limitations and the separately labeled user opinion |

The existing context/reducer remains the state owner. `trialStage`, `trialFurthestStage` and `caseVotes` extend it; `evidenceTimestamp` and `courtroomReturnPosition` retain their original separate roles. Votes use a compound match/case key, survive fixture changes and repeat case visits, and last only for the current mounted session. They are not sent to a backend or persisted across a page refresh.

Opening a case freezes the match clock at its exact, possibly fractional cursor, invalidates pending replay responses and resets trial progress. A reducer guard prevents skipping directly to the ruling. Vote actions must name the active case and current match version. A recorded vote unlocks the ruling; choosing a button alone does not.

Evidence playback has its own local animation-frame transport and uses the shared **evidence** cursor. Unmounting that stage cancels its frame. It never dispatches match seeks or requests replacement match snapshots. Returning to the match retains its selected fixture, committed snapshot and exact cursor, with playback paused.

## Evidence and time boundaries

`domain/courtroom.js` is a pure presentation adapter over the existing API case and recorded events, not another match engine. It:

- Requires the maximum of detection time, availability and every observation-window end to be known before opening a case; invalid times and wrong-match cases are rejected.
- Limits the evidence file to the case's completed window, even if the match was opened later. The three clip ranges sit inside that file. Shared reducer guards also bound direct evidence seeks.
- Derives the **incident score** from completed goal records at the trigger time; the score at courtroom entry is not substituted for it.
- Reuses `PitchStage`, `EventCaption`, `Scorebug` and the existing motion/outcome whitelist. An evidence replay cannot expose the result of an action before that action completes. Replay statistics count completed clip events only.
- Builds prosecution submissions from case `evidence`, retaining their event citations. A missing/future/uncited reference causes the full submission to be withheld. If the supporting record is incomplete, both sides' submissions and ruling findings are withheld rather than patched with invented claims.
- Builds defense submissions from the case's own `counterevidence`. Values are paraphrased only to replace outcome codes, comparison shorthand and technical wording with plain language. No dialogue or extra football claims are generated.

Case-level submissions summarize the already eligible observation window; they are distinct from the evolving clip caption and statistics. Internal case/event IDs are retained as citations but never displayed as product copy.

## Preliminary assessment

The three current case questions concern significance or cause and effect. The available detector evidence can describe a spell of play, but does not establish those conclusions. The current assessment therefore returns **inconclusive**, with the actual supporting case facts and its limitations. A detector's `confidence: high` is not treated as a judge's confidence or a probability of causation. The user's vote has no influence on this assessment.

The result is labeled preliminary and explicitly described as an assessment from recorded evidence; no AI judge has evaluated it. Counterpoints are opposing submissions, not automatically accepted findings.

## Future response interface

The UI consumes a `TrialPresentation` v1 object produced by `createTrialPresentation`:

```text
version, source, caseId, question, label, summary, team,
incidentTimestamp, bounds {start, end}, knownEvents,
arguments {
  prosecution: [{id, title, text, context, eventIds, citation}],
  defense: [{id, title, text, eventIds, citation}]
},
assessment {
  source, result, label, headline, reason,
  findings: [{id, text, eventIds, citation}], limitations, disclosure
}
```

`citation` identifies the source evidence/counterevidence index; `eventIds` links recorded facts to the match log. Presentation components read these objects instead of knowing how submissions or assessments were produced. Ruling labels, explanations, findings and disclosure are data fields rather than agent-specific UI code.

Microsoft Foundry integration can later supply the two sides and judge assessment behind this boundary. That work still needs a backend response contract, agent prompts/orchestration, explicit source attribution, citation/cutoff validation, match/case request versioning, and loading/error/fallback handling. Supplied responses must never replace the session's recorded event log, eligibility rules or vote-before-ruling guard. No agent requests, credentials, SDKs or simulated agent responses are implemented in Step 3.

## Validation

Frontend tests cover the journey, all three votes, ruling gating, source citations, future/missing evidence, incident scoring, evidence playback and pause, exact return position, fixture-scoped votes and keyboard interaction. Cross-stack tests consume actual FastAPI case payloads. Browser checks run all stages at 1440×900 and 390×844, capture screenshots, check overflow and verify the exact paused match return.
