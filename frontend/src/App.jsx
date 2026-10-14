import { useEffect, useMemo, useState } from 'react'
import './App.css'

const matchSummary = {
  home: 'Northbridge City',
  away: 'Harbor Athletic',
  venue: 'The Crown Ground',
  minute: '72\'',
  score: '1 - 1',
  narrative: 'A tactical change is under review after the manager introduced a more aggressive press pattern.',
}

const evidence = [
  { label: 'Possession', value: '48% - 52%' },
  { label: 'Progressive passes', value: '31 - 20' },
  { label: 'High press wins', value: '12 - 7' },
  { label: 'Midfield duels won', value: '23 - 18' },
]

const prosecution = [
  'The substitution shifted the team from a compact midfield block into a stretched 4-3-3 shape.',
  'Within five minutes, the opposition created three high-value entries through the central channels.',
  'The change reduced ball retention and allowed the opponent to control the tempo of the game.',
]

const defense = [
  'The substitute was introduced to respond to an overload on the left wing and recovered the team structure.',
  'The equalising chance came from a set-piece sequence, not a breakdown in midfield control.',
  'The wider sample shows the side remained more dangerous in transition after the change.',
]

const judge = {
  verdict: 'Split verdict',
  confidence: '71%',
  reasoning:
    'The evidence suggests the substitution increased attacking risk, but the decision was contextually justified because the team was chasing an imbalance on the left side. The case is therefore not a clear liability, yet it did materially alter the game state.',
}

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

function App() {
  const [screen, setScreen] = useState('landing')
  const [entered, setEntered] = useState(false)
  const [matches, setMatches] = useState([])
  const [selectedMatchId, setSelectedMatchId] = useState('')
  const [matchData, setMatchData] = useState(null)
  const [events, setEvents] = useState([])
  const [state, setState] = useState(null)
  const [replaySpeed, setReplaySpeed] = useState(1)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  useEffect(() => {
    const fetchMatches = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/matches')
        const payload = await response.json()
        const nextMatches = payload.matches || []
        setMatches(nextMatches)
        if (nextMatches.length > 0) {
          setSelectedMatchId(nextMatches[0].match_id)
        }
      } catch (error) {
        console.error('Failed to load synthetic matches', error)
      }
    }

    fetchMatches()
  }, [])

  useEffect(() => {
    if (!selectedMatchId) {
      return
    }

    const fetchMatch = async () => {
      const response = await fetch(`http://localhost:8000/api/matches/${selectedMatchId}`)
      const payload = await response.json()
      setMatchData(payload)
    }

    fetchMatch()
  }, [selectedMatchId])

  useEffect(() => {
    if (!selectedMatchId) {
      return
    }

    const fetchEvents = async () => {
      const response = await fetch(`http://localhost:8000/api/matches/${selectedMatchId}/events`)
      const payload = await response.json()
      setEvents(payload.events || [])
      setCurrentIndex(0)
      setIsPlaying(false)
    }

    fetchEvents()
  }, [selectedMatchId])

  useEffect(() => {
    if (!selectedMatchId || events.length === 0) {
      return
    }

    const throughEvent = Math.min(currentIndex + 1, events.length)
    const fetchState = async () => {
      const response = await fetch(
        `http://localhost:8000/api/matches/${selectedMatchId}/state?through_event=${throughEvent}`,
      )
      const payload = await response.json()
      setState(payload.state)
    }

    fetchState()
  }, [selectedMatchId, currentIndex, events.length])

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
  }

  const handlePlayPause = () => {
    if (currentIndex >= events.length - 1 && events.length > 0) {
      setCurrentIndex(0)
    }
    setIsPlaying((previous) => !previous)
  }

  const goToCourtroom = () => {
    setEntered(true)
    setScreen('courtroom')
  }

  const goToLive = () => {
    setScreen('live')
    setEntered(true)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">FC</span>
          <span>Football Courtroom</span>
        </div>

        {entered ? (
          <nav className="topnav" aria-label="Primary navigation">
            <button type="button" className="secondary-btn" onClick={() => setScreen('courtroom')}>
              Courtroom
            </button>
            <button type="button" className="secondary-btn" onClick={() => setScreen('live')}>
              Live Match
            </button>
            <button type="button" className="secondary-btn" onClick={() => setScreen('landing')}>
              Lobby
            </button>
          </nav>
        ) : null}
      </header>

      {screen === 'landing' && !entered ? (
        <main className="landing-page">
          <div className="spotlight" aria-hidden="true" />
          <p className="eyebrow">Premier League × Microsoft Hackathon</p>
          <h1>Football Courtroom</h1>
          <p className="subtitle">Every Moment Has Two Sides</p>

          <button type="button" className="primary-btn" onClick={goToCourtroom}>
            Enter the Courtroom
          </button>

          <div className="landing-meta">
            <div>
              <span className="meta-label">Case Type</span>
              <strong>Substitution review</strong>
            </div>
            <div>
              <span className="meta-label">Format</span>
              <strong>AI trial simulation</strong>
            </div>
            <div>
              <span className="meta-label">Mode</span>
              <strong>Mock analyst feed</strong>
            </div>
          </div>
        </main>
      ) : null}

      {screen === 'courtroom' ? (
        <main className="courtroom-page">
          <div className="courtroom-header">
            <div>
              <p className="eyebrow">Case 07 • Synthetic Match Review</p>
              <h2>Did the substitution cost the team control of midfield?</h2>
            </div>
            <div className="header-actions">
              <button type="button" className="secondary-btn" onClick={goToLive}>
                Open Live Match
              </button>
              <span className="status-pill">Open case</span>
            </div>
          </div>

          <section className="match-overview panel">
            <div className="team-block">
              <span className="team-crest purple">N</span>
              <div>
                <small>Home</small>
                <strong>{matchSummary.home}</strong>
              </div>
            </div>

            <div className="score-wrap">
              <span className="score">{matchSummary.score}</span>
              <small>{matchSummary.minute}</small>
            </div>

            <div className="team-block right">
              <div>
                <small>Away</small>
                <strong>{matchSummary.away}</strong>
              </div>
              <span className="team-crest gold">H</span>
            </div>
          </section>

          <div className="courtroom-grid">
            <section className="panel">
              <div className="panel-header">
                <span className="panel-kicker">Match Information</span>
                <h3>Game context</h3>
              </div>
              <ul className="detail-list">
                <li>
                  <span>Venue</span>
                  <strong>{matchSummary.venue}</strong>
                </li>
                <li>
                  <span>Phase</span>
                  <strong>Late pressing phase</strong>
                </li>
                <li>
                  <span>Trigger</span>
                  <strong>Second-half tactical switch</strong>
                </li>
                <li>
                  <span>Narrative</span>
                  <strong>{matchSummary.narrative}</strong>
                </li>
              </ul>
            </section>

            <section className="panel">
              <div className="panel-header">
                <span className="panel-kicker">Evidence</span>
                <h3>What the numbers say</h3>
              </div>
              <div className="stats-row">
                {evidence.map((item) => (
                  <div key={item.label} className="stat-card">
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <span className="panel-kicker">Prosecution</span>
                <h3>Argument for guilt</h3>
              </div>
              <ul className="argument-list">
                {prosecution.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </section>

            <section className="panel">
              <div className="panel-header">
                <span className="panel-kicker">Defense</span>
                <h3>Argument for innocence</h3>
              </div>
              <ul className="argument-list defend">
                {defense.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </section>

            <section className="panel judge-panel">
              <div className="panel-header">
                <span className="panel-kicker">Judge</span>
                <h3>Verdict</h3>
              </div>
              <div className="judge-summary">
                <div>
                  <span className="judgement-label">Decision</span>
                  <strong>{judge.verdict}</strong>
                </div>
                <div>
                  <span className="judgement-label">Confidence</span>
                  <strong>{judge.confidence}</strong>
                </div>
              </div>
              <p>{judge.reasoning}</p>
            </section>
          </div>
        </main>
      ) : null}

      {screen === 'live' ? (
        <main className="live-page">
          <div className="live-header">
            <div>
              <p className="eyebrow">Synthetic Match Feed</p>
              <h2>Live Match Replay</h2>
            </div>
            <span className="synthetic-badge">Synthetic data</span>
          </div>

          <div className="live-controls panel">
            <div className="match-picker">
              <label htmlFor="match-select">Select match</label>
              <select
                id="match-select"
                value={selectedMatchId}
                onChange={(event) => setSelectedMatchId(event.target.value)}
              >
                {matches.map((item) => (
                  <option key={item.match_id} value={item.match_id}>
                    {item.home_team} vs {item.away_team}
                  </option>
                ))}
              </select>
            </div>

            <div className="replay-controls">
              <button type="button" className="primary-btn small" onClick={handlePlayPause}>
                {isPlaying ? 'Pause' : 'Play'}
              </button>
              <button type="button" className="secondary-btn small" onClick={handleReset}>
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

          {matchData ? (
            <section className="match-overview panel">
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
            <section className="panel">
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

            <section className="panel event-panel">
              <div className="panel-header">
                <span className="panel-kicker">Event feed</span>
                <h3>Chronological replay</h3>
              </div>

              <ul className="event-list">
                {liveEvents.map((event) => {
                  const eventTeam = normalizeTeamKey(event.team_id) === 'home' ? matchData?.home_team : matchData?.away_team
                  return (
                    <li key={event.event_id}>
                      <span className="event-time">{event.minute}</span>
                      <div>
                        <strong>{event.event_type.replace(/_/g, ' ')}</strong>
                        <small>{eventTeam}</small>
                        <p>{describeEvent(event, matchData)}</p>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>
          </div>
        </main>
      ) : null}
    </div>
  )
}

export default App
