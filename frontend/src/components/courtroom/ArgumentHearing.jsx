export default function ArgumentHearing({
  trial,
  side,
  index,
  onSide,
  onIndex,
  onEvidence,
}) {
  const points = trial.arguments[side]
  const point = points[index] || points[0]
  return (
    <section
      className={`argument-hearing argument-${side}`}
      aria-labelledby="argument-heading"
    >
      <div
        className="counsel-switch"
        role="group"
        aria-label="Opposing arguments"
      >
        {['prosecution', 'defense'].map((value) => (
          <button
            type="button"
            key={value}
            aria-pressed={side === value}
            onClick={() => onSide(value)}
          >
            {value === 'prosecution' ? 'Prosecution' : 'Defense'}
          </button>
        ))}
      </div>
      <div className="submission-heading">
        <span className="trial-overline">
          {side === 'prosecution' ? 'Prosecution case' : 'The defense responds'}
        </span>
        <span>
          {points.length
            ? `${String(index + 1).padStart(2, '0')} / ${String(points.length).padStart(2, '0')}`
            : 'NO SUBMISSION'}
        </span>
      </div>
      <div className="submission-body" key={point?.id || side}>
        <span className="submission-quote" aria-hidden="true">
          “
        </span>
        <h2 id="argument-heading">
          {point?.text || 'There is no complete submission on record.'}
        </h2>
        <p>
          {point?.context ||
            (point
              ? 'A counterpoint included in the case record.'
              : 'The court cannot fill gaps in the evidence.')}
        </p>
      </div>
      <div className="submission-source">
        <span>FROM THE CASE RECORD</span>
        <span>{point?.title || 'Evidence unavailable'}</span>
      </div>
      <div className="submission-controls">
        <button type="button" className="court-text" onClick={onEvidence}>
          ↶ Inspect the moment
        </button>
        <div>
          <button
            type="button"
            aria-label="Previous submission"
            disabled={index === 0}
            onClick={() => onIndex(index - 1)}
          >
            ←
          </button>
          <button
            type="button"
            aria-label="Next submission"
            disabled={index >= points.length - 1}
            onClick={() => onIndex(index + 1)}
          >
            →
          </button>
        </div>
      </div>
    </section>
  )
}
