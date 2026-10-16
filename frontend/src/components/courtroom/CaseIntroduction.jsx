import { CourtSeal } from './CourtroomSet.jsx'
import BroadcastIcon from '../match/BroadcastIcon.jsx'

export default function CaseIntroduction({ trial, onBegin }) {
  return (
    <section className="trial-introduction" aria-labelledby="trial-question">
      <span className="trial-overline">{trial.label} · OPENING THE CASE</span>
      <h1 id="trial-question">{trial.question}</h1>
      <div className="case-question-rule">
        <span />
        <CourtSeal />
        <span />
      </div>
      <p>{trial.summary}</p>
      <button className="court-primary" type="button" onClick={onBegin}>
        Begin trial <BroadcastIcon name="arrow" />
      </button>
      <small>Examine the moment. Hear both sides. Make your call.</small>
    </section>
  )
}
