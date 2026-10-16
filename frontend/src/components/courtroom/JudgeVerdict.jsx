import { VOTE_LABELS } from '../../domain/courtroom.js'
import { CourtSeal } from './CourtroomSet.jsx'

export default function JudgeVerdict({ assessment, vote, onReturn }) {
  return (
    <section className="judge-verdict" aria-labelledby="ruling-heading">
      <div className="ruling-stamp">
        <CourtSeal />
        <span>PRELIMINARY RULING</span>
        <strong>{assessment.label.toUpperCase()}</strong>
      </div>
      <h2 id="ruling-heading">{assessment.headline}</h2>
      <p className="ruling-reason">{assessment.reason}</p>
      {assessment.findings.length ? (
        <div className="ruling-findings">
          <span className="trial-overline">WHAT THE RECORD SUPPORTS</span>
          {assessment.findings.map((finding) => (
            <p key={finding.id}>
              <span aria-hidden="true">✓</span>
              {finding.text}
            </p>
          ))}
        </div>
      ) : null}
      <details className="ruling-limits">
        <summary>Why the court leaves it open</summary>
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
