import { useMatchSession } from '../session/useMatchSession.js'
import {
  describeEvent, formatClock, formatPassRate, formatPercent,
  getCaseDisplayTitle, normalizeTeamKey,
} from '../domain/formatters.js'

export default function MatchScene() {
  const {
    matchLoading, matchError, loadMatches, matchData, selectedMatchId,
    setSelectedMatchId, matches, scoreText, state, handlePlayPause, events,
    isPlaying, handleReset, replaySpeed, setReplaySpeed, caseNotifications,
    openCourtroom, cases, statsOpen, toggleStats, liveEvents, selectedCase,
  } = useMatchSession()
  const homePossession = state?.possession?.home
  const awayPossession = state?.possession?.away
  const homePassRate = state?.pass_completion?.home
  const awayPassRate = state?.pass_completion?.away

  if (matchLoading) {
    return (
      <main className="page-shell">
        <section className="panel panel-soft">
          <p className="eyebrow">Loading</p>
          <h2>Preparing the match feed</h2>
        </section>
      </main>
    )
  }

  if (matchError) {
    return (
      <main className="page-shell">
        <section className="panel error-panel">
          <p className="eyebrow">Connection issue</p>
          <h2>{matchError}</h2>
          <button type="button" className="primary-btn" onClick={loadMatches}>Retry</button>
        </section>
      </main>
    )
  }

  return (
    <main className="page-shell match-page">
      <section className="broadcast-panel panel">
        <div className="broadcast-top">
          <div>
            <p className="eyebrow">Match centre</p>
            <h1>{matchData ? `${matchData.home_team} vs ${matchData.away_team}` : 'Select a match'}</h1>
          </div>
          <div className="selector-row">
            <label htmlFor="match-select">Select fixture</label>
            <select
              id="match-select"
              value={selectedMatchId}
              onChange={(event) => setSelectedMatchId(event.target.value)}
              disabled={!matches.length}
            >
              {!matches.length ? <option value="">No matches available</option> : null}
              {matches.map((item) => (
                <option key={item.match_id} value={item.match_id}>
                  {item.home_team} vs {item.away_team}
                </option>
              ))}
            </select>
            <span className="simulated-pill">Simulated Match</span>
          </div>
        </div>

        <div className="score-strip">
          <div className="team-side">
            <span className="team-crest purple">{matchData?.home_team?.slice(0, 1)?.toUpperCase() || 'H'}</span>
            <div>
              <small>Home</small>
              <strong>{matchData?.home_team || 'Home club'}</strong>
            </div>
          </div>

          <div className="score-wrap">
            <span className="score">{scoreText}</span>
            <small>{state ? formatClock(state.match_clock_seconds) : '00:00'}</small>
          </div>

          <div className="team-side team-side-right">
            <div>
              <small>Away</small>
              <strong>{matchData?.away_team || 'Away club'}</strong>
            </div>
            <span className="team-crest gold">{matchData?.away_team?.slice(0, 1)?.toUpperCase() || 'A'}</span>
          </div>
        </div>

        <div className="playback-row">
          <button type="button" className="primary-btn" onClick={handlePlayPause} disabled={!events.length}>
            {isPlaying ? 'Pause' : 'Play'}
          </button>
          <button type="button" className="secondary-btn" onClick={handleReset} disabled={!events.length}>
            Reset
          </button>
          {[0.5, 1, 2].map((speed) => (
            <button
              key={speed}
              type="button"
              className={replaySpeed === speed ? 'speed-button active' : 'speed-button'}
              onClick={() => setReplaySpeed(speed)}
            >
              {speed}x
            </button>
          ))}
        </div>
      </section>

      {caseNotifications.length > 0 ? (
        <section className="case-alerts" aria-live="polite">
          {caseNotifications.map((notification) => (
            <button
              key={notification.case_id}
              type="button"
              className="case-alert"
              onClick={() => openCourtroom(cases.find((item) => item.case_id === notification.case_id))}
            >
              <span>Case alert</span>
              <strong>{notification.title}</strong>
            </button>
          ))}
        </section>
      ) : null}

      <section className="match-grid">
        <article className="panel timeline-panel">
          <div className="panel-header compact-header">
            <div>
              <p className="eyebrow">Timeline</p>
              <h3>Key moments</h3>
            </div>
            <button type="button" className="secondary-btn small" onClick={() => toggleStats()}>
              {statsOpen ? 'Hide stats' : 'Show stats'}
            </button>
          </div>

          {statsOpen && state ? (
            <div className="stats-grid">
              <div className="metric-card">
                <span>Possession</span>
                <strong>{formatPercent(homePossession)} / {formatPercent(awayPossession)}</strong>
              </div>
              <div className="metric-card">
                <span>Pass accuracy</span>
                <strong>{formatPassRate(homePassRate)} / {formatPassRate(awayPassRate)}</strong>
              </div>
              <div className="metric-card">
                <span>Shots</span>
                <strong>{state.shots.home} / {state.shots.away}</strong>
              </div>
              <div className="metric-card">
                <span>Pressing</span>
                <strong>{state.pressure_events.home} / {state.pressure_events.away}</strong>
              </div>
            </div>
          ) : null}

          <ul className="event-list">
            {liveEvents.map((event) => {
              const teamName = normalizeTeamKey(event.team_id) === 'home' ? matchData?.home_team : matchData?.away_team
              return (
                <li key={event.event_id}>
                  <span className="event-time">{event.minute}</span>
                  <div>
                    <strong>{event.event_type.replace(/_/g, ' ')}</strong>
                    <small>{teamName}</small>
                    <p>{describeEvent(event, matchData)}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </article>

        <aside className="panel case-panel">
          <div className="panel-header compact-header">
            <div>
              <p className="eyebrow">Match debate</p>
              <h3>Case alerts</h3>
            </div>
          </div>

          {cases.length === 0 ? (
            <p className="empty-state">No key moments yet. Keep the replay moving and new cases will appear here.</p>
          ) : (
            <div className="case-stack">
              {cases.map((caseItem) => (
                <button
                  key={caseItem.case_id}
                  type="button"
                  className={selectedCase?.case_id === caseItem.case_id ? 'case-card active' : 'case-card'}
                  onClick={() => openCourtroom(caseItem)}
                >
                  <span className="case-pill">{caseItem.case_type.replace(/_/g, ' ')}</span>
                  <strong>{getCaseDisplayTitle(caseItem, matchData)}</strong>
                  <small>{formatClock(caseItem.detection_timestamp)}</small>
                </button>
              ))}
            </div>
          )}
        </aside>
      </section>
    </main>
  )
}
