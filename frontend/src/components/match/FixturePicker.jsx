import { clubFor } from '../../domain/broadcast.js'
import ClubCrest from './ClubCrest.jsx'
import BroadcastIcon from './BroadcastIcon.jsx'

export default function FixturePicker({
  matches,
  selectedId,
  onSelect,
  onEnter,
  loading,
  error,
  onRetry,
}) {
  return (
    <main className="fixture-lobby">
      <div className="fixture-intro">
        <span className="broadcast-kicker">
          THE MATCH IS ONLY HALF THE STORY
        </span>
        <h1>
          Pick your
          <br />
          <em>point of view.</em>
        </h1>
        <p>
          Follow the football. Find the turning point.
          <br />
          Take the moments that matter to court.
        </p>
      </div>
      <section aria-label="Choose a fixture" className="fixture-selection">
        <div className="fixture-section-heading">
          <h2>Tonight’s fixtures</h2>
          <span>{matches.length} simulated matches</span>
        </div>
        <div className="fixture-tiles">
          {matches.map((match, index) => {
            const home = clubFor(match, 'home')
            const away = clubFor(match, 'away')
            const selected = selectedId === match.match_id
            return (
              <button
                type="button"
                key={match.match_id}
                className={`fixture-tile${selected ? ' is-selected' : ''}`}
                aria-pressed={selected}
                aria-label={`Select ${home.name} vs ${away.name}`}
                onClick={() => onSelect(match.match_id)}
                style={{
                  '--home-color': home.color,
                  '--away-color': away.color,
                }}
              >
                <span className="fixture-tile-meta">
                  <span>MATCH 0{index + 1}</span>
                  <span>{selected ? 'SELECTED' : '90 MIN'}</span>
                </span>
                <span className="fixture-clubs">
                  <ClubCrest club={home} />
                  <span className="fixture-versus">VS</span>
                  <ClubCrest club={away} />
                </span>
                <span className="fixture-names">
                  <strong>{home.name}</strong>
                  <span>vs</span>
                  <strong>{away.name}</strong>
                </span>
                <span className="fixture-tile-footer">
                  {selected ? 'Your fixture' : 'Choose fixture'}
                  <BroadcastIcon name={selected ? 'ball' : 'arrow'} size={16} />
                </span>
              </button>
            )
          })}
        </div>
        {!matches.length && !loading && !error ? (
          <p>No fixtures available.</p>
        ) : null}
        {error ? (
          <p role="alert" className="broadcast-error">
            {error}{' '}
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          </p>
        ) : null}
        <div className="fixture-entry">
          <span>
            <i className="status-dot" /> Fictional clubs. Real debate.
          </span>
          <button
            type="button"
            className="broadcast-primary"
            onClick={onEnter}
            disabled={loading || !selectedId || !!error}
          >
            {loading ? 'Preparing replay…' : 'Enter replay'}
            <BroadcastIcon name="arrow" />
          </button>
        </div>
      </section>
      <div className="fixture-disclosure">
        SIMULATED MATCH DATA <span>•</span> FOOTBALL COURTROOM
      </div>
    </main>
  )
}
