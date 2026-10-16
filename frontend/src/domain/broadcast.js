export function clubFor(match, side) {
  const team = match?.teams?.find((item) => item.team_id === side)
  const name =
    team?.name || match?.[`${side}_team`] || (side === 'home' ? 'Home' : 'Away')
  return {
    name,
    shortName:
      team?.short_name ||
      match?.[`${side}_short_name`] ||
      name
        .split(' ')
        .map((word) => word[0])
        .join('')
        .slice(0, 3),
    color: team?.primary_color || '#b2b8c8',
    secondaryColor: team?.secondary_color || '#28313e',
  }
}

export function pitchPoint(value) {
  if (
    !value ||
    ![value.x, value.y].every(
      (number) =>
        typeof number === 'number' &&
        Number.isFinite(number) &&
        number >= 0 &&
        number <= 100,
    )
  )
    return null
  return { x: value.x * 1.05, y: value.y * 0.68 }
}

export function eventGeometry(event) {
  if (!event) return { point: null, path: null }
  const metadata = event.metadata || {}
  const location = pitchPoint(metadata.location) || pitchPoint(event)
  const start = pitchPoint(metadata.start) || location
  const end = pitchPoint(metadata.end) || pitchPoint(metadata.target)
  const canDrawPath = [
    'pass',
    'cross',
    'shot',
    'carry',
    'dribble',
    'clearance',
  ].includes(event.event_type)
  return {
    point: location || start || end,
    path: canDrawPath && start && end ? { start, end } : null,
  }
}

export function eligibleCases(cases, timestamp) {
  return cases.filter((item) => {
    const available =
      item.available_timestamp ??
      Math.max(
        item.detection_timestamp,
        ...(item.relevant_windows || []).map((window) => window.end),
      )
    return available <= timestamp
  })
}

export function timelineMarkers(events, cases, timestamp) {
  return [
    ...events
      .filter(
        (event) =>
          event.timestamp <= timestamp &&
          ['goal', 'substitution', 'card'].includes(event.event_type),
      )
      .map((event) => ({
        id: event.event_id,
        type: event.event_type,
        timestamp: event.timestamp,
      })),
    ...eligibleCases(cases, timestamp).map((item) => ({
      id: item.case_id,
      type: 'case',
      timestamp: item.available_timestamp ?? item.detection_timestamp,
    })),
  ]
}
