export const matches = [
  { match_id: 'a', home_team: 'Alpha', away_team: 'Beta' },
  { match_id: 'b', home_team: 'Gamma', away_team: 'Delta' },
  { match_id: 'c', home_team: 'Epsilon', away_team: 'Zeta' },
]

export const events = [
  { event_id: 'kickoff', timestamp: 0, index: 0, minute: '00:00', team_id: 'home', event_type: 'kickoff', x: 50, y: 50 },
  { event_id: 'pass', timestamp: 10, index: 8, minute: '00:10', team_id: 'home', event_type: 'pass', metadata: { description: 'First pass', start: { x: 24, y: 20 }, end: { x: 68, y: 60 } } },
  { event_id: 'goal', timestamp: 10, index: 9, minute: '00:10', team_id: 'home', event_type: 'goal', x: 88, y: 50, metadata: { description: 'Equal timestamp goal', player_name: 'Alex Fiction' } },
  { event_id: 'later', timestamp: 20, index: 2, minute: '00:20', team_id: 'away', event_type: 'pressure_event' },
]

export const caseItem = {
  case_id: 'case-a', title: 'Did Home gain momentum?', case_type: 'momentum_shift',
  detection_timestamp: 0, available_timestamp: 10, teams: { team_id: 'home' },
  evidence: [{ label: 'Attack', value: 'Attacking evidence', event_ids: ['goal'] }],
  counterevidence: ['Small sample'], limitations: ['Synthetic evidence'],
  relevant_windows: [{ label: 'After', start: 0, end: 10 }], confidence: 'low',
}

export function snapshot(timestamp, id = 'a') {
  return {
    timestamp,
    state: {
      score: { home: timestamp >= 10 ? 1 : 0, away: 0 }, match_clock_seconds: timestamp,
      possession: { home: 50, away: 50 }, pass_completion: { home: null, away: 0 },
      shots: { home: 0, away: 0 }, pressure_events: { home: 0, away: 0 },
    },
    cases: id === 'a' && timestamp >= 10 ? [caseItem] : [],
  }
}

export function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}
