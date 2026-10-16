import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
  await screen.findByRole('button', { name: 'Enter replay', exact: true })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enter replay', exact: true }).disabled).toBe(false))
  await user.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
  await screen.findByRole('heading', { name: 'Alpha vs Beta' })
  return user
}

async function chooseFixture(name) {
  fireEvent.click(screen.getByRole('button', { name: /Change fixture/ }))
  fireEvent.click(screen.getByRole('button', { name: `Select ${name}` }))
  await act(async () => {})
  fireEvent.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
  await act(async () => {})
}

afterEach(() => vi.useRealTimers())

describe('broadcast scenes and synchronized replay', () => {
  it('offers all fixtures as selected tiles before entering replay', async () => {
    render(<App api={makeApi()} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Enter the match' }))
    expect(screen.queryByRole('combobox')).toBeNull()
    await screen.findByRole('button', { name: 'Select Epsilon vs Zeta' })
    expect(screen.queryByRole('img', { name: /Football pitch/ })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Select Gamma vs Delta' }))
    expect(screen.getByRole('button', { name: 'Select Gamma vs Delta' }).getAttribute('aria-pressed')).toBe('true')
    await user.click(await screen.findByRole('button', { name: 'Enter replay', exact: true }))
    expect(screen.getByRole('heading', { name: 'Gamma vs Delta' })).toBeTruthy()
  })

  it('commits pitch, score, events and case markers together, then pauses in court', async () => {
    const api = makeApi()
    const pending = deferred()
    api.loadSnapshot.mockImplementation((id, timestamp) => timestamp === 10 ? pending.promise : Promise.resolve(snapshot(timestamp, id)))
    await enterMatch(api)
    const accuracy = screen.getByText('Pass accuracy').parentElement
    expect(accuracy.textContent).toContain('N/A')
    expect(accuracy.textContent).toContain('0.0%')
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Play', exact: true }))
    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(api.loadSnapshot).toHaveBeenLastCalledWith('a', 10, expect.any(AbortSignal))
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    expect(screen.queryByRole('button', { name: /Courtroom case available at/ })).toBeNull()
    await act(async () => pending.resolve(snapshot(10)))
    expect(screen.getByText('1 - 0')).toBeTruthy()
    expect(screen.getByText('Equal timestamp goal')).toBeTruthy()
    expect(screen.getByText(/Alex Fiction/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Courtroom case available at 00:10' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /NEW CASE/ }))
    expect(screen.getByText('Prosecution case')).toBeTruthy()
    const calls = api.loadSnapshot.mock.calls.length
    await act(() => vi.advanceTimersByTimeAsync(10000))
    expect(api.loadSnapshot).toHaveBeenCalledTimes(calls)
    fireEvent.click(screen.getByRole('button', { name: 'Return to match' }))
    expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeTruthy()
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:10')
    fireEvent.click(screen.getByRole('tab', { name: 'Events' }))
    expect(screen.getByText('First pass')).toBeTruthy()
  })

  it('preserves details, speed, restart and fixture selection', async () => {
    const api = makeApi()
    const user = await enterMatch(api)
    await user.click(screen.getByRole('tab', { name: 'Events' }))
    expect(screen.queryByText('Pass accuracy')).toBeNull()
    await user.click(screen.getByRole('tab', { name: 'Stats' }))
    expect(screen.getByText('Pass accuracy')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: '2x' }))
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Play', exact: true }))
    await act(() => vi.advanceTimersByTimeAsync(500))
    expect(screen.getByText('1 - 0')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Restart', exact: true }))
    await act(async () => {})
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Courtroom case available at/ })).toBeNull()
    await chooseFixture('Gamma vs Delta')
    expect(screen.getByRole('heading', { name: 'Gamma vs Delta' })).toBeTruthy()
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeTruthy()
    vi.useRealTimers()
    await user.click(screen.getByRole('button', { name: /Exit to welcome/ }))
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
    await chooseFixture('Gamma vs Delta')
    expect(oldSignal.aborted).toBe(true)
    expect(screen.getByRole('heading', { name: 'Gamma vs Delta' })).toBeTruthy()
    await act(async () => pending.resolve(snapshot(10)))
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    expect(screen.queryByRole('button', { name: /Courtroom case available at/ })).toBeNull()
  })

  it('seeks arbitrary timestamps, rewinds without future markers, and skips events', async () => {
    const api = makeApi()
    await enterMatch(api)
    const slider = screen.getByRole('slider', { name: 'Seek match replay' })
    fireEvent.change(slider, { target: { value: '15' } })
    await act(async () => {})
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:15')
    expect(screen.getByRole('button', { name: 'Courtroom case available at 00:10' })).toBeTruthy()
    fireEvent.change(slider, { target: { value: '5' } })
    await act(async () => {})
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:05')
    expect(screen.getByText('0 - 0')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Goal at 00:10' })).toBeNull()
    expect(screen.queryByRole('button', { name: /Courtroom case available at/ })).toBeNull()
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Next event' }))
    await act(async () => {})
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:10')
    fireEvent.click(screen.getByRole('button', { name: 'Previous event' }))
    await act(async () => {})
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:00')
  })

  it('rejects stale responses during rapid dragging and speed changes', async () => {
    const api = makeApi()
    const first = deferred()
    const second = deferred()
    api.loadSnapshot.mockImplementation((id, timestamp) => timestamp === 5 ? first.promise : timestamp === 15 ? second.promise : Promise.resolve(snapshot(timestamp, id)))
    await enterMatch(api)
    const slider = screen.getByRole('slider')
    fireEvent.change(slider, { target: { value: '5' } })
    await act(async () => {})
    const abortedSignal = api.loadSnapshot.mock.calls.at(-1)[2]
    fireEvent.change(slider, { target: { value: '15' } })
    fireEvent.click(screen.getByRole('button', { name: '2x' }))
    await act(async () => {})
    expect(abortedSignal.aborted).toBe(true)
    await act(async () => second.resolve(snapshot(15)))
    await act(async () => first.resolve(snapshot(5)))
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:15')
    expect(screen.getByText('1 - 0')).toBeTruthy()
    expect(screen.getByRole('button', { name: '2x' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('reports snapshot errors and recovers with Retry', async () => {
    const api = makeApi()
    api.loadSnapshot.mockRejectedValueOnce(new Error('Snapshot unavailable'))
    render(<App api={api} />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Enter the match' }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Snapshot unavailable')
    await user.click(within(alert).getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Enter replay', exact: true }).disabled).toBe(false))
    await user.click(screen.getByRole('button', { name: 'Enter replay', exact: true }))
    expect(screen.getByRole('heading', { name: 'Alpha vs Beta' })).toBeTruthy()
  })
})
