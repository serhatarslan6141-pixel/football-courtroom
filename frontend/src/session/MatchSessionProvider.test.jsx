import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { MatchSessionProvider } from './MatchSessionProvider.jsx'
import { useMatchSession } from './useMatchSession.js'
import { deferred, events, matches, snapshot } from '../test/fixtures.js'

function SessionProbe() {
  const session = useMatchSession()
  return (
    <>
      <button onClick={() => session.setSelectedMatchId('a')}>Select A</button>
      <button onClick={() => session.setSelectedMatchId('b')}>Select B</button>
      <output>{session.matchData?.home_team || 'Loading'}</output>
    </>
  )
}

it('ignores obsolete metadata and events after A → B → A even if transport ignores abort', async () => {
  const oldA = deferred()
  let aLoads = 0
  const api = {
    listMatches: vi.fn(async () => ({ matches })),
    loadMatch: vi.fn((id) => {
      if (id === 'a' && ++aLoads === 1) return oldA.promise
      return Promise.resolve({ matchData: matches.find((item) => item.match_id === id), events })
    }),
    loadSnapshot: vi.fn(async (id, timestamp) => snapshot(timestamp, id)),
  }
  render(<StrictMode><MatchSessionProvider api={api}><SessionProbe /></MatchSessionProvider></StrictMode>)
  await waitFor(() => expect(api.loadMatch).toHaveBeenCalledWith('a', expect.any(AbortSignal)))
  const oldSignal = api.loadMatch.mock.calls[0][1]
  fireEvent.click(screen.getByRole('button', { name: 'Select B' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Gamma'))
  expect(oldSignal.aborted).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Select A' }))
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Alpha'))
  await act(async () => oldA.resolve({ matchData: { ...matches[0], home_team: 'Obsolete Alpha' }, events: [] }))
  expect(screen.getByRole('status').textContent).toBe('Alpha')
})
