import { CourtSeal } from './CourtroomSet.jsx'

const messages = {
  introduction: 'The court is in session',
  evidence: 'Let the record speak',
  arguments: 'Every moment has two sides',
  vote: 'The floor is yours',
  verdict: 'A preliminary ruling',
}

export default function JudgeBench({ stage }) {
  return (
    <div className="judge-area" aria-label="Judge’s bench">
      <CourtSeal className="court-seal" />
      <span className="court-inscription">THE FOOTBALL COURT</span>
      <p>{messages[stage]}</p>
      <div className="judge-bench">
        <span>
          OBSERVE <i /> QUESTION <i /> DECIDE
        </span>
      </div>
    </div>
  )
}
