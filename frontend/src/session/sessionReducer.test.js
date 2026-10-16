import { describe, expect, it } from 'vitest'
import { initialSession, sessionReducer, visibleEvents } from './sessionReducer.js'
import { caseItem, events, matches, snapshot } from '../test/fixtures.js'

const reduce = sessionReducer

function ready(timestamp = 0) {
  let session = reduce(initialSession, { type: 'SELECT_MATCH', id: 'a' })
  session = reduce(session, { type: 'MATCH_LOADED', matchVersion: session.matchVersion, matchData: matches[0], events })
  session = { ...session, pendingTimestamp: timestamp }
  return reduce(session, {
    type: 'SNAPSHOT_LOADED', matchVersion: session.matchVersion, replayVersion: session.replayVersion,
    snapshot: snapshot(timestamp), now: 1000,
  })
}

describe('match session', () => {
  it('commits events, statistics and cases together, including equal timestamps', () => {
    let session = ready()
    session = reduce(session, { type: 'NAVIGATE', screen: 'match' })
    session = reduce(session, { type: 'TOGGLE_PLAY' })
    session = reduce(session, { type: 'TICK' })
    expect(session.pendingTimestamp).toBe(10)
    expect(session.replayTimestamp).toBe(0)
    expect(visibleEvents(session).map((item) => item.event_id)).toEqual(['kickoff'])
    expect(session.snapshot.state.score.home).toBe(0)
    expect(session.snapshot.cases).toEqual([])
    session = reduce(session, {
      type: 'SNAPSHOT_LOADED', matchVersion: session.matchVersion, replayVersion: session.replayVersion,
      snapshot: snapshot(10), now: 1000,
    })
    expect(visibleEvents(session).map((item) => item.event_id)).toEqual(['kickoff', 'pass', 'goal'])
    expect(session.snapshot.state.score.home).toBe(1)
    expect(session.snapshot.cases).toEqual([caseItem])
    expect(reduce(session, { type: 'TICK' }).pendingTimestamp).toBe(20)
  })

  it('pauses in court, isolates evidence review, and returns at the same position', () => {
    let session = { ...ready(10), screen: 'match', isPlaying: true }
    session = reduce(session, { type: 'TICK' })
    const obsoleteVersion = session.replayVersion
    session = reduce(session, { type: 'OPEN_COURTROOM', caseId: caseItem.case_id })
    expect(session.screen).toBe('courtroom')
    expect(session.isPlaying).toBe(false)
    expect(session.pendingTimestamp).toBeNull()
    expect(session.courtroomReturnPosition).toBe(10)
    expect(reduce(session, { type: 'TICK' })).toBe(session)
    const reviewed = reduce(session, { type: 'REVIEW_EVIDENCE', timestamp: 3 })
    expect(reviewed.evidenceTimestamp).toBe(3)
    expect(reviewed.replayTimestamp).toBe(10)
    expect(reviewed.snapshot).toBe(session.snapshot)
    expect(reduce(reviewed, { type: 'REVIEW_EVIDENCE', timestamp: 999 }).evidenceTimestamp).toBe(10)
    const returned = reduce(reviewed, { type: 'NAVIGATE', screen: 'match' })
    expect(returned.replayTimestamp).toBe(10)
    expect(returned.isPlaying).toBe(false)
    expect(reduce(returned, {
      type: 'SNAPSHOT_LOADED', matchVersion: returned.matchVersion, replayVersion: obsoleteVersion,
      snapshot: snapshot(20), now: 1000,
    })).toBe(returned)
  })

  it('rejects unavailable cases and pauses when navigating to welcome', () => {
    const session = ready()
    expect(reduce(session, { type: 'OPEN_COURTROOM', caseId: caseItem.case_id })).toBe(session)
    const welcome = reduce({ ...session, screen: 'match', isPlaying: true }, { type: 'NAVIGATE', screen: 'welcome' })
    expect(welcome.screen).toBe('welcome')
    expect(welcome.isPlaying).toBe(false)
  })

  it('clears match-specific state and rejects stale responses after A → B → A', () => {
    let session = ready(10)
    const oldMatchVersion = session.matchVersion
    session = reduce(session, { type: 'SELECT_MATCH', id: 'b' })
    expect(session.snapshot).toBeNull()
    expect(session.events).toEqual([])
    expect(session.selectedCaseId).toBe('')
    expect(session.caseNotifications).toEqual([])
    expect(session.replayTimestamp).toBe(0)
    session = reduce(session, { type: 'SELECT_MATCH', id: 'a' })
    expect(reduce(session, { type: 'MATCH_LOADED', matchVersion: oldMatchVersion, matchData: matches[0], events })).toBe(session)
    expect(reduce(session, { type: 'SNAPSHOT_FAILED', matchVersion: oldMatchVersion, replayVersion: session.replayVersion, error: 'Old failure' })).toBe(session)
  })

  it('reset invalidates pending responses and clears cases once timestamp zero commits', () => {
    let session = { ...ready(10), screen: 'match' }
    const oldVersion = session.replayVersion
    session = reduce(session, { type: 'RESET' })
    expect(session.isPlaying).toBe(false)
    expect(session.caseNotifications).toEqual([])
    expect(reduce(session, {
      type: 'SNAPSHOT_LOADED', matchVersion: session.matchVersion, replayVersion: oldVersion,
      snapshot: snapshot(10), now: 1000,
    })).toBe(session)
    session = reduce(session, {
      type: 'SNAPSHOT_LOADED', matchVersion: session.matchVersion, replayVersion: session.replayVersion,
      snapshot: snapshot(0), now: 1000,
    })
    expect(session.replayTimestamp).toBe(0)
    expect(session.snapshot.cases).toEqual([])
  })

  it('stops at the end and replays from zero on Play', () => {
    let session = { ...ready(10), screen: 'match', isPlaying: true }
    session = reduce(session, { type: 'TICK' })
    session = reduce(session, {
      type: 'SNAPSHOT_LOADED', matchVersion: session.matchVersion, replayVersion: session.replayVersion,
      snapshot: snapshot(20), now: 1000,
    })
    expect(session.isPlaying).toBe(false)
    const restarted = reduce(session, { type: 'TOGGLE_PLAY' })
    expect(restarted.pendingTimestamp).toBe(0)
    expect(restarted.isPlaying).toBe(true)
  })

  it('expires notifications independently of subsequent snapshots', () => {
    let session = ready(10)
    expect(session.caseNotifications).toHaveLength(1)
    session = reduce(session, { type: 'EXPIRE_NOTIFICATIONS', now: 6000 })
    expect(session.caseNotifications).toEqual([])
    expect(session.seenCaseIds).toContain(caseItem.case_id)
  })
})
