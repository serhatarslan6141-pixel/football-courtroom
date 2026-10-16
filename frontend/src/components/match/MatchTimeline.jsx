import { timelineMarkers } from '../../domain/broadcast.js'
import { formatClock } from '../../domain/formatters.js'

const markerLabels = {
  goal: 'Goal',
  substitution: 'Substitution',
  card: 'Card',
  case: 'Courtroom case available',
}
const markerSymbols = { goal: '●', substitution: '⇄', card: '▪', case: '◆' }

export default function MatchTimeline({
  events,
  cases,
  timestamp,
  pendingTimestamp,
  duration,
  onSeek,
  disabled,
}) {
  const markers = timelineMarkers(events, cases, timestamp)
  const target = pendingTimestamp ?? timestamp
  const percent = (value) =>
    `${Math.max(0, Math.min(100, (value / (duration || 1)) * 100))}%`
  return (
    <section className="match-timeline" aria-label="Replay timeline">
      <div className="timeline-heading">
        <span>MATCH TIMELINE</span>
        <div>
          <span className="timeline-legend">
            <b>●</b> Goal <b>⇄</b> Sub <b>▪</b> Card <b>◆</b> Case
          </span>
          <time>
            {formatClock(timestamp)} <span>/ {formatClock(duration)}</span>
          </time>
        </div>
      </div>
      <div className="timeline-track">
        <div className="timeline-rail">
          <span style={{ width: percent(timestamp) }} />
        </div>
        <input
          type="range"
          min="0"
          max={duration || 1}
          step="1"
          value={target}
          disabled={disabled}
          aria-label="Seek match replay"
          aria-valuetext={`${formatClock(target)}${pendingTimestamp !== null ? ', seeking' : ''}`}
          onChange={(event) => onSeek(Number(event.target.value))}
        />
        <div className="timeline-markers">
          {markers.map((marker, index) => (
            <button
              type="button"
              key={marker.id}
              className={`timeline-marker marker-${marker.type}`}
              style={{
                left: percent(marker.timestamp),
                top: `${(index % 2) * 12}px`,
              }}
              aria-label={`${markerLabels[marker.type]} at ${formatClock(marker.timestamp)}`}
              title={`${markerLabels[marker.type]} · ${formatClock(marker.timestamp)}`}
              onClick={() => onSeek(marker.timestamp)}
            >
              {markerSymbols[marker.type]}
            </button>
          ))}
        </div>
      </div>
      <div className="timeline-ticks">
        <span>KO</span>
        <span>{formatClock(duration / 4)}</span>
        <span>HT · {formatClock(duration / 2)}</span>
        <span>{formatClock((duration * 3) / 4)}</span>
        <span>FT</span>
      </div>
    </section>
  )
}
