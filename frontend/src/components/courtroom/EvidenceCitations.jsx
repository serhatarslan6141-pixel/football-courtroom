import { useState } from 'react'
import { formatClock } from '../../domain/formatters.js'

export default function EvidenceCitations({ eventIds = [], trial, onCite }) {
  const [expanded, setExpanded] = useState(false)
  const known = new Map(trial.knownEvents.filter((event) => event.timestamp >= trial.bounds.start
    && event.timestamp <= trial.bounds.end).map((event) => [event.event_id, event]))
  // No partial citation repair: withhold the links if any reference is invalid.
  if (!eventIds.length || eventIds.some((id) => !known.has(id))) return null
  const button = (id) => {
    const event = known.get(id)
    const label = `${event.event_type.replaceAll('_', ' ')} · ${formatClock(event.timestamp)}`
    return <button type="button" key={id} className="evidence-citation" onClick={() => onCite(id)}
      aria-label={`Review cited ${event.event_type.replaceAll('_', ' ')} at ${formatClock(event.timestamp)}`}>
      <span aria-hidden="true">↗</span> {label}
    </button>
  }
  const ids = [...new Set(eventIds)]
  return <div className="evidence-citations" aria-label="Supporting match references">
    {ids.slice(0, 3).map(button)}
    {ids.length > 3 && <details onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary>{ids.length - 3} more references</summary>
      {expanded && <div>{ids.slice(3).map(button)}</div>}
    </details>}
  </div>
}
