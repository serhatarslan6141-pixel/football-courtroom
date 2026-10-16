import { useState } from 'react'
import { VOTE_LABELS } from '../../domain/courtroom.js'

export default function UserVerdict({ vote, onVote }) {
  const [choice, setChoice] = useState(vote)
  return (
    <section className="user-verdict" aria-labelledby="vote-heading">
      <span className="trial-overline">YOUR SEAT ON THE JURY</span>
      <h2 id="vote-heading">
        You’ve heard the case.
        <br />
        Where do you stand?
      </h2>
      <p>Your opinion is yours. The court’s assessment comes next.</p>
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
      <small>Your vote stays in this session. No account needed.</small>
    </section>
  )
}
