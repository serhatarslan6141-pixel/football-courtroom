import { useId } from 'react'
import { clubFor, eventGeometry, pitchPoint } from '../../domain/broadcast.js'
import { replayVisual } from '../../domain/replayVisual.js'
import { useReducedMotion } from '../../hooks/useReducedMotion.js'
import { normalizeTeamKey } from '../../domain/formatters.js'

function RecordedPath({ event, path, color, marker, opacity = 1, testId }) {
  if (!path) return null
  const failed = event.metadata?.outcome === 'incomplete'
  const carry = ['carry', 'dribble'].includes(event.event_type)
  return (
    <line
      data-testid={testId}
      x1={path.start.x}
      y1={path.start.y}
      x2={path.end.x}
      y2={path.end.y}
      stroke={failed ? '#d99b88' : color}
      opacity={opacity}
      strokeWidth={event.event_type === 'shot' ? '.7' : carry ? '.35' : '.45'}
      strokeDasharray={
        failed
          ? '1 .7'
          : carry
            ? '.4 .8'
            : event.event_type === 'clearance'
              ? '2 1'
              : undefined
      }
      markerEnd={carry ? undefined : `url(#${marker})`}
    />
  )
}

export default function PitchStage({
  event,
  events = [],
  timestamp = event?.timestamp ?? 0,
  match,
  children,
}) {
  const id = useId().replace(/:/g, '')
  const reducedMotion = useReducedMotion()
  const visual = events.length
    ? replayVisual(events, timestamp, reducedMotion)
    : null
  const current = visual?.event || event
  const geometry = eventGeometry(current)
  const point = visual ? visual.ball : geometry.point
  const path = visual ? visual.path : geometry.path
  const side = normalizeTeamKey(current?.team_id)
  const club = clubFor(match, side || 'home')
  const owner = clubFor(match, current?.possession_team_id || side || 'home')
  const type = current?.event_type
  const cue = visual?.cue || current
  const cueType = cue?.event_type
  const cuePoint = eventGeometry(cue).point
  const restart =
    visual?.restart || (['restart', 'kickoff'].includes(type) ? current : null)
  const discipline =
    visual?.discipline ||
    (['card', 'offside', 'foul'].includes(type) ? current : null)
  const offside =
    discipline?.event_type === 'offside'
      ? discipline.metadata?.offside_context
      : null
  const offsideLine = Number.isFinite(offside?.offside_line_x)
    ? offside.offside_line_x * 1.05
    : null
  const restartLabel = restart?.metadata?.restart_type?.replace(/_/g, ' ')
  const setup = restart?.metadata?.setup_positions || []
  const period = current?.period || 1
  const phase = current?.metadata?.phase?.replace(/_/g, ' ')
  const goalAge = Math.max(0, timestamp - (cue?.timestamp ?? timestamp))
  const home = clubFor(match, 'home')
  const away = clubFor(match, 'away')
  return (
    <section className="pitch-stage" aria-label="Tactical match replay">
      <div className="pitch-chrome">
        <span>
          <i className="status-dot" /> TACTICAL FEED
        </span>
        <span>
          {period === 2 ? 'SECOND HALF' : 'FIRST HALF'}
          {phase ? ` · ${phase.toUpperCase()}` : ' · 2D EVENT REPLAY'}
        </span>
      </div>
      <svg
        className="football-pitch"
        viewBox="-5 -5 115 78"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Football pitch${current ? `: ${type.replace(/_/g, ' ')}` : ''}`}
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
            <path d="M0 0 10 5 0 10Z" fill="context-stroke" />
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
        {offsideLine != null ? (
          <g
            data-testid="offside-context"
            aria-label="Offside positions at pass release"
          >
            <line
              x1={offsideLine}
              x2={offsideLine}
              y1="0"
              y2="68"
              stroke="#e7c974"
              strokeWidth=".35"
              strokeDasharray="1 1"
            />
            {pitchPoint(offside.receiver_position) ? (
              <circle
                cx={pitchPoint(offside.receiver_position).x}
                cy={pitchPoint(offside.receiver_position).y}
                r="1.6"
                fill="none"
                stroke="#e7c974"
                strokeWidth=".4"
              />
            ) : null}
            <text
              x="52.5"
              y="65"
              textAnchor="middle"
              fontSize="1.5"
              fill="#e7c974"
            >
              AT PASS RELEASE · SIMULATED POSITIONS
            </text>
          </g>
        ) : null}
        {restart ? (
          <g data-testid="restart-setup" aria-label={`${restartLabel} setup`}>
            {setup
              .filter(
                (player) =>
                  player.player_id === restart.player_id ||
                  (restart.metadata.restart_type === 'penalty' &&
                    player.role === 'GK' &&
                    player.team_id !== restart.team_id),
              )
              .map((player) => {
                const location = pitchPoint(player)
                return location ? (
                  <g
                    key={player.player_id}
                    transform={`translate(${location.x} ${location.y})`}
                  >
                    <circle
                      r="2.1"
                      fill="none"
                      stroke={clubFor(match, player.team_id).color}
                      strokeWidth=".35"
                      strokeDasharray=".6 .6"
                    />
                    <text
                      y="-3"
                      x={location.x > 90 ? -2 : 2}
                      textAnchor={location.x > 90 ? 'end' : 'start'}
                      fontSize="1.5"
                      fill="#eff0db"
                    >
                      {player.player_id === restart.player_id
                        ? restart.metadata.player_name
                        : 'GK · goal line'}
                    </text>
                  </g>
                ) : null
              })}
          </g>
        ) : null}
        <g className="possession-trail" aria-label="Recent possession sequence">
          {visual?.trail
            .filter((item) => item.event_id !== current?.event_id)
            .map((item, index) => (
              <RecordedPath
                key={item.event_id}
                event={item}
                path={eventGeometry(item).path}
                marker={`${id}-arrow`}
                color={clubFor(match, item.team_id).color}
                opacity={0.14 + index * 0.07}
              />
            ))}
        </g>
        <g className="pitch-event" style={{ '--event-color': club.color }}>
          {cuePoint && cueType === 'pressure_event' ? (
            <circle
              data-testid="pressure-region"
              cx={cuePoint.x}
              cy={cuePoint.y}
              r="5"
              fill={clubFor(match, cue.team_id).color}
              fillOpacity=".12"
              stroke={clubFor(match, cue.team_id).color}
              strokeWidth=".3"
              strokeDasharray="1 1"
            />
          ) : null}
          <RecordedPath
            event={current || {}}
            path={path}
            color={club.color}
            marker={`${id}-arrow`}
            testId="event-path"
          />
          {cuePoint &&
          [
            'tackle',
            'foul',
            'interception',
            'recovery',
            'possession_change',
            'save',
          ].includes(cueType) ? (
            <g
              data-testid="possession-cue"
              data-cue-type={cueType}
              transform={`translate(${cuePoint.x} ${cuePoint.y})`}
            >
              {cueType === 'recovery' ? (
                <circle
                  r="2.5"
                  fill="none"
                  stroke={clubFor(match, cue.team_id).color}
                  strokeWidth=".45"
                />
              ) : cueType === 'save' ? (
                <rect
                  x="-2.3"
                  y="-2.3"
                  width="4.6"
                  height="4.6"
                  rx=".5"
                  fill="none"
                  stroke={clubFor(match, cue.team_id).color}
                  strokeWidth=".45"
                />
              ) : (
                <path
                  d={
                    ['interception', 'possession_change'].includes(cueType)
                      ? 'M0-2.8 2.8 0 0 2.8-2.8 0Z'
                      : 'm-2-2 4 4m0-4-4 4'
                  }
                  fill="none"
                  stroke={clubFor(match, cue.team_id).color}
                  strokeWidth=".45"
                />
              )}
              <text
                y="5"
                textAnchor="middle"
                fontSize="1.3"
                fill="#d8dcca"
                stroke="#0a211a"
                strokeWidth=".2"
                paintOrder="stroke"
              >
                {cueType.replace(/_/g, ' ').toUpperCase()}
              </text>
            </g>
          ) : null}
          {point ? (
            <g
              data-testid="event-point"
              data-in-progress={visual?.inProgress || false}
              transform={`translate(${point.x} ${point.y})`}
            >
              {cueType === 'goal' && goalAge <= 1.8 ? (
                <circle
                  className="goal-ring"
                  r={reducedMotion ? 3 : 2 + goalAge * 2}
                  opacity={reducedMotion ? 0.8 : 1 - goalAge / 2}
                  fill="none"
                  stroke="#e7c974"
                  strokeWidth=".5"
                />
              ) : null}
              <circle r="2.1" fill={owner.color} fillOpacity=".19" />
              <circle
                r=".85"
                fill="#f0f1df"
                stroke={owner.color}
                strokeWidth=".4"
              />
              {current?.metadata?.player_name &&
              current.metadata.ball_in_play !== false ? (
                <text
                  className="active-player-label"
                  x={point.x > 88 ? -2.2 : 2.2}
                  y={point.y < 8 ? 3.5 : -2.2}
                  textAnchor={point.x > 88 ? 'end' : 'start'}
                  fill="#eff0db"
                  stroke="#0a211a"
                  strokeWidth=".25"
                  paintOrder="stroke"
                  fontSize="1.6"
                >
                  {current.metadata.player_name}
                  {current.metadata.player_role
                    ? ` · ${current.metadata.player_role}`
                    : ''}
                </text>
              ) : null}
            </g>
          ) : null}
        </g>
      </svg>
      {restartLabel || discipline ? (
        <div className="pitch-rules-cue" role="status" aria-live="off">
          {discipline?.event_type === 'card' ? (
            <span
              className={`disciplinary-card ${discipline.metadata?.card_type === 'red' ? 'is-red' : ''}`}
              aria-label={`${discipline.metadata?.card_type} card`}
            />
          ) : null}
          <strong>
            {restartLabel
              ? `${restartLabel.replace(/^./, (c) => c.toUpperCase())} — ${clubFor(match, restart.team_id).name}`
              : discipline.event_type === 'card'
                ? `${discipline.metadata?.card_type === 'red' ? 'SENT OFF' : 'YELLOW CARD'} · ${discipline.metadata?.player_name}`
                : discipline.event_type === 'offside'
                  ? `Offside · ${discipline.metadata?.player_name}`
                  : `Foul · ${discipline.metadata?.player_name}`}
          </strong>
          {restartLabel && discipline?.event_type === 'card' ? (
            <span>
              {discipline.metadata?.player_name}
              {discipline.metadata?.card_type === 'red'
                ? ' · sent off'
                : ' · booked'}
            </span>
          ) : null}
        </div>
      ) : null}
      {!point && event ? (
        <span className="pitch-location-note">
          Location not recorded for this event
        </span>
      ) : null}
      <div className="pitch-orientation">
        <span style={{ color: home.color }}>
          {period === 1
            ? `${home.shortName} ATTACK →`
            : `← ${home.shortName} ATTACK`}
        </span>
        <span>EVENT LOCATIONS · NO TRACKING DATA</span>
        <span style={{ color: away.color }}>
          {period === 1
            ? `← ${away.shortName} ATTACK`
            : `${away.shortName} ATTACK →`}
        </span>
      </div>
      {children}
    </section>
  )
}
