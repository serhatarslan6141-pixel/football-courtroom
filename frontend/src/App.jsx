import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

const formatClock = (seconds) => {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0
  const minute = Math.floor(safeSeconds / 60)
  const second = safeSeconds % 60
  return `${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`
}

const normalizeTeamKey = (value) => {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (normalized === 'home' || normalized === 'away') {
      return normalized
    }
    if (normalized === '0') {
      return 'home'
    }
    if (normalized === '1') {
      return 'away'
    }
  }

  if (value === 0 || value === 1) {
    return value === 0 ? 'home' : 'away'
  }

  return null
}

const formatPercent = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return 'N/A'
  }
  return `${numeric.toFixed(1)}%`
}

const formatPassRate = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return 'N/A'
  }
  return `${(numeric * 100).toFixed(1)}%`
}

const describeEvent = (event, matchData) => {
  const metadata = event?.metadata || {}
  if (metadata.description) {
    return metadata.description
  }

  const teamName = normalizeTeamKey(event.team_id) === 'home' ? matchData?.home_team : matchData?.away_team
  const playerName = metadata.player_name || 'Player'
  const playerLabel = metadata.recipient_name ? `${playerName} to ${metadata.recipient_name}` : playerName

  switch (event.event_type) {
    case 'pass':
      return `${playerLabel} ${metadata.outcome === 'complete' ? 'completes' : 'attempts'} a pass.`
    case 'pressure_event':
      return `${playerName} presses high to regain possession.`
    case 'shot':
      return `${playerName} takes a shot ${metadata.outcome === 'goal' ? 'and scores' : 'with intent'}.`
    case 'goal':
      return `${playerName} scores for ${teamName}.`
    case 'foul':
      return `${playerName} commits a foul.`
    case 'substitution':
      return `${metadata.player_in_name || 'Substitute'} comes on for ${metadata.player_out_name || 'the outgoing player'}.`
    case 'tackle':
      return `${playerName} makes a challenge.`
    case 'kickoff':
      return `${teamName} kick off.`
    case 'whistle':
      return 'The referee blows for full time.'
    case 'card':
      return `${playerName} is booked.`
    default:
      return event.event_type.replace(/_/g, ' ')
  }
}

const safeFetchJson = async (url) => {
  const response = await fetch(url)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with status ${response.status}`)
  }
  return response.json()
}

function App() {
  const [screen, setScreen] = useState('lobby')
  const [matches, setMatches] = useState([])
  const [selectedMatchId, setSelectedMatchId] = useState('')
  const [matchData, setMatchData] = useState(null)
  const [events, setEvents] = useState([])
  const [state, setState] = useState(null)
  const [cases, setCases] = useState([])
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [replaySpeed, setReplaySpeed] = useState(1)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [matchLoading, setMatchLoading] = useState(true)
  const [matchError, setMatchError] = useState('')
  const [caseNotifications, setCaseNotifications] = useState([])
  const previousCaseIdsRef = useRef(new Set())

  const selectedCase = useMemo(() => {
    if (!cases.length) {
      return null
    }
    return cases.find((caseItem) => caseItem.case_id === selectedCaseId) || cases[0]
  }, [cases, selectedCaseId])

  const loadMatches = async () => {
    setMatchLoading(true)
    setMatchError('')

    try {
      const payload = await safeFetchJson(`${API_BASE}/api/matches`)
      const nextMatches = payload.matches || []
      setMatches(nextMatches)

      if (nextMatches.length === 0) {
        setSelectedMatchId('')
        setMatchData(null)
        setEvents([])
        setState(null)
        setCases([])
        setSelectedCaseId('')
        return
      }

      const nextMatchId = nextMatches.some((item) => item.match_id === selectedMatchId)
        ? selectedMatchId
        : nextMatches[0].match_id

      setSelectedMatchId(nextMatchId)
    } catch (error) {
      setMatchError(
        error instanceof Error && error.message ? error.message : 'The backend is unavailable. Retry when the API is running.',
      )
      setMatches([])
      setSelectedMatchId('')
    } finally {
      setMatchLoading(false)
    }
  }

  useEffect(() => {
    loadMatches()
  }, [])

  useEffect(() => {
    if (!selectedMatchId) {
      setMatchData(null)
      setEvents([])
      setState(null)
      setCases([])
      setSelectedCaseId('')
      setCaseNotifications([])
      previousCaseIdsRef.current = new Set()
      return
    }

    let active = true

    const loadSelectedMatch = async () => {
      try {
        const payload = await safeFetchJson(`${API_BASE}/api/matches/${selectedMatchId}`)
        if (!active) {
          return
        }
        setMatchData(payload)
      } catch (error) {
        console.error('Failed to load selected match data', error)
      }
    }

    const loadEvents = async () => {
      try {
        const payload = await safeFetchJson(`${API_BASE}/api/matches/${selectedMatchId}/events`)
        if (!active) {
          return
        }
        setEvents(payload.events || [])
        setCurrentIndex(0)
        setIsPlaying(false)
        setCases([])
        setSelectedCaseId('')
        setCaseNotifications([])
        previousCaseIdsRef.current = new Set()
      } catch (error) {
        console.error('Failed to load match events', error)
      }
    }

    loadSelectedMatch()
    loadEvents()

    return () => {
      active = false
    }
  }, [selectedMatchId])

  useEffect(() => {
    if (!selectedMatchId || events.length === 0) {
      return
    }

    const throughEvent = Math.min(currentIndex + 1, events.length)
    const loadState = async () => {
      try {
        const payload = await safeFetchJson(
          `${API_BASE}/api/matches/${selectedMatchId}/state?through_event=${throughEvent}`,
        )
        setState(payload.state)
      } catch (error) {
        console.error('Failed to load replay state', error)
      }
    }

    const currentTimestamp = Number(events[Math.max(0, currentIndex)]?.timestamp ?? 0)
    const loadCases = async () => {
      try {
        const payload = await safeFetchJson(
          `${API_BASE}/api/matches/${selectedMatchId}/cases?through_timestamp=${currentTimestamp}`,
        )
        const nextCases = payload.cases || []
        setCases(nextCases)
        setSelectedCaseId((previousCaseId) => {
          if (previousCaseId && nextCases.some((item) => item.case_id === previousCaseId)) {
            return previousCaseId
          }
          return nextCases[0]?.case_id || ''
        })
      } catch (error) {
        console.error('Failed to load match cases', error)
      }
    }

    loadState()
    loadCases()
  }, [selectedMatchId, currentIndex, events])

  useEffect(() => {
    if (!isPlaying || events.length === 0) {
      return undefined
    }

    const timer = window.setInterval(() => {
      setCurrentIndex((previous) => {
        if (previous >= events.length - 1) {
          setIsPlaying(false)
          return previous
        }
        return previous + 1
      })
    }, 1000 / replaySpeed)

    return () => window.clearInterval(timer)
  }, [events.length, isPlaying, replaySpeed])

  useEffect(() => {
    if (!cases.length) {
      previousCaseIdsRef.current = new Set()
      return
    }

    const previousCaseIds = previousCaseIdsRef.current
    const newlyAvailable = cases.filter((caseItem) => !previousCaseIds.has(caseItem.case_id))
    previousCaseIdsRef.current = new Set(cases.map((caseItem) => caseItem.case_id))

    if (!newlyAvailable.length) {
      return
    }

    setCaseNotifications((previous) => [
      ...newlyAvailable.map((caseItem) => ({ case_id: caseItem.case_id, title: caseItem.title })),
      ...previous,
    ].slice(0, 3))

    const timeout = window.setTimeout(() => {
      setCaseNotifications((previous) =>
        previous.filter(
          (notification) => !newlyAvailable.some((caseItem) => caseItem.case_id === notification.case_id),
        ),
      )
    }, 5000)

    return () => window.clearTimeout(timeout)
  }, [cases])

  const liveEvents = useMemo(() => events.slice(0, currentIndex + 1), [currentIndex, events])
  const activeScore = state?.score || { home: 0, away: 0 }
  const scoreText = `${activeScore.home} - ${activeScore.away}`
  const possession = state?.possession || { home: 0, away: 0 }
  const passCompletion = state?.pass_completion || { home: null, away: null }
  const homePossession = Number(possession.home) || 0
  const awayPossession = Number(possession.away) || 0
  const homePassRate = Number(passCompletion.home)
  const awayPassRate = Number(passCompletion.away)

  const handleReset = () => {
    setCurrentIndex(0)
    setIsPlaying(false)
    setCases([])
    setSelectedCaseId('')
    setCaseNotifications([])
    previousCaseIdsRef.current = new Set()
  }

  const handlePlayPause = () => {
    if (currentIndex >= events.length - 1 && events.length > 0) {
      setCurrentIndex(0)
    }
    setIsPlaying((previous) => !previous)
  }

  const goToLobby = () => {
    setScreen('lobby')
  }

  const goToLive = () => {
    setScreen('live')
  }

  const openCourtroom = (caseItem = null) => {
    if (caseItem) {
      setSelectedCaseId(caseItem.case_id)
    }
    setScreen('courtroom')
  }

  const renderLobby = () => (
    <main className="landing-page">
      <div className="spotlight" aria-hidden="true" />
      <p className="eyebrow">Premier League × Microsoft Hackathon</p>
      <h1>Football Courtroom</h1>
      <p className="subtitle">Every Moment Has Two Sides</p>

      <button type="button" className="primary-btn" onClick={goToLive}>
        Enter Live Match
      </button>
    </main>
  )

  const renderLiveMatch = () => (
    <main className="live-page">
      <div className="live-header">
        <div>
          <p className="eyebrow">Synthetic Match Feed</p>
          <h2>Live Match Replay</h2>
        </div>
        <span className="synthetic-badge">Deterministic evidence</span>
      </div>

      {matchLoading ? (
        <section className="panel status-panel">
          <p className="empty-state">Loading synthetic matches…</p>
        </section>
      ) : matchError ? (
        <section className="panel status-panel error-panel">
          <p className="error-text">{matchError}</p>
          <button type="button" className="primary-btn small" onClick={loadMatches}>
            Retry
          </button>
        </section>
      ) : (
        <>
          <div className="live-controls panel compact-panel">
            <div className="match-picker">
              <label htmlFor="match-select">Select match</label>
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
            </div>

            <div className="replay-controls">
              <button type="button" className="primary-btn small" onClick={handlePlayPause} disabled={!events.length}>
                {isPlaying ? 'Pause' : 'Play'}
              </button>
              <button type="button" className="secondary-btn small" onClick={handleReset} disabled={!events.length}>
                Reset
              </button>
              <div className="speed-controls" aria-label="Replay speed controls">
                {[0.5, 1, 2].map((speed) => (
                  <button
                    type="button"
                    key={speed}
                    className={replaySpeed === speed ? 'speed active' : 'speed'}
                    onClick={() => setReplaySpeed(speed)}
                  >
                    {speed}x
                  </button>
                ))}
              </div>
            </div>
          </div>

          {caseNotifications.length > 0 ? (
            <div className="case-toast-stack" aria-live="polite">
              {caseNotifications.map((notification) => (
                <button
                  key={notification.case_id}
                  type="button"
                  className="case-toast"
                  onClick={() => openCourtroom(cases.find((item) => item.case_id === notification.case_id))}
                >
                  <strong>New case available</strong>
                  <span>{notification.title}</span>
                </button>
              ))}
            </div>
          ) : null}

          {matchData ? (
            <section className="match-overview panel compact-panel">
              <div className="team-block">
                <span className="team-crest purple">{matchData.home_team.slice(0, 1)}</span>
                <div>
                  <small>Home</small>
                  <strong>{matchData.home_team}</strong>
                </div>
              </div>

              <div className="score-wrap">
                <span className="score">{scoreText}</span>
                <small>{state ? formatClock(state.match_clock_seconds) : '00:00'}</small>
              </div>

              <div className="team-block right">
                <div>
                  <small>Away</small>
                  <strong>{matchData.away_team}</strong>
                </div>
                <span className="team-crest gold">{matchData.away_team.slice(0, 1)}</span>
              </div>
            </section>
          ) : null}

          <div className="live-grid">
            <section className="panel compact-panel">
              <div className="panel-header">
                <span className="panel-kicker">Live statistics</span>
                <h3>Match state</h3>
              </div>

              {state ? (
                <div className="stats-grid">
                  <div className="stat-box">
                    <span>Possession</span>
                    <strong>
                      {Number.isFinite(homePossession) && Number.isFinite(awayPossession)
                        ? `${formatPercent(homePossession)} - ${formatPercent(awayPossession)}`
                        : 'N/A - N/A'}
                    </strong>
                  </div>
                  <div className="stat-box">
                    <span>Pass completion</span>
                    <strong>
                      {Number.isFinite(homePassRate) ? formatPassRate(homePassRate) : 'N/A'} -{' '}
                      {Number.isFinite(awayPassRate) ? formatPassRate(awayPassRate) : 'N/A'}
                    </strong>
                  </div>
                  <div className="stat-box">
                    <span>Shots</span>
                    <strong>
                      {state.shots.home} - {state.shots.away}
                    </strong>
                  </div>
                  <div className="stat-box">
                    <span>Fouls</span>
                    <strong>
                      {state.fouls.home} - {state.fouls.away}
                    </strong>
                  </div>
                  <div className="stat-box">
                    <span>Pressure</span>
                    <strong>
                      {state.pressure_events.home} - {state.pressure_events.away}
                    </strong>
                  </div>
                  <div className="stat-box">
                    <span>Cards</span>
                    <strong>
                      {state.yellow_cards.home + state.red_cards.home} -{' '}
                      {state.yellow_cards.away + state.red_cards.away}
                    </strong>
                  </div>
                </div>
              ) : (
                <p className="empty-state">Loading synthetic state...</p>
              )}
            </section>

            <section className="panel compact-panel event-panel">
              <div className="panel-header">
                <span className="panel-kicker">Event feed</span>
                <h3>Chronological replay</h3>
              </div>

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
            </section>
          </div>

          <section className="panel compact-panel case-panel">
            <div className="panel-header">
              <span className="panel-kicker">Deterministic case detection</span>
              <h3>Courtroom cases</h3>
            </div>

            {cases.length === 0 ? (
              <p className="empty-state">
                No courtroom cases are eligible at the current replay timestamp. New cases become visible only after the relevant match events are in view.
              </p>
            ) : (
              <div className="case-layout">
                <div className="case-list">
                  {cases.map((caseItem) => (
                    <button
                      key={caseItem.case_id}
                      type="button"
                      className={selectedCase?.case_id === caseItem.case_id ? 'case-item active' : 'case-item'}
                      onClick={() => openCourtroom(caseItem)}
                    >
                      <span className="case-tag">{caseItem.case_type.replace(/_/g, ' ')}</span>
                      <strong>{caseItem.title}</strong>
                      <small>{formatClock(caseItem.detection_timestamp)}</small>
                    </button>
                  ))}
                </div>

                <div className="case-detail">
                  <div className="case-detail-header">
                    <span className="case-mode">Deterministic layer</span>
                    <strong>{selectedCase?.title || 'No case selected'}</strong>
                    <small>
                      Match {selectedCase?.match_id || selectedMatchId} • Detected at{' '}
                      {selectedCase ? formatClock(selectedCase.detection_timestamp) : '00:00'}
                    </small>
                  </div>

                  <div className="case-meta-grid">
                    <div>
                      <span>Question</span>
                      <strong>{selectedCase?.title || 'N/A'}</strong>
                    </div>
                    <div>
                      <span>Trigger</span>
                      <strong>{selectedCase?.trigger_event_ids?.join(', ') || 'N/A'}</strong>
                    </div>
                    <div>
                      <span>Confidence</span>
                      <strong>{selectedCase?.confidence || 'N/A'}</strong>
                    </div>
                    <div>
                      <span>Relevant window</span>
                      <strong>
                        {selectedCase?.relevant_windows?.map(
                          (windowItem) =>
                            `${windowItem.label}: ${formatClock(windowItem.start)}-${formatClock(windowItem.end)}`,
                        ).join(' • ') || 'N/A'}
                      </strong>
                    </div>
                  </div>

                  <div className="case-section">
                    <h4>Supporting evidence</h4>
                    <ul>
                      {selectedCase?.evidence?.map((item) => (
                        <li key={`${selectedCase.case_id}-${item.label}`}>
                          <strong>{item.label}</strong>
                          <span>{item.value}</span>
                          <small>{item.context}</small>
                          <em>Events: {item.event_ids?.join(', ') || 'N/A'}</em>
                        </li>
                      )) || <li>No evidence available.</li>}
                    </ul>
                  </div>

                  <div className="case-section muted">
                    <h4>Counterevidence</h4>
                    <ul>
                      {(selectedCase?.counterevidence || []).map((item) => (
                        <li key={`${selectedCase.case_id}-counter-${item}`}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="case-section">
                    <h4>Limitations</h4>
                    <ul>
                      {(selectedCase?.limitations || []).map((item) => (
                        <li key={`${selectedCase.case_id}-limit-${item}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )

  const renderCourtroom = () => {
    if (!selectedCase) {
      return (
        <main className="courtroom-page empty-courtroom">
          <div className="panel compact-panel empty-panel">
            <p className="eyebrow">No case selected</p>
            <h2>No courtroom case is currently available.</h2>
            <p className="empty-state">
              Select a live match and replay to a moment where deterministic case detection triggers evidence.
            </p>
            <button type="button" className="primary-btn" onClick={goToLive}>
              Back to Live Match
            </button>
          </div>
        </main>
      )
    }

    const caseTypeLabel = selectedCase.case_type?.replace(/_/g, ' ') || 'Case'
    const caseEvidence = selectedCase.evidence || []
    const counterEvidence = selectedCase.counterevidence || []
    const limitations = selectedCase.limitations || []
    const relevantWindows = selectedCase.relevant_windows || []

    return (
      <main className="courtroom-page">
        <div className="courtroom-header compact-header">
          <div>
            <p className="eyebrow">Deterministic case review</p>
            <h2>{selectedCase.title}</h2>
          </div>
          <div className="header-actions">
            <button type="button" className="secondary-btn" onClick={goToLive}>
              Back to Live Match
            </button>
            <button type="button" className="secondary-btn" onClick={goToLobby}>
              Lobby
            </button>
          </div>
        </div>

        <section className="match-overview panel compact-panel">
          <div className="team-block">
            <span className="team-crest purple">{(matchData?.home_team || selectedMatchId).slice(0, 1).toUpperCase()}</span>
            <div>
              <small>Home</small>
              <strong>{matchData?.home_team || 'Match home team'}</strong>
            </div>
          </div>

          <div className="score-wrap">
            <span className="score">{scoreText}</span>
            <small>{selectedCase ? formatClock(selectedCase.detection_timestamp) : '00:00'}</small>
          </div>

          <div className="team-block right">
            <div>
              <small>Away</small>
              <strong>{matchData?.away_team || 'Match away team'}</strong>
            </div>
            <span className="team-crest gold">{(matchData?.away_team || selectedMatchId).slice(0, 1).toUpperCase()}</span>
          </div>
        </section>

        <div className="courtroom-grid compact-grid">
          <section className="panel compact-panel">
            <div className="panel-header">
              <span className="panel-kicker">Case summary</span>
              <h3>{caseTypeLabel}</h3>
            </div>
            <ul className="detail-list">
              <li>
                <span>Question</span>
                <strong>{selectedCase.title}</strong>
              </li>
              <li>
                <span>Match</span>
                <strong>{selectedCase.match_id || selectedMatchId}</strong>
              </li>
              <li>
                <span>Detected</span>
                <strong>{formatClock(selectedCase.detection_timestamp)}</strong>
              </li>
              <li>
                <span>Confidence</span>
                <strong>{selectedCase.confidence || 'N/A'}</strong>
              </li>
            </ul>
          </section>

          <section className="panel compact-panel">
            <div className="panel-header">
              <span className="panel-kicker">Evidence</span>
              <h3>Supporting signal</h3>
            </div>
            <div className="stack-list">
              {caseEvidence.length ? (
                caseEvidence.map((item) => (
                  <div key={`${selectedCase.case_id}-${item.label}`} className="mini-card">
                    <strong>{item.label}</strong>
                    <span>{item.value}</span>
                    <small>{item.context}</small>
                  </div>
                ))
              ) : (
                <p className="empty-state">No evidence recorded for this case.</p>
              )}
            </div>
          </section>

          <section className="panel compact-panel">
            <div className="panel-header">
              <span className="panel-kicker">Counterevidence</span>
              <h3>Context check</h3>
            </div>
            <ul className="argument-list compact-list">
              {counterEvidence.length ? (
                counterEvidence.map((item) => <li key={`${selectedCase.case_id}-counter-${item}`}>{item}</li>)
              ) : (
                <li>No counterevidence is available for this case.</li>
              )}
            </ul>
          </section>

          <section className="panel compact-panel">
            <div className="panel-header">
              <span className="panel-kicker">Limitations</span>
              <h3>Known caveats</h3>
            </div>
            <ul className="argument-list compact-list">
              {limitations.length ? (
                limitations.map((item) => <li key={`${selectedCase.case_id}-limit-${item}`}>{item}</li>)
              ) : (
                <li>No limitations are recorded for this case.</li>
              )}
            </ul>
          </section>

          <section className="panel judge-panel compact-panel">
            <div className="panel-header">
              <span className="panel-kicker">Windowing</span>
              <h3>Relevant timeline</h3>
            </div>
            <div className="mini-grid">
              {relevantWindows.length ? (
                relevantWindows.map((windowItem, index) => (
                  <div key={`${selectedCase.case_id}-window-${index}`} className="mini-card">
                    <strong>{windowItem.label}</strong>
                    <span>
                      {formatClock(windowItem.start)}–{formatClock(windowItem.end)}
                    </span>
                  </div>
                ))
              ) : (
                <p className="empty-state">No relevant windows recorded.</p>
              )}
            </div>
          </section>

          <section className="panel compact-panel agent-panel">
            <div className="panel-header">
              <span className="panel-kicker">Future agent slots</span>
              <h3>Prepared for evidence agents</h3>
            </div>
            <div className="agent-grid">
              <div className="agent-slot">
                <span>Evidence</span>
                <strong>Queue ready</strong>
              </div>
              <div className="agent-slot">
                <span>Prosecution</span>
                <strong>Not yet connected</strong>
              </div>
              <div className="agent-slot">
                <span>Defense</span>
                <strong>Not yet connected</strong>
              </div>
              <div className="agent-slot">
                <span>Judge</span>
                <strong>Not yet connected</strong>
              </div>
            </div>
          </section>
        </div>
      </main>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button type="button" className="brand button-brand" onClick={goToLobby}>
          <span className="brand-mark">FC</span>
          <span>Football Courtroom</span>
        </button>

        <nav className="topnav" aria-label="Primary navigation">
          <button type="button" className={screen === 'lobby' ? 'secondary-btn active' : 'secondary-btn'} onClick={goToLobby}>
            Lobby
          </button>
          <button type="button" className={screen === 'live' ? 'secondary-btn active' : 'secondary-btn'} onClick={goToLive}>
            Live Match
          </button>
          <button
            type="button"
            className={screen === 'courtroom' ? 'secondary-btn active' : 'secondary-btn'}
            onClick={() => openCourtroom(selectedCase)}
          >
            Courtroom
          </button>
        </nav>
      </header>

      {screen === 'lobby' ? renderLobby() : null}
      {screen === 'live' ? renderLiveMatch() : null}
      {screen === 'courtroom' ? renderCourtroom() : null}
    </div>
  )
}

export default App
