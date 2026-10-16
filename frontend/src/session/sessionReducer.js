export const initialSession = {
  screen: 'welcome',
  matches: [],
  catalogStatus: 'loading',
  catalogVersion: 0,
  selectedMatchId: '',
  matchVersion: 0,
  matchData: null,
  events: [],
  dataStatus: 'idle',
  replayTimestamp: 0,
  pendingTimestamp: null,
  replayVersion: 0,
  snapshot: null,
  snapshotStatus: 'idle',
  isPlaying: false,
  replaySpeed: 1,
  selectedCaseId: '',
  courtroomReturnPosition: null,
  evidenceTimestamp: null,
  caseNotifications: [],
  seenCaseIds: [],
  statsOpen: true,
  error: '',
}

function selectMatch(session, id) {
  return {
    ...initialSession,
    screen: session.screen === 'courtroom' ? 'match' : session.screen,
    matches: session.matches,
    catalogStatus: session.catalogStatus,
    catalogVersion: session.catalogVersion,
    selectedMatchId: id,
    matchVersion: session.matchVersion + 1,
    replayVersion: session.replayVersion + 1,
    dataStatus: id ? 'loading' : 'idle',
    replaySpeed: session.replaySpeed,
    statsOpen: session.statsOpen,
  }
}

function requestReplay(session, timestamp, reset = false) {
  return {
    ...session,
    pendingTimestamp: timestamp,
    replayVersion: session.replayVersion + 1,
    snapshotStatus: 'loading',
    error: '',
    ...(reset || timestamp < session.replayTimestamp
      ? { selectedCaseId: '', seenCaseIds: [], caseNotifications: [] }
      : {}),
  }
}

export function sessionReducer(session, action) {
  switch (action.type) {
    case 'RETRY':
      return {
        ...selectMatch(session, session.selectedMatchId),
        catalogVersion: session.catalogVersion + 1,
        catalogStatus: 'loading',
      }
    case 'MATCHES_LOADED': {
      if (action.catalogVersion !== session.catalogVersion) return session
      const next = { ...session, matches: action.matches, catalogStatus: 'ready' }
      if (action.matches.some((match) => match.match_id === session.selectedMatchId)) return next
      return selectMatch(next, action.matches[0]?.match_id || '')
    }
    case 'CATALOG_FAILED':
      if (action.catalogVersion !== session.catalogVersion) return session
      return { ...session, catalogStatus: 'error', error: action.error, isPlaying: false }
    case 'SELECT_MATCH':
      if (action.id === session.selectedMatchId) return session
      return selectMatch(session, action.id)
    case 'MATCH_LOADED': {
      if (action.matchVersion !== session.matchVersion) return session
      const events = [...action.events].sort((a, b) => a.timestamp - b.timestamp || a.index - b.index)
      return requestReplay({ ...session, matchData: action.matchData, events, dataStatus: 'ready' }, 0)
    }
    case 'MATCH_FAILED':
      if (action.matchVersion !== session.matchVersion) return session
      return { ...session, dataStatus: 'error', error: action.error, isPlaying: false }
    case 'SNAPSHOT_LOADED': {
      if (action.matchVersion !== session.matchVersion || action.replayVersion !== session.replayVersion
        || action.snapshot.timestamp !== session.pendingTimestamp) return session
      const { snapshot } = action
      const ids = new Set(snapshot.cases.map((item) => item.case_id))
      const newCases = snapshot.cases.filter((item) => !session.seenCaseIds.includes(item.case_id))
      const notifications = [
        ...newCases.map((item) => ({ case_id: item.case_id, title: item.title, expiresAt: action.now + 5000 })),
        ...session.caseNotifications.filter((item) => ids.has(item.case_id) && item.expiresAt > action.now),
      ].slice(0, 3)
      return {
        ...session,
        snapshot,
        replayTimestamp: snapshot.timestamp,
        pendingTimestamp: null,
        snapshotStatus: 'ready',
        error: '',
        isPlaying: session.isPlaying && snapshot.timestamp < (session.events.at(-1)?.timestamp ?? 0),
        selectedCaseId: ids.has(session.selectedCaseId) ? session.selectedCaseId : snapshot.cases[0]?.case_id || '',
        seenCaseIds: [...new Set([...session.seenCaseIds, ...ids])],
        caseNotifications: notifications,
      }
    }
    case 'SNAPSHOT_FAILED':
      if (action.matchVersion !== session.matchVersion || action.replayVersion !== session.replayVersion) return session
      return { ...session, snapshotStatus: 'error', error: action.error, isPlaying: false }
    case 'TICK': {
      if (!session.isPlaying || session.screen !== 'match' || session.pendingTimestamp !== null) return session
      const nextEvent = session.events.find((event) => event.timestamp > session.replayTimestamp)
      return nextEvent ? requestReplay(session, nextEvent.timestamp) : { ...session, isPlaying: false }
    }
    case 'TOGGLE_PLAY': {
      if (session.screen !== 'match' || !session.snapshot || session.error) return session
      if (!session.isPlaying && session.replayTimestamp >= (session.events.at(-1)?.timestamp ?? 0)) {
        return { ...requestReplay(session, 0, true), isPlaying: true }
      }
      return { ...session, isPlaying: !session.isPlaying }
    }
    case 'RESET':
      if (session.screen !== 'match') return session
      return { ...requestReplay(session, 0, true), isPlaying: false }
    case 'SET_SPEED':
      return [0.5, 1, 2].includes(action.speed) ? { ...session, replaySpeed: action.speed } : session
    case 'NAVIGATE':
      if (!['welcome', 'match'].includes(action.screen)) return session
      return {
        ...session,
        screen: action.screen,
        isPlaying: false,
        courtroomReturnPosition: null,
        evidenceTimestamp: null,
      }
    case 'OPEN_COURTROOM': {
      const selected = session.snapshot?.cases.find((item) => item.case_id === action.caseId)
      if (!selected) return session
      return {
        ...session,
        screen: 'courtroom',
        isPlaying: false,
        pendingTimestamp: null,
        replayVersion: session.replayVersion + 1,
        snapshotStatus: 'ready',
        error: '',
        selectedCaseId: selected.case_id,
        courtroomReturnPosition: session.courtroomReturnPosition ?? session.replayTimestamp,
        evidenceTimestamp: selected.detection_timestamp,
      }
    }
    case 'REVIEW_EVIDENCE':
      if (session.screen !== 'courtroom' || !Number.isFinite(action.timestamp)) return session
      return {
        ...session,
        evidenceTimestamp: Math.max(0, Math.min(action.timestamp, session.courtroomReturnPosition)),
      }
    case 'EXPIRE_NOTIFICATIONS':
      return { ...session, caseNotifications: session.caseNotifications.filter((item) => item.expiresAt > action.now) }
    case 'TOGGLE_STATS':
      return { ...session, statsOpen: !session.statsOpen }
    default:
      return session
  }
}

export function visibleEvents(session) {
  // Statistics, cases, and event visibility all advance in the same commit.
  return session.snapshot ? session.events.filter((event) => event.timestamp <= session.replayTimestamp) : []
}
