import { useState } from 'react'
import { VOTE_LABELS } from '../../domain/courtroom.js'

export default function UserVerdict({ vote, onVote }) {
  const [choice, setChoice] = useState(vote)
  return (
    <section className="user-verdict" aria-labelledby="vote-heading">
      <h2 id="vote-heading">
        You’ve heard the case.
        <br />
        Where do you stand?
      </h2>
      <p>Make your own call before the judge’s ruling is revealed.</p>
      <div className="vote-options" role="group" aria-label="Your verdict">
        {Object.entries(VOTE_LABELS).map(([value, label], index) => (
          <button
            key={value}
            type="button"
            className={`vote-option vote-${value}`}
            aria-pressed={choice === value}
            onClick={() => setChoice(value)}
          >
            <span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
            <strong>{label}</strong>
            <i aria-hidden="true">{choice === value ? '●' : '○'}</i>
          </button>
        ))}
      </div>
      <button
        className="court-primary"
        type="button"
        disabled={!choice}
        onClick={() => onVote(choice)}
      >
        Record my vote & hear the ruling <span aria-hidden="true">→</span>
      </button>
    </section>
  )
}
