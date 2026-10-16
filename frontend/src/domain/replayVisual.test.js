import { describe, expect, it } from 'vitest'
import { replayVisual } from './replayVisual.js'

const kickoff = {
  event_id: 'ko',
  timestamp: 0,
  period: 1,
  event_type: 'kickoff',
  possession_id: 1,
  team_id: 'home',
  metadata: { end: { x: 20, y: 40 } },
}
const pass = {
  event_id: 'p',
  start_timestamp: 2,
  timestamp: 4,
  duration: 2,
  event_type: 'pass',
  team_id: 'home',
  player_id: 'home-8',
  possession_id: 1,
  period: 1,
  metadata: {
    start: { x: 20, y: 40 },
    end: { x: 40, y: 60 },
    outcome: 'complete',
    description: 'Spoiler: pass completed',
    player_name: 'Alex',
    player_role: 'CM',
  },
}
const events = [kickoff, pass]

describe('recorded motion reconstruction', () => {
  it('interpolates the same recorded position on playback or seek', () => {
    const visual = replayVisual(events, 3)
    expect(visual.ball.x).toBeCloseTo(30 * 1.05)
    expect(visual.ball.y).toBeCloseTo(50 * 0.68)
    expect(visual.path.end).toEqual(visual.ball)
    expect(replayVisual(events, 3)).toEqual(visual)
    expect(replayVisual(events, 4).ball.x).toBeCloseTo(40 * 1.05)
  })
  it('hides future results and completed paths until completion', () => {
    const visual = replayVisual(events, 3)
    expect(visual.event.in_progress).toBe(true)
    expect(visual.event.metadata.outcome).toBeUndefined()
    expect(visual.event.metadata.description).toBeUndefined()
    expect(visual.event.metadata.recipient_id).toBeUndefined()
    expect(visual.trail).toHaveLength(0)
    expect(replayVisual(events, 4).event.metadata.outcome).toBe('complete')
    expect(replayVisual(events, 1).event.event_id).toBe('ko')
  })
  it('does not reveal goals before the shot finishes', () => {
    const shot = {
      ...pass,
      event_type: 'shot',
      metadata: { ...pass.metadata, outcome: 'goal' },
    }
    const goal = { ...shot, event_id: 'goal', event_type: 'goal', duration: 0 }
    expect(replayVisual([kickoff, shot, goal], 3).event.event_type).toBe('shot')
    expect(replayVisual([kickoff, shot, goal], 3).cue).toBeNull()
    expect(replayVisual([kickoff, shot, goal], 4).cue.event_type).toBe('goal')
  })
  it('reduced motion holds until recorded completion', () => {
    expect(replayVisual(events, 3, true).ball.x).toBeCloseTo(21)
    expect(replayVisual(events, 3, true).ball.y).toBeCloseTo(27.2)
    expect(replayVisual(events, 4, true).ball.x).toBeCloseTo(42)
  })
  it('shows failed passes and ownership changes, then clears old sequences', () => {
    const failed = {
      ...pass,
      metadata: { ...pass.metadata, outcome: 'incomplete' },
    }
    const change = {
      ...failed,
      event_id: 'change',
      event_type: 'possession_change',
      possession_id: 2,
      team_id: 'away',
      duration: 0,
    }
    const visual = replayVisual([kickoff, failed, change], 4.5)
    expect(visual.event.team_id).toBe('away')
    expect(visual.cue.event_type).toBe('possession_change')
    expect(visual.trail[0].metadata.outcome).toBe('incomplete')
    expect(replayVisual([kickoff, failed, change], 7).trail).toHaveLength(0)
  })
})
