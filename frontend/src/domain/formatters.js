export const formatClock = (seconds) => {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0
  const minute = Math.floor(safeSeconds / 60)
  const second = safeSeconds % 60
  return `${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`
}

export const normalizeTeamKey = (value) => {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (normalized === 'home' || normalized === 'away') {
      return normalized
    }
    if (normalized === '0') {
      return 'home'
    }
    if (normalized === '1') {
      return 'away'
    }
  }

  if (value === 0 || value === 1) {
    return value === 0 ? 'home' : 'away'
  }

  return null
}

export const formatPercent = (value) => {
  const numeric = Number(value)
  if (value == null || value === '' || !Number.isFinite(numeric)) {
    return 'N/A'
  }
  return `${numeric.toFixed(1)}%`
}

export const formatPassRate = (value) => {
  const numeric = Number(value)
  if (value == null || value === '' || !Number.isFinite(numeric)) {
    return 'N/A'
  }
  return `${(numeric * 100).toFixed(1)}%`
}

export const getTeamNameForId = (teamKey, matchData) => {
  if (!teamKey) {
    return null
  }

  const normalizedKey = String(teamKey).trim().toLowerCase()
  if (normalizedKey === 'home') {
    return matchData?.home_team || 'Home'
  }
  if (normalizedKey === 'away') {
    return matchData?.away_team || 'Away'
  }

  const teamMatch = matchData
    ? [
        { teamId: 'home', name: matchData.home_team },
        { teamId: 'away', name: matchData.away_team },
      ].find((entry) => {
        const candidate = entry.name.toLowerCase().replace(/[^a-z]/g, '')
        return candidate.includes(normalizedKey.replace(/[^a-z]/g, ''))
      })
    : null

  if (teamMatch) {
    return teamMatch.name
  }

  return teamKey
}

export const getMatchHeadline = (matchData) => {
  if (!matchData) {
    return 'Selected match'
  }
  return `${matchData.home_team} vs ${matchData.away_team}`
}

export const getCaseDisplayTitle = (caseItem, matchData) => {
  if (!caseItem) {
    return 'Case'
  }

  let title = caseItem.title || 'Case'
  const teamId = caseItem.teams?.team_id || caseItem.team_id
  const teamName = getTeamNameForId(teamId, matchData)

  if (teamName) {
    title = title.replace(/\bHome\b|\bAway\b|\bhome\b|\baway\b/g, teamName)
  }

  return title
}

export const describeEvent = (event, matchData) => {
  const metadata = event?.metadata || {}
  if (metadata.description) {
    return metadata.description
  }

  const teamName = normalizeTeamKey(event.team_id) === 'home' ? matchData?.home_team : matchData?.away_team
  const playerName = metadata.player_name || 'Player'
  const playerLabel = metadata.recipient_name ? `${playerName} to ${metadata.recipient_name}` : playerName

  switch (event.event_type) {
    case 'pass':
      return `${playerLabel} ${metadata.outcome === 'complete' ? 'completes' : 'attempts'} a pass.`
    case 'pressure_event':
      return `${playerName} presses high to regain possession.`
    case 'shot':
      return `${playerName} takes a shot ${metadata.outcome === 'goal' ? 'and scores' : 'with intent'}.`
    case 'goal':
      return `${playerName} scores for ${teamName}.`
    case 'foul':
      return `${playerName} commits a foul.`
    case 'substitution':
      return `${metadata.player_in_name || 'Substitute'} comes on for ${metadata.player_out_name || 'the outgoing player'}.`
    case 'tackle':
      return `${playerName} makes a challenge.`
    case 'kickoff':
      return `${teamName} kick off.`
    case 'whistle':
      return 'The referee blows for full time.'
    case 'card':
      return `${playerName} is booked.`
    default:
      return event.event_type.replace(/_/g, ' ')
  }
}

