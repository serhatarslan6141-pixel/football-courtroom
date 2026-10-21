import EvidenceCitations from './EvidenceCitations.jsx'
import { isAiSource } from '../../domain/aiCourtroom.js'

export default function VerifiedEvidenceFile({ trial, onCite }) {
  if (!trial.evidenceFacts?.length) return null
  return <section className="verified-evidence-file" aria-label="Verified case evidence">
    <div className="verified-file-heading"><span className="trial-overline">Verified match facts</span></div>
    <div className="verified-fact-list">{trial.evidenceFacts.map((fact) => <article key={fact.id}>
      <h3>{fact.title}</h3><p>{fact.text}</p>
      <EvidenceCitations eventIds={fact.eventIds} trial={trial} onCite={onCite} />
    </article>)}</div>
    {isAiSource(trial.source) && trial.evidenceInterpretation && <div className="evidence-agent-reading">
      <span className="trial-overline">EVIDENCE AGENT · AI INTERPRETATION</span>
      <p>{trial.evidenceInterpretation.text}</p><details className="evidence-reading-limits"><summary>Limits of this reading</summary><p>{trial.evidenceInterpretation.context}</p></details>
      <EvidenceCitations eventIds={trial.evidenceInterpretation.eventIds} trial={trial} onCite={onCite} />
    </div>}
  </section>
}
