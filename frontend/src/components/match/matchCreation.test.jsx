import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from '../../App.jsx'
import FixturePicker from './FixturePicker.jsx'
import {
  matches,
  events,
  snapshot,
  deferred,
  caseItem,
} from '../../test/fixtures.js'

function makeApi() {
  const library = [...matches]
  let next = 1
  const publish = () => {
    const item = {
      match_id: `generated-${next}`,
      seed: 10000 + next,
      generation_mode: 'varied-v1',
      home_team: next === 1 ? 'Alpha' : 'Gamma',
      away_team: 'Zeta',
    }
    next += 1
    library.push(item)
    return item
  }
  return {
    library,
    publish,
    listMatches: vi.fn(async () => ({ matches: [...library] })),
    loadMatch: vi.fn(async (id) => ({
      matchData: library.find((match) => match.match_id === id),
      events,
    })),
    loadSnapshot: vi.fn(async (id, time) => ({
      ...snapshot(time, id),
      cases:
        id.startsWith('generated-') && time >= 10
          ? [{ ...caseItem, case_id: `${id}-case`, match_id: id }]
          : [],
    })),
    createMatch: vi.fn(async () => publish()),
  }
}
async function lobby(api) {
  const view = render(<App api={api} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Enter the match' }))
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Create a new match' }).disabled,
    ).toBe(false),
  )
  return { ...view, user }
}
const ready = () =>
  waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Enter replay', exact: true })
        .disabled,
    ).toBe(false),
  )

describe('new match creation in the fixture lobby', () => {
  it('creates once, selects the generated fixture and plays it through the existing replay and courtroom', async () => {
    const api = makeApi()
    const pending = deferred()
    api.createMatch.mockImplementation(() => pending.promise)
    const { user } = await lobby(api)
    fireEvent.click(screen.getByRole('button', { name: 'Create a new match' }))
    fireEvent.click(screen.getByRole('button', { name: 'Creating match…' }))
    expect(api.createMatch).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status').textContent).toContain(
      'Preparing a new 90 minutes',
    )
    await act(async () => pending.resolve(api.publish()))
    await ready()
    const tile = screen.getByRole('button', {
      name: 'Select Alpha vs Zeta · Match 4',
    })
    expect(tile.getAttribute('aria-pressed')).toBe('true')
    await user.click(
      screen.getByRole('button', { name: 'Enter replay', exact: true }),
    )
    expect(screen.getByRole('heading', { name: 'Alpha vs Zeta' })).toBeTruthy()
    fireEvent.change(screen.getByRole('slider'), { target: { value: '10' } })
    await waitFor(() =>
      expect(screen.getByLabelText('Match clock').textContent).toBe('00:10'),
    )
    await user.click(screen.getByRole('tab', { name: /Cases/ }))
    await user.click(screen.getByRole('button', { name: /Open case/ }))
    expect(screen.getByRole('button', { name: 'Begin trial' })).toBeTruthy()
    await user.click(
      screen.getByRole('button', { name: 'Return to match', exact: true }),
    )
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:10')
    expect(
      screen.getByRole('button', { name: 'Play', exact: true }),
    ).toBeTruthy()
  })

  it('creates multiple fixtures and revisits the same server-session match after remount', async () => {
    const api = makeApi()
    const first = await lobby(api)
    await first.user.click(
      screen.getByRole('button', { name: 'Create a new match' }),
    )
    await ready()
    await first.user.click(
      screen.getByRole('button', { name: 'Create a new match' }),
    )
    await ready()
    expect(api.createMatch).toHaveBeenCalledTimes(2)
    expect(screen.getByText('5 simulated matches')).toBeTruthy()
    first.unmount()
    const second = await lobby(api)
    await second.user.click(
      screen.getByRole('button', { name: 'Next fixtures' }),
    )
    await second.user.click(
      screen.getByRole('button', { name: 'Select Alpha vs Zeta · Match 4' }),
    )
    await ready()
    await second.user.click(
      screen.getByRole('button', { name: 'Enter replay', exact: true }),
    )
    expect(screen.getByRole('heading', { name: 'Alpha vs Zeta' })).toBeTruthy()
    expect(api.loadMatch).toHaveBeenLastCalledWith(
      'generated-1',
      expect.any(AbortSignal),
    )
    expect(api.createMatch).toHaveBeenCalledTimes(2)
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:00')
  })

  it('keeps an existing fixture usable if creation fails', async () => {
    const api = makeApi()
    api.createMatch.mockRejectedValueOnce(new Error('Backend unavailable'))
    const { user } = await lobby(api)
    await user.click(screen.getByRole('button', { name: 'Create a new match' }))
    expect((await screen.findByRole('alert')).textContent).toContain(
      'Backend unavailable',
    )
    await ready()
    await user.click(
      screen.getByRole('button', { name: 'Enter replay', exact: true }),
    )
    expect(screen.getByRole('heading', { name: 'Alpha vs Beta' })).toBeTruthy()
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:00')
  })

  it('does not steal the selection or reset playback if the user enters another fixture during creation', async () => {
    const api = makeApi()
    const pending = deferred()
    api.createMatch.mockImplementation(() => pending.promise)
    const { user } = await lobby(api)
    await user.click(screen.getByRole('button', { name: 'Create a new match' }))
    await user.click(
      screen.getByRole('button', { name: 'Select Gamma vs Delta' }),
    )
    await ready()
    await user.click(
      screen.getByRole('button', { name: 'Enter replay', exact: true }),
    )
    fireEvent.change(screen.getByRole('slider'), { target: { value: '5' } })
    await waitFor(() =>
      expect(screen.getByLabelText('Match clock').textContent).toBe('00:05'),
    )
    await act(async () => pending.resolve(api.publish()))
    expect(screen.getByRole('heading', { name: 'Gamma vs Delta' })).toBeTruthy()
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:05')
    expect(
      screen.getByRole('button', { name: 'Play', exact: true }),
    ).toBeTruthy()
  })

  it('bounds a 100-match catalog to three visible tiles without a dropdown', async () => {
    const fixtures = Array.from({ length: 100 }, (_, index) => ({
      match_id: String(index),
      home_team: `Club ${index}`,
      away_team: 'Rivals',
      generation_mode: 'varied-v1',
    }))
    const user = userEvent.setup()
    render(
      <FixturePicker
        matches={fixtures}
        selectedId="99"
        loading={false}
        onSelect={() => {}}
        onCreate={() => {}}
      />,
    )
    expect(screen.getByText('100 simulated matches')).toBeTruthy()
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(
      screen.getByRole('button', {
        name: 'Select Club 99 vs Rivals · Match 100',
      }),
    ).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Previous fixtures' }))
    expect(
      screen.getAllByRole('button', { name: /^Select Club/ }),
    ).toHaveLength(3)
  })
})
