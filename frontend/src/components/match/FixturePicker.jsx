import { useState } from 'react'
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
  onCreate,
  creating = false,
  creationError,
}) {
  const pageSize = 3
  const [pageSelection, setPageSelection] = useState(null)
  const selected = matches.find((match) => match.match_id === selectedId)
  const pageCount = Math.max(1, Math.ceil(matches.length / pageSize))
  const selectedPage = Math.floor(
    Math.max(
      0,
      matches.findIndex((match) => match.match_id === selectedId),
    ) / pageSize,
  )
  const currentPage = Math.min(
    pageSelection?.selectedId === selectedId
      ? pageSelection.page
      : selectedPage,
    pageCount - 1,
  )
  const setPage = (page) => setPageSelection({ selectedId, page })
  const fixtures = matches.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize,
  )
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
          <div>
            <h2>Your match collection</h2>
            <span>{matches.length} simulated matches</span>
          </div>
          <button
            type="button"
            className="fixture-create"
            onClick={onCreate}
            disabled={creating || loading}
          >
            <span aria-hidden="true">＋</span>
            {creating ? 'Creating match…' : 'Create a new match'}
          </button>
        </div>
        <div className="fixture-tiles">
          {fixtures.map((match, index) => {
            const home = clubFor(match, 'home')
            const away = clubFor(match, 'away')
            const selected = selectedId === match.match_id
            return (
              <button
                type="button"
                key={match.match_id}
                className={`fixture-tile${selected ? ' is-selected' : ''}`}
                aria-pressed={selected}
                aria-label={`Select ${home.name} vs ${away.name}${match.generation_mode === 'varied-v1' ? ` · Match ${currentPage * pageSize + index + 1}` : ''}`}
                onClick={() => onSelect(match.match_id)}
                style={{
                  '--home-color': home.color,
                  '--away-color': away.color,
                }}
              >
                <span className="fixture-tile-meta">
                  <span>
                    {match.generation_mode === 'varied-v1'
                      ? 'NEW MATCH'
                      : 'DEMO'}{' '}
                    /{' '}
                    {String(currentPage * pageSize + index + 1).padStart(
                      2,
                      '0',
                    )}
                  </span>
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
        {pageCount > 1 ? (
          <div className="fixture-pagination" aria-label="Fixture pages">
            <button
              type="button"
              aria-label="Previous fixtures"
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
            >
              ← Previous
            </button>
            <span>
              {currentPage * pageSize + 1}–
              {Math.min(matches.length, (currentPage + 1) * pageSize)} of{' '}
              {matches.length}
            </span>
            <button
              type="button"
              aria-label="Next fixtures"
              disabled={currentPage >= pageCount - 1}
              onClick={() => setPage(currentPage + 1)}
            >
              Next →
            </button>
          </div>
        ) : null}
        {creating ? (
          <p className="fixture-creation-status" role="status">
            Preparing a new 90 minutes. Your existing matches are safe to
            revisit.
          </p>
        ) : null}
        {creationError ? (
          <p className="broadcast-error" role="alert">
            Couldn’t create a match: {creationError}. Try again or choose an
            existing fixture.
          </p>
        ) : null}
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
            <i className="status-dot" />{' '}
            {selected
              ? `Selected: ${selected.home_team} vs ${selected.away_team}`
              : 'Fictional clubs. Real debate.'}
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
