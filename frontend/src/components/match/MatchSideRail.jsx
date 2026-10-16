import { useState } from 'react'
import { clubFor } from '../../domain/broadcast.js'
import {
  describeEvent,
  formatClock,
  formatPassRate,
  formatPercent,
  getCaseDisplayTitle,
} from '../../domain/formatters.js'
import BroadcastIcon from './BroadcastIcon.jsx'

const PAGE_SIZE = 20
const TABS = ['stats', 'events', 'cases']

export default function MatchSideRail({
  state,
  events,
  cases,
  match,
  onOpen,
  onSeek,
}) {
  const [tab, setTab] = useState('stats')
  const [page, setPage] = useState(0)
  const home = clubFor(match, 'home')
  const away = clubFor(match, 'away')
  const rows = [
    ['Possession', state?.possession, formatPercent],
    ['Pass accuracy', state?.pass_completion, formatPassRate],
    ['Shots', state?.shots],
    ['On target', state?.shots_on_target],
    ['Pressure', state?.pressure_events],
    ['Fouls', state?.fouls],
    ['Yellow cards', state?.yellow_cards],
    ['Red cards', state?.red_cards],
  ]
  const pageCount = Math.max(1, Math.ceil(events.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount - 1)
  const history = [...events]
    .reverse()
    .slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE)
  const handleTabKey = (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const index = TABS.indexOf(tab)
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? 2
          : (index + (event.key === 'ArrowRight' ? 1 : 2)) % 3
    setTab(TABS[next])
    event.currentTarget.querySelectorAll('[role="tab"]')[next].focus()
  }
  return (
    <aside className="match-side-rail" aria-label="Match details">
      <div className="rail-heading">
        <span className="broadcast-kicker">THE MATCH FILE</span>
        <span className="rail-edition">FC / 01</span>
      </div>
      <div
        className="rail-tabs"
        role="tablist"
        aria-label="Match information"
        onKeyDown={handleTabKey}
      >
        {TABS.map((item) => (
          <button
            type="button"
            key={item}
            role="tab"
            id={`rail-tab-${item}`}
            tabIndex={tab === item ? 0 : -1}
            aria-selected={tab === item}
            aria-controls={`rail-panel-${item}`}
            onClick={() => setTab(item)}
          >
            {item === 'stats'
              ? 'Stats'
              : item === 'events'
                ? 'Events'
                : `Cases ${cases.length ? `(${cases.length})` : ''}`}
          </button>
        ))}
      </div>
      <div
        className="rail-content"
        role="tabpanel"
        id={`rail-panel-${tab}`}
        aria-labelledby={`rail-tab-${tab}`}
      >
        {tab === 'stats' ? (
          <>
            <div className="stat-clubs">
              <strong style={{ color: home.color }}>{home.shortName}</strong>
              <span>MATCH STATS</span>
              <strong style={{ color: away.color }}>{away.shortName}</strong>
            </div>
            {rows.map(([label, values, format]) => (
              <div className="broadcast-stat" key={label}>
                <strong>
                  {format ? format(values?.home) : (values?.home ?? 'N/A')}
                </strong>
                <span>{label}</span>
                <strong>
                  {format ? format(values?.away) : (values?.away ?? 'N/A')}
                </strong>
              </div>
            ))}
            <p className="rail-footnote">
              Statistics reflect the current replay position. Possession is
              estimated from events.
            </p>
          </>
        ) : null}
        {tab === 'events' ? (
          <>
            <div className="history-page-controls">
              <button
                type="button"
                disabled={!currentPage}
                onClick={() => setPage(currentPage - 1)}
              >
                Newer
              </button>
              <span>
                {events.length} events · {currentPage + 1}/{pageCount}
              </span>
              <button
                type="button"
                disabled={currentPage >= pageCount - 1}
                onClick={() => setPage(currentPage + 1)}
              >
                Older
              </button>
            </div>
            <ol className="broadcast-history">
              {history.map((event) => (
                <li key={event.event_id}>
                  <button type="button" onClick={() => onSeek(event.timestamp)}>
                    <time>{formatClock(event.timestamp)}</time>
                    <span>
                      <strong>{event.event_type.replace(/_/g, ' ')}</strong>
                      <span>{describeEvent(event, match)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </>
        ) : null}
        {tab === 'cases' ? (
          <div className="broadcast-case-list">
            {cases.length ? (
              cases.map((item) => (
                <button
                  type="button"
                  key={item.case_id}
                  onClick={() => onOpen(item)}
                >
                  <span>
                    <BroadcastIcon name="court" size={16} />{' '}
                    {formatClock(
                      item.available_timestamp ?? item.detection_timestamp,
                    )}
                  </span>
                  <strong>{getCaseDisplayTitle(item, match)}</strong>
                  <small>
                    {item.case_type.replace(/_/g, ' ')} <span>Open case →</span>
                  </small>
                </button>
              ))
            ) : (
              <div className="rail-empty">
                <BroadcastIcon name="court" size={30} />
                <h3>Let the evidence build.</h3>
                <p>
                  Cases appear as the replay reaches a complete evidence window.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>
      <div className="rail-bottom">
        <BroadcastIcon name="court" />
        <p>
          Every moment has two sides.
          <br />
          <span>Follow the match. Make your case.</span>
        </p>
      </div>
    </aside>
  )
}
