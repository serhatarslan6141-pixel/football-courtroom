import BroadcastIcon from '../match/BroadcastIcon.jsx'

export default function CaseIntroduction({ trial, onBegin, busy = false, buttonRef }) {
  return (
    <section className="trial-introduction" aria-labelledby="trial-question">
      <h1 id="trial-question">{trial.question}</h1>
      <p>{trial.summary}</p>
      <button ref={buttonRef} className="court-primary" type="button" onClick={onBegin} disabled={busy}>
        {busy ? 'Preparing the court…' : 'Begin trial'} <BroadcastIcon name="arrow" />
      </button>
    </section>
  )
}
