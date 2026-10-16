export default function CounselPodium({
  side,
  count,
  active,
  interactive,
  onSelect,
}) {
  const title = side === 'prosecution' ? 'Prosecution' : 'Defense'
  const content = (
    <>
      <span className="counsel-number">
        {side === 'prosecution' ? '01' : '02'} / COUNSEL
      </span>
      <span className="podium-monogram" aria-hidden="true">
        {side === 'prosecution' ? 'P' : 'D'}
      </span>
      <strong>{title}</strong>
      <span className="podium-line" />
      <small>
        {count
          ? `${count} ${side === 'prosecution' ? (count === 1 ? 'submission' : 'submissions') : count === 1 ? 'counterpoint' : 'counterpoints'}`
          : 'No submission on record'}
      </small>
      <span className="podium-status">
        {active
          ? 'PRESENTING THE CASE'
          : interactive
            ? 'HEAR THIS SIDE ↗'
            : 'AWAITING THE FLOOR'}
      </span>
    </>
  )
  return (
    <aside
      className={`counsel-podium counsel-${side}${active ? ' is-speaking' : ''}`}
    >
      {interactive ? (
        <button
          type="button"
          onClick={onSelect}
          aria-label={`Hear the ${side}`}
          aria-pressed={active}
        >
          {content}
        </button>
      ) : (
        <div className="podium-content">{content}</div>
      )}
      <div className="podium-base" aria-hidden="true" />
    </aside>
  )
}
