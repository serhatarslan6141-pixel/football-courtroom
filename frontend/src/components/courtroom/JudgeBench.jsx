import { CourtSeal } from './CourtroomSet.jsx'

const messages = {
  introduction: 'The court is in session',
  evidence: 'The evidence before the court',
  arguments: 'Counsel, present your case',
  vote: 'The floor is yours',
  verdict: 'The court’s ruling',
}

export default function JudgeBench({ stage }) {
  return (
    <div className="judge-area" aria-label="Judge’s bench">
      <CourtSeal className="court-seal" />
      <p>{messages[stage]}</p>
      <div className="judge-bench" aria-hidden="true" />
    </div>
  )
}
