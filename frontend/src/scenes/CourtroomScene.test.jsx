import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.jsx'
import { caseItem, events, matches, snapshot } from '../test/fixtures.js'

const trialCase = {
  ...caseItem,
  evidence: [
    ...caseItem.evidence,
    {
      label: 'Pass',
      value: 'A completed passage of play',
      event_ids: ['pass'],
    },
  ],
  counterevidence: [
    'Small sample',
    'A short spell does not prove a lasting change',
  ],
  confidence: 'high',
}
function makeApi() {
  return {
    listMatches: vi.fn(async () => ({ matches })),
    loadMatch: vi.fn(async (id) => ({
      matchData: matches.find((match) => match.match_id === id),
      events,
    })),
    loadSnapshot: vi.fn(async (id, time) => ({
      ...snapshot(time, id),
      cases: id === 'a' && time >= 10 ? [trialCase] : [],
    })),
  }
}
async function openTrial(api = makeApi()) {
  render(<App api={api} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Enter the match' }))
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Enter replay', exact: true })
        .disabled,
    ).toBe(false),
  )
  await user.click(
    screen.getByRole('button', { name: 'Enter replay', exact: true }),
  )
  fireEvent.change(screen.getByRole('slider', { name: 'Seek match replay' }), {
    target: { value: '10' },
  })
  await waitFor(() =>
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:10'),
  )
  await user.click(screen.getByRole('tab', { name: /Cases/ }))
  await user.click(screen.getByRole('button', { name: /Open case/ }))
  return { user, api }
}
async function reachVote(user) {
  await user.click(screen.getByRole('button', { name: 'Begin trial' }))
  await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
  await user.click(screen.getByRole('button', { name: 'Make your call' }))
}

afterEach(() => vi.useRealTimers())

describe('interactive football trial', () => {
  it('opens with the case question, incident score and a sealed ruling', async () => {
    await openTrial()
    expect(
      screen.getByRole('heading', { name: 'Did Alpha gain momentum?' }),
    ).toBeTruthy()
    expect(screen.getByLabelText('Score at the incident').textContent).toBe(
      '0 – 0',
    )
    expect(screen.getByRole('button', { name: /The ruling/ }).disabled).toBe(
      true,
    )
    expect(screen.queryByText('INCONCLUSIVE')).toBeNull()
    expect(screen.queryByText('Attacking evidence')).toBeNull()
    expect(
      screen.queryByRole('slider', { name: 'Seek evidence replay' }),
    ).toBeNull()
    expect(document.body.textContent).not.toContain('case-a')
  })

  it('plays, pauses and seeks evidence without changing the main replay or requesting new snapshots', async () => {
    const { user, api } = await openTrial()
    await user.click(screen.getByRole('button', { name: 'Begin trial' }))
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    const slider = screen.getByRole('slider', { name: 'Seek evidence replay' })
    expect(Number(slider.max)).toBe(10)
    const requests = api.loadSnapshot.mock.calls.length
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: 'Play evidence' }))
    await act(() => vi.advanceTimersByTimeAsync(1200))
    expect(Number(slider.value)).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: 'Pause evidence' }))
    const paused = slider.value
    await act(() => vi.advanceTimersByTimeAsync(1200))
    expect(slider.value).toBe(paused)
    fireEvent.change(slider, { target: { value: '10' } })
    expect(screen.getByText('Equal timestamp goal')).toBeTruthy()
    fireEvent.click(
      screen.getByRole('button', { name: 'Restart evidence clip' }),
    )
    expect(screen.queryByText('Equal timestamp goal')).toBeNull()
    expect(api.loadSnapshot).toHaveBeenCalledTimes(requests)
    fireEvent.click(
      screen.getByRole('button', { name: 'Return to match', exact: true }),
    )
    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(screen.getByLabelText('Match clock').textContent).toBe('00:10')
    expect(
      screen.getByRole('button', { name: 'Play', exact: true }),
    ).toBeTruthy()
  })

  it('gives each side the floor one submission at a time and permits evidence review', async () => {
    const { user } = await openTrial()
    await user.click(screen.getByRole('button', { name: 'Begin trial' }))
    await user.click(screen.getByRole('button', { name: 'Hear the arguments' }))
    expect(
      screen.getByRole('heading', { name: 'Attacking evidence' }),
    ).toBeTruthy()
    expect(screen.queryByText('A completed passage of play')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Next submission' }))
    expect(
      screen.getByRole('heading', { name: 'A completed passage of play' }),
    ).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Hear the defense' }))
    expect(screen.getByRole('heading', { name: 'Small sample' })).toBeTruthy()
    expect(screen.queryByText('Attacking evidence')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Next submission' }))
    expect(
      screen.getByRole('heading', {
        name: 'A short spell does not prove a lasting change',
      }),
    ).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Inspect the moment/ }))
    expect(
      screen.getByRole('slider', { name: 'Seek evidence replay' }),
    ).toBeTruthy()
  })

  it.each([
    'Agree with the prosecution',
    'Agree with the defense',
    'Not enough evidence',
  ])(
    'records "%s" before revealing an independent assessment',
    async (label) => {
      const { user } = await openTrial()
      await reachVote(user)
      const submit = screen.getByRole('button', {
        name: 'Record my vote & hear the ruling',
      })
      expect(submit.disabled).toBe(true)
      expect(screen.queryByText('INCONCLUSIVE')).toBeNull()
      await user.click(screen.getByRole('button', { name: label, exact: true }))
      expect(screen.queryByText('INCONCLUSIVE')).toBeNull()
      await user.click(submit)
      expect(screen.getByText('INCONCLUSIVE')).toBeTruthy()
      expect(
        screen.getByText('No AI judge has evaluated this case.', {
          exact: false,
        }),
      ).toBeTruthy()
      expect(
        screen.getByText('YOUR OPINION').parentElement.textContent,
      ).toContain(label)
      expect(screen.getByText('WHAT THE RECORD SUPPORTS')).toBeTruthy()
      await user.click(screen.getByText('Why the court leaves it open'))
      expect(screen.getByText('Synthetic evidence')).toBeTruthy()
      await user.click(
        screen.getByRole('button', { name: 'Return to match', exact: true }),
      )
      expect(screen.getByLabelText('Match clock').textContent).toBe('00:10')
    },
  )

  it('remembers the vote when reopening the same case without unlocking a new ruling early', async () => {
    const { user } = await openTrial()
    await reachVote(user)
    await user.click(
      screen.getByRole('button', { name: 'Not enough evidence', exact: true }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Record my vote & hear the ruling' }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Return to match', exact: true }),
    )
    await user.click(screen.getByRole('tab', { name: /Cases/ }))
    await user.click(screen.getByRole('button', { name: /Open case/ }))
    expect(screen.queryByText('INCONCLUSIVE')).toBeNull()
    await reachVote(user)
    expect(
      screen
        .getByRole('button', { name: 'Not enough evidence', exact: true })
        .getAttribute('aria-pressed'),
    ).toBe('true')
  })

  it('supports keyboard voting and back navigation through completed stages', async () => {
    const { user } = await openTrial()
    await reachVote(user)
    const choice = screen.getByRole('button', {
      name: 'Agree with the defense',
      exact: true,
    })
    choice.focus()
    await user.keyboard('{Enter}')
    expect(choice.getAttribute('aria-pressed')).toBe('true')
    const progress = screen.getByRole('navigation', { name: 'Trial progress' })
    await user.click(within(progress).getByRole('button', { name: /Evidence/ }))
    expect(
      screen.getByRole('slider', { name: 'Seek evidence replay' }),
    ).toBeTruthy()
    expect(
      within(progress).getByRole('button', { name: /The ruling/ }).disabled,
    ).toBe(true)
  })
})
