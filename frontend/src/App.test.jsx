import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'
import { deferred, events, matches, snapshot } from './test/fixtures.js'

function makeApi() {
  return {
    listMatches: vi.fn(async () => ({ matches })),
    loadMatch: vi.fn(async (id) => ({ matchData: matches.find((item) => item.match_id === id), events })),
    loadSnapshot: vi.fn(async (id, timestamp) => snapshot(timestamp, id)),
  }
}

async function enterMatch(api) {
  render(<App api={api} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Enter the match' }))
  await screen.findByRole('heading', { name: 'Alpha vs Beta' })
  return user
}

afterEach(() => vi.useRealTimers())

describe('scene and replay integration', () => {
  it('keeps the display synchronized while a snapshot is pending, then pauses in court', async () => {
    const api = makeApi()
    const pending = deferred()
    api.loadSnapshot.mockImplementation((id, timestamp) => timestamp === 10 ? pending.promise : Promise.resolve(snapshot(timestamp, id)))
    await enterMatch(api)
    expect(screen.getByText('N/A / 0.0%')).toBeTruthy()
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Play', exact: true }))
    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(api.loadSnapshot).toHaveBeenLastCalledWith('a', 10, expect.any(AbortSignal))
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Case room' })).toBeNull()
    await act(async () => pending.resolve(snapshot(10)))
    expect(screen.getByText('1 - 0')).toBeTruthy()
    expect(screen.getByText('First pass')).toBeTruthy()
    expect(screen.getByText('Equal timestamp goal')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Case room' }))
    expect(screen.getByText('Prosecution case')).toBeTruthy()
    const calls = api.loadSnapshot.mock.calls.length
    await act(() => vi.advanceTimersByTimeAsync(10000))
    expect(api.loadSnapshot).toHaveBeenCalledTimes(calls)
    fireEvent.click(screen.getByRole('button', { name: 'Return to match' }))
    expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeTruthy()
    expect(screen.getByText('1 - 0')).toBeTruthy()
    expect(screen.getByText('00:10', { selector: '.score-wrap small' })).toBeTruthy()
  })

  it('preserves navigation, stats toggle, speed, reset and fixture selection', async () => {
    const api = makeApi()
    const user = await enterMatch(api)
    await user.click(screen.getByRole('button', { name: 'Hide stats' }))
    expect(screen.queryByText('Pass accuracy')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Show stats' }))
    expect(screen.getByText('Pass accuracy')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: '2x' }))
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Play', exact: true }))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(screen.getByText('1 - 0')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Reset', exact: true }))
    await act(async () => {})
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Case room' })).toBeNull()
    vi.useRealTimers()
    await user.selectOptions(screen.getByLabelText('Select fixture'), 'b')
    await screen.findByRole('heading', { name: 'Gamma vs Delta' })
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Welcome', exact: true }))
    expect(screen.getByRole('heading', { name: 'Every Moment Has Two Sides' })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Enter the match' }))
    expect(screen.getByRole('heading', { name: 'Gamma vs Delta' })).toBeTruthy()
  })

  it('aborts and ignores an old replay response after match switching', async () => {
    const api = makeApi()
    const pending = deferred()
    api.loadSnapshot.mockImplementation((id, timestamp) => id === 'a' && timestamp === 10
      ? pending.promise : Promise.resolve(snapshot(timestamp, id)))
    await enterMatch(api)
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Play', exact: true }))
    await act(() => vi.advanceTimersByTimeAsync(1000))
    const oldSignal = api.loadSnapshot.mock.calls.at(-1)[2]
    fireEvent.change(screen.getByLabelText('Select fixture'), { target: { value: 'b' } })
    await act(async () => {})
    expect(oldSignal.aborted).toBe(true)
    expect(screen.getByRole('heading', { name: 'Gamma vs Delta' })).toBeTruthy()
    await act(async () => pending.resolve(snapshot(10)))
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Case room' })).toBeNull()
  })

  it('reports snapshot errors and recovers with Retry', async () => {
    const api = makeApi()
    api.loadSnapshot.mockRejectedValueOnce(new Error('Snapshot unavailable'))
    render(<App api={api} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Enter the match' }))
    await screen.findByRole('heading', { name: 'Snapshot unavailable' })
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Alpha vs Beta' })).toBeTruthy())
    expect(screen.getByText('0 - 0')).toBeTruthy()
  })
})
