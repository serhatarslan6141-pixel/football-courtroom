import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PitchStage from './PitchStage.jsx'
import EventCaption from './EventCaption.jsx'
import { replayVisual } from '../../domain/replayVisual.js'
import { eventGeometry } from '../../domain/broadcast.js'
import { matches } from '../../test/fixtures.js'

const match = matches[0]
const point = { x: 100, y: 0 }
const player = { player_id: 'taker', team_id: 'home', role: 'RW', ...point }
function restart(kind = 'corner', location = point) {
  return {
    event_id: 'setup',
    event_type: 'restart',
    timestamp: 10,
    start_timestamp: 10,
    duration: 0,
    team_id: 'home',
    player_id: 'taker',
    possession_id: 2,
    period: 1,
    metadata: {
      start: { x: 95, y: 44 },
      end: location,
      location: { x: 95, y: 44 },
      movement: 'reset',
      ball_in_play: false,
      restart_type: kind,
      player_name: 'Alex Taker',
      player_role: kind === 'goal_kick' ? 'GK' : 'RW',
      setup_positions: [{ ...player, ...location }],
    },
  }
}
function pause(setup) {
  return {
    ...setup,
    event_id: 'pause',
    event_type: 'stoppage',
    timestamp: 35,
    start_timestamp: 10,
    duration: 25,
    metadata: {
      ...setup.metadata,
      movement: undefined,
      start: setup.metadata.end,
      location: setup.metadata.end,
    },
  }
}

describe('recorded football rules in the broadcast', () => {
  it.each([
    ['corner', { x: 100, y: 0 }, 'Corner'],
    ['throw_in', { x: 40, y: 100 }, 'Throw in'],
    ['goal_kick', { x: 3, y: 50 }, 'Goal kick'],
    ['direct_free_kick', { x: 72, y: 45 }, 'Direct free kick'],
    ['indirect_free_kick', { x: 60, y: 35 }, 'Indirect free kick'],
  ])(
    'shows %s at the recorded restart spot throughout its pause',
    (kind, location, title) => {
      const setup = restart(kind, location)
      const events = [setup, pause(setup)]
      const visual = replayVisual(events, 20)
      render(
        <>
          <PitchStage events={events} timestamp={20} match={match} />
          <EventCaption event={visual.event} timestamp={20} match={match} />
        </>,
      )
      expect(screen.getByRole('status').textContent).toContain(
        `${title} — ${match.home_team}`,
      )
      expect(screen.getByTestId('restart-setup')).toBeTruthy()
      expect(visual.ball.x).toBeCloseTo(location.x * 1.05)
      expect(visual.ball.y).toBeCloseTo(location.y * 0.68)
      expect(screen.getByText(/Alex Taker prepares the restart/)).toBeTruthy()
      expect(screen.queryByTestId('event-path')).toBeNull()
      expect(visual.event.metadata.outcome).toBeUndefined()
      expect(eventGeometry(setup).point).toEqual(visual.ball)
    },
  )

  it('shows the penalty taker and recorded goalkeeper setup without revealing the outcome', () => {
    const setup = restart('penalty', { x: 89.52, y: 50 })
    setup.metadata.setup_positions.push({
      player_id: 'keeper',
      team_id: 'away',
      role: 'GK',
      x: 100,
      y: 50,
    })
    const shot = {
      event_id: 'shot',
      event_type: 'shot',
      timestamp: 36,
      start_timestamp: 35,
      duration: 1,
      team_id: 'home',
      player_id: 'taker',
      possession_id: 2,
      metadata: {
        start: setup.metadata.end,
        end: { x: 100, y: 50 },
        outcome: 'goal',
        description: 'Alex Taker scores!',
        on_target: true,
        restart_type: 'penalty',
        player_name: 'Alex Taker',
        ball_in_play: true,
      },
    }
    const events = [
      setup,
      pause(setup),
      shot,
      { ...shot, event_id: 'goal', event_type: 'goal', timestamp: 36 },
    ]
    const { rerender } = render(
      <PitchStage events={events} timestamp={20} match={match} />,
    )
    expect(screen.getByText('GK · goal line')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Penalty')
    rerender(<PitchStage events={events} timestamp={35.5} match={match} />)
    expect(screen.queryByTestId('restart-setup')).toBeNull()
    expect(screen.queryByText(/scores/)).toBeNull()
    expect(replayVisual(events, 35.5).event.metadata.outcome).toBeUndefined()
    rerender(<PitchStage events={events} timestamp={36} match={match} />)
    expect(document.querySelector('.goal-ring')).toBeTruthy()
  })

  it.each(['yellow', 'red'])(
    'renders the recorded %s card with the player identity',
    (color) => {
      const card = {
        event_id: 'card',
        event_type: 'card',
        timestamp: 9,
        team_id: 'away',
        metadata: { card_type: color, player_name: 'Jamie Defender' },
      }
      render(<PitchStage event={card} match={match} />)
      expect(screen.getByLabelText(`${color} card`)).toBeTruthy()
      expect(screen.getByRole('status').textContent).toContain('Jamie Defender')
      if (color === 'red')
        expect(screen.getByRole('status').textContent).toContain('SENT OFF')
    },
  )

  it('keeps a dismissal visible alongside the awarded restart and clears it on backwards seek', () => {
    const setup = restart('direct_free_kick', { x: 65, y: 50 })
    const card = {
      event_id: 'red',
      event_type: 'card',
      timestamp: 10,
      team_id: 'away',
      metadata: { card_type: 'red', player_name: 'Jamie Defender' },
    }
    const events = [card, setup, pause(setup)]
    const { rerender } = render(
      <PitchStage events={events} timestamp={12} match={match} />,
    )
    expect(screen.getByRole('status').textContent).toContain('sent off')
    expect(screen.getByRole('status').textContent).toContain('Direct free kick')
    rerender(<PitchStage events={events} timestamp={9} match={match} />)
    expect(screen.queryByLabelText('red card')).toBeNull()
    expect(screen.queryByTestId('restart-setup')).toBeNull()
  })

  it('shows offside release context only after the recorded receiver involvement', () => {
    const pass = {
      event_id: 'pass',
      event_type: 'pass',
      timestamp: 10,
      start_timestamp: 8,
      duration: 2,
      team_id: 'home',
      possession_id: 1,
      metadata: {
        start: { x: 75, y: 50 },
        end: { x: 93, y: 45 },
        failure_reason: 'offside',
        outcome: 'incomplete',
        ball_in_play: true,
        offside_context: {
          receiver_position: { x: 91, y: 48 },
          offside_line_x: 88,
        },
      },
    }
    const call = {
      ...pass,
      event_id: 'offside',
      event_type: 'offside',
      start_timestamp: 10,
      duration: 0,
      metadata: {
        ...pass.metadata,
        player_name: 'Alex Runner',
        ball_in_play: false,
      },
    }
    const events = [pass, call]
    const { rerender } = render(
      <PitchStage events={events} timestamp={9} match={match} />,
    )
    expect(screen.queryByTestId('offside-context')).toBeNull()
    expect(
      replayVisual(events, 9).event.metadata.failure_reason,
    ).toBeUndefined()
    expect(
      replayVisual(events, 9).event.metadata.offside_context,
    ).toBeUndefined()
    rerender(<PitchStage events={events} timestamp={10} match={match} />)
    expect(screen.getByTestId('offside-context')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain(
      'Offside · Alex Runner',
    )
    expect(
      screen.getByText('AT PASS RELEASE · SIMULATED POSITIONS'),
    ).toBeTruthy()
  })

  it('reduced motion holds the same recorded restart spot', () => {
    const setup = restart('throw_in', { x: 35, y: 0 })
    const events = [setup, pause(setup)]
    expect(replayVisual(events, 24, true).ball).toEqual(
      replayVisual(events, 24).ball,
    )
  })
})
