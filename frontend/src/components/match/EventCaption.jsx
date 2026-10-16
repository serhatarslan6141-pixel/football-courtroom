import { clubFor } from '../../domain/broadcast.js'
import {
  describeEvent,
  formatClock,
  normalizeTeamKey,
} from '../../domain/formatters.js'

export default function EventCaption({ event, match, timestamp }) {
  const club = clubFor(match, normalizeTeamKey(event?.team_id) || 'home')
  return (
    <div className="event-caption" style={{ '--club-color': club.color }}>
      <time>{formatClock(event?.timestamp ?? timestamp)}</time>
      <div>
        <span className="caption-meta">
          {event?.event_type.replace(/_/g, ' ') || 'Ready for kickoff'}{' '}
          <span>·</span> {club.name}
          {event?.metadata?.player_name
            ? ` / ${event.metadata.player_name}`
            : ''}
        </span>
        <p>
          {event
            ? describeEvent(event, match)
            : 'Your match is ready. Press play to follow the action.'}
        </p>
      </div>
      {event?.event_type === 'goal' ? (
        <span className="caption-goal">GOAL</span>
      ) : null}
    </div>
  )
}
