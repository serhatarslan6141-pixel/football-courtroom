import { VOTE_LABELS } from '../../domain/courtroom.js'
import { CourtSeal } from './CourtroomSet.jsx'
import EvidenceCitations from './EvidenceCitations.jsx'
import { isAiSource } from '../../domain/aiCourtroom.js'

export default function JudgeVerdict({ assessment, vote, onReturn, trial, onCite }) {
  const lead = assessment.findings.find((finding) => finding.id === assessment.leadFindingId)
  const additionalFindings = assessment.findings.filter((finding) => finding !== lead)
  return (
    <section className="judge-verdict" aria-labelledby="ruling-heading">
      <div className="ruling-stamp">
        <CourtSeal />
        <span>{isAiSource(assessment.source) ? 'AI JUDGE’S RULING' : 'PRELIMINARY RULING'}</span>
        <strong>{assessment.label.toUpperCase()}</strong>
      </div>
      <h2 id="ruling-heading">{assessment.headline}</h2>
      <p className="ruling-reason">{assessment.reason}</p>
      {lead && trial && <EvidenceCitations eventIds={lead.eventIds} trial={trial} onCite={onCite} />}
      {assessment.confidence && <p className="ruling-confidence">Confidence in this ruling: {assessment.confidence}</p>}
      {assessment.sides && <div className="judge-weighing">{assessment.sides.map((side) => <article key={side.name}>
        <h3>{side.name}</h3><p>{side.text}</p>
      </article>)}</div>}
      {additionalFindings.length ? (
        <div className="ruling-findings">
          <span className="trial-overline">{isAiSource(assessment.source) ? 'THE JUDGE’S FINDINGS · AI INTERPRETATIONS' : 'WHAT THE RECORD SUPPORTS'}</span>
          {additionalFindings.map((finding) => (
            <div key={finding.id}><p>
              <span aria-hidden="true">✓</span>
              {finding.text}
            </p>{trial && <EvidenceCitations eventIds={finding.eventIds} trial={trial} onCite={onCite} />}</div>
          ))}
        </div>
      ) : null}
      <details className="ruling-limits">
        <summary>{isAiSource(assessment.source) ? 'Uncertainty and limits of this ruling' : 'Why the court leaves it open'}</summary>
        {assessment.limitations.map((text) => (
          <p key={text}>{text}</p>
        ))}
      </details>
      <div className="recorded-vote">
        <span>YOUR OPINION</span>
        <strong>{VOTE_LABELS[vote]}</strong>
      </div>
      <small className="assessment-disclosure">{assessment.disclosure}</small>
      <button className="court-primary" type="button" onClick={onReturn}>
        Back to the replay <span aria-hidden="true">↗</span>
      </button>
    </section>
  )
}
