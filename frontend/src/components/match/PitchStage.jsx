import { useId } from 'react'
import { clubFor, eventGeometry } from '../../domain/broadcast.js'
import { normalizeTeamKey } from '../../domain/formatters.js'

export default function PitchStage({ event, match, children }) {
  const id = useId().replace(/:/g, '')
  const { point, path } = eventGeometry(event)
  const side = normalizeTeamKey(event?.team_id)
  const club = clubFor(match, side || 'home')
  const type = event?.event_type
  const home = clubFor(match, 'home')
  const away = clubFor(match, 'away')
  return (
    <section className="pitch-stage" aria-label="Tactical match replay">
      <div className="pitch-chrome">
        <span>
          <i className="status-dot" /> TACTICAL FEED
        </span>
        <span>2D EVENT REPLAY</span>
      </div>
      <svg
        className="football-pitch"
        viewBox="-5 -5 115 78"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Football pitch${event ? `: ${type.replace(/_/g, ' ')}` : ''}`}
      >
        <defs>
          <linearGradient id={`${id}-grass`} x2="0" y2="1">
            <stop stopColor="#163e30" />
            <stop offset="1" stopColor="#0d2e23" />
          </linearGradient>
          <pattern
            id={`${id}-stripes`}
            width="21"
            height="68"
            patternUnits="userSpaceOnUse"
          >
            <rect width="10.5" height="68" fill="white" opacity=".025" />
          </pattern>
          <marker
            id={`${id}-arrow`}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto-start-reverse"
          >
            <path d="M0 0 10 5 0 10Z" fill={club.color} />
          </marker>
          <pattern
            id={`${id}-net`}
            width="1"
            height="1"
            patternUnits="userSpaceOnUse"
          >
            <path d="M1 0H0V1" stroke="#94b4a3" strokeWidth=".1" />
          </pattern>
        </defs>
        <rect x="-5" y="-5" width="115" height="78" fill="#0a211a" />
        <rect width="105" height="68" fill={`url(#${id}-grass)`} />
        <rect width="105" height="68" fill={`url(#${id}-stripes)`} />
        <g
          className="pitch-markings"
          fill="none"
          stroke="#b0cbbb"
          strokeWidth=".22"
          opacity=".65"
        >
          <rect width="105" height="68" />
          <path d="M52.5 0v68" />
          <circle cx="52.5" cy="34" r="9.15" />
          <path d="M0 13.84h16.5v40.32H0M105 13.84H88.5v40.32H105M0 24.84h5.5v18.32H0M105 24.84h-5.5v18.32H105" />
          <path d="M16.5 26.69a9.15 9.15 0 0 1 0 14.62M88.5 26.69a9.15 9.15 0 0 0 0 14.62" />
          <path d="M0 1a1 1 0 0 0 1-1M104 0a1 1 0 0 0 1 1M0 67a1 1 0 0 1 1 1M104 68a1 1 0 0 1 1-1" />
          <circle cx="52.5" cy="34" r=".3" fill="#b0cbbb" />
          <circle cx="11" cy="34" r=".25" fill="#b0cbbb" />
          <circle cx="94" cy="34" r=".25" fill="#b0cbbb" />
          <rect
            x="-2.3"
            y="30.34"
            width="2.3"
            height="7.32"
            fill={`url(#${id}-net)`}
          />
          <rect
            x="105"
            y="30.34"
            width="2.3"
            height="7.32"
            fill={`url(#${id}-net)`}
          />
        </g>
        <g
          className="pitch-event"
          key={event?.event_id}
          style={{ '--event-color': club.color }}
        >
          {point && type === 'pressure_event' ? (
            <circle
              data-testid="pressure-region"
              cx={point.x}
              cy={point.y}
              r="7"
              fill={club.color}
              fillOpacity=".14"
              stroke={club.color}
              strokeWidth=".3"
              strokeDasharray="1 1"
            />
          ) : null}
          {path ? (
            <>
              <line
                data-testid="event-path"
                x1={path.start.x}
                y1={path.start.y}
                x2={path.end.x}
                y2={path.end.y}
                stroke={club.color}
                strokeWidth={type === 'shot' ? '.75' : '.5'}
                strokeDasharray={type === 'shot' ? '1.4 .8' : undefined}
                markerEnd={`url(#${id}-arrow)`}
              />
              <circle
                cx={path.start.x}
                cy={path.start.y}
                r=".8"
                fill="#e9eee7"
              />
              <circle
                cx={path.end.x}
                cy={path.end.y}
                r="1.2"
                fill={club.color}
                fillOpacity=".3"
                stroke={club.color}
                strokeWidth=".3"
              />
            </>
          ) : null}
          {point ? (
            <g
              data-testid="event-point"
              transform={`translate(${point.x} ${point.y})`}
            >
              {type === 'goal' ? (
                <circle
                  className="goal-ring"
                  r="4"
                  fill="none"
                  stroke="#e7c974"
                  strokeWidth=".5"
                />
              ) : null}
              <circle r="2.2" fill={club.color} fillOpacity=".16" />
              <circle
                r=".95"
                fill={type === 'goal' ? '#e7c974' : club.color}
                stroke="#f0f4eb"
                strokeWidth=".3"
              />
              {['foul', 'tackle'].includes(type) ? (
                <path
                  d="m-1.2-1.2 2.4 2.4m0-2.4-2.4 2.4"
                  stroke="white"
                  strokeWidth=".35"
                />
              ) : null}
            </g>
          ) : null}
        </g>
      </svg>
      {!point && event ? (
        <span className="pitch-location-note">
          Location not recorded for this event
        </span>
      ) : null}
      <div className="pitch-orientation">
        <span style={{ color: home.color }}>{home.shortName} ATTACK →</span>
        <span>EVENT LOCATIONS · NO TRACKING DATA</span>
        <span style={{ color: away.color }}>← {away.shortName} ATTACK</span>
      </div>
      {children}
    </section>
  )
}
