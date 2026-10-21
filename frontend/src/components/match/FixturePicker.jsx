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
    <main className="fixture-lobby" id="main-content" tabIndex={-1}>
      <div className="fixture-intro">
        <div><span className="broadcast-kicker">Match selection</span><h1>Choose your match.</h1></div>
        <p>Select a fixture to explore its replay, or create a fresh match.</p>
      </div>
      <section aria-label="Choose a fixture" className="fixture-selection">
        <div className="fixture-section-heading">
          <div>
            <h2>Fixtures</h2>
            <span>{matches.length} available</span>
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
                      : 'FIXTURE'}{' '}
                    /{' '}
                    {String(currentPage * pageSize + index + 1).padStart(
                      2,
                      '0',
                    )}
                  </span>
                  <span>{selected ? '✓ Selected' : '90 min'}</span>
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
                  {selected ? 'Ready for replay' : 'Select fixture'}
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
            Creating your match…
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
              : 'Select a fixture to continue.'}
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
    </main>
  )
}
