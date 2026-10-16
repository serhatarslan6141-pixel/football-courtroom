import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import {
  eligibleCases,
  eventGeometry,
  timelineMarkers,
} from '../../domain/broadcast.js'
import { caseItem, events, matches, snapshot } from '../../test/fixtures.js'
import PitchStage from './PitchStage.jsx'
import MatchTimeline from './MatchTimeline.jsx'
import MatchSideRail from './MatchSideRail.jsx'

describe('pitch event metadata', () => {
  it('draws a pass using recorded start and end coordinates', () => {
    render(<PitchStage event={events[1]} match={matches[0]} />)
    const path = screen.getByTestId('event-path')
    expect(Number(path.getAttribute('x1'))).toBeCloseTo(24 * 1.05)
    expect(Number(path.getAttribute('y1'))).toBeCloseTo(20 * 0.68)
    expect(Number(path.getAttribute('x2'))).toBeCloseTo(68 * 1.05)
    expect(Number(path.getAttribute('y2'))).toBeCloseTo(60 * 0.68)
  })

  it('shows a point for a shot without a target, and a path only with an explicit target', () => {
    const shot = {
      event_id: 's',
      event_type: 'shot',
      team_id: 'away',
      x: 12,
      y: 35,
      metadata: { on_target: true },
    }
    const { rerender } = render(<PitchStage event={shot} match={matches[0]} />)
    expect(screen.getByTestId('event-point')).toBeTruthy()
    expect(screen.queryByTestId('event-path')).toBeNull()
    expect(eventGeometry(shot).point.x).toBeCloseTo(12.6) // Away is not mirrored a second time.
    rerender(
      <PitchStage
        event={{ ...shot, metadata: { target: { x: 0, y: 40 } } }}
        match={matches[0]}
      />,
    )
    expect(screen.getByTestId('event-path').getAttribute('x2')).toBe('0')
  })

  it('does not invent a missing pass endpoint or map null to the corner', () => {
    expect(eventGeometry({ event_type: 'pass', x: 20, y: 30 }).path).toBeNull()
    expect(
      eventGeometry({ event_type: 'pass', metadata: { end: { x: 60, y: 20 } } })
        .path,
    ).toBeNull()
    for (const value of [null, NaN, -1, 101, undefined]) {
      expect(
        eventGeometry({ event_type: 'foul', x: value, y: 20 }).point,
      ).toBeNull()
    }
    expect(eventGeometry({ event_type: 'foul', x: 0, y: 0 }).point).toEqual({
      x: 0,
      y: 0,
    })
  })

  it('renders pressure regions, foul/tackle points and a restrained goal cue', () => {
    const event = { event_id: 'e', team_id: 'home', x: 30, y: 40 }
    const { rerender, container } = render(
      <PitchStage
        event={{ ...event, event_type: 'pressure_event' }}
        match={matches[0]}
      />,
    )
    expect(screen.getByTestId('pressure-region')).toBeTruthy()
    for (const type of ['foul', 'tackle']) {
      rerender(
        <PitchStage
          event={{ ...event, event_type: type }}
          match={matches[0]}
        />,
      )
      expect(screen.getByTestId('event-point')).toBeTruthy()
      expect(screen.queryByTestId('event-path')).toBeNull()
    }
    rerender(
      <PitchStage
        event={{ ...event, event_type: 'goal' }}
        match={matches[0]}
      />,
    )
    expect(container.querySelector('.goal-ring')).toBeTruthy()
    rerender(
      <PitchStage event={{ event_type: 'substitution' }} match={matches[0]} />,
    )
    expect(screen.queryByTestId('event-point')).toBeNull()
    expect(
      screen.getByText('Location not recorded for this event'),
    ).toBeTruthy()
  })
})

describe('timeline eligibility and details', () => {
  it('hides future event and case markers even if given a complete match array', () => {
    expect(timelineMarkers(events, [caseItem], 5)).toEqual([])
    expect(eligibleCases([caseItem], 9)).toEqual([])
    const markers = timelineMarkers(events, [caseItem], 10)
    expect(markers.map((item) => item.type)).toEqual(['goal', 'case'])
    expect(markers.find((item) => item.type === 'case').timestamp).toBe(10)
    const moreEvents = [
      ...events,
      { event_id: 'sub', event_type: 'substitution', timestamp: 12 },
      { event_id: 'card', event_type: 'card', timestamp: 14 },
    ]
    expect(
      timelineMarkers(moreEvents, [], 13).map((item) => item.type),
    ).toEqual(['goal', 'substitution'])
    expect(
      timelineMarkers(moreEvents, [], 14).map((item) => item.type),
    ).toEqual(['goal', 'substitution', 'card'])
  })

  it('seeks to a marker or a requested range position without exposing future cases', () => {
    const onSeek = vi.fn()
    const { rerender } = render(
      <MatchTimeline
        events={events}
        cases={[caseItem]}
        timestamp={5}
        pendingTimestamp={null}
        duration={20}
        onSeek={onSeek}
      />,
    )
    expect(screen.queryByRole('button', { name: /Courtroom/ })).toBeNull()
    fireEvent.change(screen.getByRole('slider'), { target: { value: '17' } })
    expect(onSeek).toHaveBeenLastCalledWith(17)
    rerender(
      <MatchTimeline
        events={events}
        cases={[caseItem]}
        timestamp={10}
        pendingTimestamp={null}
        duration={20}
        onSeek={onSeek}
      />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Courtroom case available at 00:10' }),
    )
    expect(onSeek).toHaveBeenLastCalledWith(10)
  })

  it('paginates detailed history instead of rendering an unbounded event feed', () => {
    const history = Array.from({ length: 65 }, (_, index) => ({
      ...events[0],
      event_id: `e-${index}`,
      timestamp: index,
      metadata: { description: `Event ${index}` },
    }))
    render(
      <MatchSideRail
        state={snapshot(0).state}
        events={history}
        cases={[]}
        match={matches[0]}
        onSeek={vi.fn()}
        onOpen={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('tab', { name: 'Events' }))
    expect(
      within(screen.getByRole('list')).getAllByRole('listitem'),
    ).toHaveLength(20)
    expect(screen.getByText('Event 64')).toBeTruthy()
    expect(screen.queryByText('Event 0')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Older' }))
    expect(screen.getByText('Event 44')).toBeTruthy()
    expect(screen.queryByText('Event 64')).toBeNull()
  })
})
