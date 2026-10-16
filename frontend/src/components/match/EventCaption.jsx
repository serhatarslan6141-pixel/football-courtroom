import { clubFor } from '../../domain/broadcast.js'
import {
  describeEvent,
  formatClock,
  normalizeTeamKey,
} from '../../domain/formatters.js'

const actionVerbs = {
  ball_control: 'controls the ball',
  pass: 'plays a pass',
  cross: 'sends a cross',
  carry: 'carries into space',
  dribble: 'dribbles forward',
  shot: 'shoots toward goal',
  clearance: 'clears upfield',
  pressure_event: 'presses the ball carrier',
  miscontrol: 'chases a loose touch',
}

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
          {event?.in_progress
            ? event.metadata?.ball_in_play === false
              ? 'Play is stopped. Waiting for the restart.'
              : `${event.metadata?.player_name || club.name} ${actionVerbs[event.event_type] || event.event_type.replace(/_/g, ' ')}.`
            : event
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
