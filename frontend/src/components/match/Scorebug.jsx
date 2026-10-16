import { clubFor } from '../../domain/broadcast.js'
import { formatClock } from '../../domain/formatters.js'
import ClubCrest from './ClubCrest.jsx'

export default function Scorebug({ match, state, timestamp }) {
  const home = clubFor(match, 'home')
  const away = clubFor(match, 'away')
  return (
    <div className="scorebug" aria-label="Match scoreboard">
      <div className="scorebug-club" style={{ '--club-color': home.color }}>
        <ClubCrest club={home} small />
        <strong>
          <span className="club-full-name">{home.name}</span>
          <span className="club-short-name">{home.shortName}</span>
        </strong>
      </div>
      <span className="scorebug-score" aria-label="Score">
        {state ? `${state.score.home} - ${state.score.away}` : '–'}
      </span>
      <time className="scorebug-clock" aria-label="Match clock">
        {formatClock(timestamp)}
      </time>
      <div
        className="scorebug-club scorebug-away"
        style={{ '--club-color': away.color }}
      >
        <strong>
          <span className="club-full-name">{away.name}</span>
          <span className="club-short-name">{away.shortName}</span>
        </strong>
        <ClubCrest club={away} small />
      </div>
    </div>
  )
}
