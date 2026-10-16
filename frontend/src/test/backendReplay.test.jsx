import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PitchStage from '../components/match/PitchStage.jsx'
import MatchTimeline from '../components/match/MatchTimeline.jsx'
import { replayVisual } from '../domain/replayVisual.js'
import {
  initialSession,
  sessionReducer,
  visibleEvents,
} from '../session/sessionReducer.js'

const root = `${resolve(process.cwd(), '..')}/`
const venv = `${root}.venv/bin/python`
const fixture = JSON.parse(
  execFileSync(
    existsSync(venv) ? venv : 'python3',
    [`${root}backend/tests/export_replay.py`],
    {
      env: { ...process.env, PYTHONPATH: `${root}backend` },
      maxBuffer: 32 * 1024 * 1024,
    },
  ).toString(),
)

describe('backend generator → API → pitch integration', () => {
  it('renders actual pass interpolation, active players and shot geometry', () => {
    const event = fixture.events.find(
      (item) => item.event_type === 'pass' && item.duration >= 2,
    )
    const timestamp = event.start_timestamp + event.duration / 2
    const { rerender } = render(
      <PitchStage
        events={fixture.events}
        timestamp={timestamp}
        match={fixture.match}
      />,
    )
    const visual = replayVisual(fixture.events, timestamp)
    expect(visual.ball.x).toBeCloseTo(
      ((event.metadata.start.x + event.metadata.end.x) / 2) * 1.05,
    )
    expect(visual.ball.y).toBeCloseTo(
      ((event.metadata.start.y + event.metadata.end.y) / 2) * 0.68,
    )
    expect(
      screen.getByTestId('event-point').getAttribute('data-in-progress'),
    ).toBe('true')
    expect(
      screen.getByText(
        `${event.metadata.player_name} · ${event.metadata.player_role}`,
      ),
    ).toBeTruthy()
    const shot = fixture.events.find((item) => item.event_type === 'shot')
    rerender(
      <PitchStage
        events={fixture.events}
        timestamp={shot.start_timestamp + 0.5}
        match={fixture.match}
      />,
    )
    expect(screen.getByTestId('event-path')).toBeTruthy()
    expect(
      replayVisual(fixture.events, shot.start_timestamp + 0.5).event.metadata
        .outcome,
    ).toBeUndefined()
  })
  it('reconstructs halftime sides and possession changes on seek', () => {
    const { rerender } = render(
      <PitchStage
        events={fixture.events}
        timestamp={2700}
        match={fixture.match}
      />,
    )
    expect(
      screen.getByText(`← ${fixture.match.teams[0].short_name} ATTACK`),
    ).toBeTruthy()
    const change = fixture.events.find(
      (item) => item.event_type === 'possession_change',
    )
    rerender(
      <PitchStage
        events={fixture.events}
        timestamp={change.timestamp}
        match={fixture.match}
      />,
    )
    expect(screen.getByTestId('possession-cue')).toBeTruthy()
    expect(
      replayVisual(fixture.events, change.timestamp).event.possession_team_id,
    ).toBe(change.metadata.new_team)
  })
  it('commits actual API snapshots at validity boundaries', () => {
    let session = {
      ...initialSession,
      screen: 'match',
      selectedMatchId: fixture.match.match_id,
      events: fixture.events,
      dataStatus: 'ready',
      isPlaying: true,
      pendingTimestamp: 0,
    }
    session = sessionReducer(session, {
      type: 'SNAPSHOT_LOADED',
      matchVersion: 0,
      replayVersion: 0,
      snapshot: fixture.snapshots['0'],
      now: 0,
    })
    const boundary = session.snapshot.state.next_update_timestamp
    expect(boundary).toBeGreaterThan(0)
    for (let i = 0; i < boundary * 4 + 1; i++)
      session = sessionReducer(session, {
        type: 'ADVANCE_CLOCK',
        elapsed: 0.25,
      })
    expect(session.pendingTimestamp).toBe(boundary)
    expect(
      visibleEvents(session).every((event) => event.timestamp < boundary),
    ).toBe(true)
    session = sessionReducer(session, {
      type: 'SNAPSHOT_LOADED',
      matchVersion: 0,
      replayVersion: session.replayVersion,
      snapshot: fixture.snapshots[String(boundary)],
      now: 0,
    })
    expect(
      visibleEvents(session).every((event) => event.timestamp <= boundary),
    ).toBe(true)
    expect(session.replayTimestamp).toBe(boundary)
  })
  it('does not expose real cases before complete evidence windows', () => {
    const first = [...fixture.cases].sort(
      (a, b) => a.available_timestamp - b.available_timestamp,
    )[0]
    const { rerender } = render(
      <MatchTimeline
        events={fixture.events}
        cases={fixture.cases}
        timestamp={first.available_timestamp - 1}
        pendingTimestamp={null}
        duration={5400}
        onSeek={() => {}}
      />,
    )
    expect(
      screen.queryByRole('button', { name: /Courtroom case available/ }),
    ).toBeNull()
    rerender(
      <MatchTimeline
        events={fixture.events}
        cases={fixture.cases}
        timestamp={first.available_timestamp}
        pendingTimestamp={null}
        duration={5400}
        onSeek={() => {}}
      />,
    )
    expect(
      screen.getAllByRole('button', { name: /Courtroom case available/ })
        .length,
    ).toBeGreaterThan(0)
  })
})
