import { eventGeometry, pitchPoint } from './broadcast.js'

const MOTION_TYPES = new Set([
  'pass',
  'cross',
  'carry',
  'dribble',
  'shot',
  'clearance',
  'miscontrol',
])
const CUE_TYPES = new Set([
  'pressure_event',
  'tackle',
  'interception',
  'recovery',
  'possession_change',
  'foul',
  'save',
  'goal',
])

function inProgressEvent(source) {
  // Whitelist facts about an action underway: its future result is not yet visible.
  const {
    start,
    end,
    location,
    player_name,
    player_role,
    squad_number,
    attack_direction,
    phase,
    ball_in_play,
  } = source.metadata || {}
  return {
    event_id: source.event_id,
    event_type: source.event_type,
    player_id: source.player_id,
    team_id: source.team_id,
    period: source.period,
    possession_id: source.possession_id,
    possession_team_id: source.possession_team_id,
    timestamp: source.start_timestamp,
    in_progress: true,
    metadata: {
      start,
      end,
      location,
      player_name,
      player_role,
      squad_number,
      attack_direction,
      phase,
      ball_in_play,
    },
  }
}

export function replayVisual(events, timestamp, reducedMotion = false) {
  let low = 0,
    high = events.length
  while (low < high) {
    const middle = (low + high) >>> 1
    if (events[middle].timestamp <= timestamp) low = middle + 1
    else high = middle
  }
  const completed = events[low - 1] || null
  const next = events[low]
  const moving =
    next &&
    next.start_timestamp <= timestamp &&
    next.duration > 0 &&
    next.metadata?.movement !== 'reset'
  const event = moving ? inProgressEvent(next) : completed
  const geometry = eventGeometry(event)
  let ball = completed
    ? pitchPoint(completed.metadata?.end) || eventGeometry(completed).point
    : null
  let partialPath = null
  if (moving) {
    const start = pitchPoint(next.metadata?.start)
    const end = pitchPoint(next.metadata?.end)
    if (start && end) {
      const progress = reducedMotion
        ? 0
        : Math.max(
            0,
            Math.min(1, (timestamp - next.start_timestamp) / next.duration),
          )
      ball = {
        x: start.x + (end.x - start.x) * progress,
        y: start.y + (end.y - start.y) * progress,
      }
      if (MOTION_TYPES.has(next.event_type)) partialPath = { start, end: ball }
    }
  }
  const recent = events.slice(Math.max(0, low - 35), low)
  const trail = recent
    .filter(
      (item) =>
        item.possession_id != null &&
        (item.possession_id === event?.possession_id ||
          (item.metadata?.outcome === 'incomplete' &&
            timestamp - item.timestamp <= 1.8)) &&
        item.timestamp >= timestamp - 18 &&
        MOTION_TYPES.has(item.event_type),
    )
    .slice(-5)
  const cues = recent.filter(
    (item) =>
      CUE_TYPES.has(item.event_type) && timestamp - item.timestamp <= 1.8,
  )
  const latestCue = cues.at(-1)
  // Prefer the recorded tackle/interception/save over its accompanying ownership row.
  const cue =
    cues.findLast(
      (item) =>
        item.timestamp === latestCue?.timestamp &&
        item.event_type !== 'possession_change',
    ) ||
    latestCue ||
    null
  return {
    event,
    ball: ball || geometry.point,
    path: moving ? partialPath : geometry.path,
    trail,
    cue,
    inProgress: !!moving,
  }
}
