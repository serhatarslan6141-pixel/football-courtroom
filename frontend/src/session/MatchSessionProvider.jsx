import { useEffect, useMemo, useReducer } from 'react'
import { apiClient } from '../services/apiClient.js'
import { MatchSessionContext } from './MatchSessionContext.js'
import { initialSession, sessionReducer, visibleEvents } from './sessionReducer.js'

export function MatchSessionProvider({ children, api = apiClient }) {
  const [session, dispatch] = useReducer(sessionReducer, initialSession)
  const { catalogVersion, selectedMatchId, matchVersion, replayVersion, pendingTimestamp,
    dataStatus, screen, isPlaying, replaySpeed, caseNotifications } = session

  useEffect(() => {
    const controller = new AbortController()
    api.listMatches(controller.signal).then((payload) => {
      if (!controller.signal.aborted) dispatch({ type: 'MATCHES_LOADED', catalogVersion, matches: payload.matches || [] })
    }).catch((error) => {
      if (!controller.signal.aborted) dispatch({ type: 'CATALOG_FAILED', catalogVersion, error: error.message })
    })
    return () => controller.abort()
  }, [api, catalogVersion])

  useEffect(() => {
    if (!selectedMatchId) return
    const controller = new AbortController()
    api.loadMatch(selectedMatchId, controller.signal).then((payload) => {
      if (!controller.signal.aborted) dispatch({ type: 'MATCH_LOADED', matchVersion, ...payload })
    }).catch((error) => {
      if (!controller.signal.aborted) dispatch({ type: 'MATCH_FAILED', matchVersion, error: error.message })
    })
    return () => controller.abort()
  }, [api, selectedMatchId, matchVersion])

  useEffect(() => {
    if (!selectedMatchId || dataStatus !== 'ready' || pendingTimestamp === null) return
    const controller = new AbortController()
    api.loadSnapshot(selectedMatchId, pendingTimestamp, controller.signal).then((snapshot) => {
      if (!controller.signal.aborted) {
        dispatch({ type: 'SNAPSHOT_LOADED', matchVersion, replayVersion, snapshot, now: Date.now() })
      }
    }).catch((error) => {
      if (!controller.signal.aborted) dispatch({ type: 'SNAPSHOT_FAILED', matchVersion, replayVersion, error: error.message })
    })
    return () => controller.abort()
  }, [api, selectedMatchId, dataStatus, pendingTimestamp, matchVersion, replayVersion])

  useEffect(() => {
    if (!isPlaying || screen !== 'match' || pendingTimestamp !== null) return
    let previous = null
    let frame
    const advance = (now) => {
      if (previous === null) previous = now
      if (now - previous >= 30) {
        dispatch({ type: 'ADVANCE_CLOCK', elapsed: (now - previous) / 1000 })
        previous = now
      }
      frame = window.requestAnimationFrame(advance)
    }
    frame = window.requestAnimationFrame(advance)
    return () => window.cancelAnimationFrame(frame)
  }, [isPlaying, screen, pendingTimestamp, replaySpeed])

  useEffect(() => {
    if (!caseNotifications.length) return
    const expiresAt = Math.min(...caseNotifications.map((item) => item.expiresAt))
    const timer = window.setTimeout(() => {
      dispatch({ type: 'EXPIRE_NOTIFICATIONS', now: Date.now() })
    }, Math.max(0, expiresAt - Date.now()))
    return () => window.clearTimeout(timer)
  }, [caseNotifications])

  const value = useMemo(() => {
    const cases = session.snapshot?.cases || []
    const state = session.snapshot?.state || null
    return {
      ...session,
      state,
      cases,
      selectedCase: cases.find((item) => item.case_id === session.selectedCaseId) || null,
      liveEvents: visibleEvents(session),
      scoreText: state ? `${state.score.home} - ${state.score.away}` : 'N/A',
      matchLoading: !session.error && (session.catalogStatus === 'loading' || session.dataStatus === 'loading'
        || (session.dataStatus === 'ready' && !session.snapshot)),
      matchError: session.error,
      loadMatches: () => dispatch({ type: 'RETRY' }),
      setSelectedMatchId: (id) => dispatch({ type: 'SELECT_MATCH', id }),
      confirmFixture: () => dispatch({ type: 'CONFIRM_FIXTURE' }),
      showFixtures: () => dispatch({ type: 'SHOW_FIXTURES' }),
      seekReplay: (timestamp) => dispatch({ type: 'SEEK', timestamp }),
      skipReplay: (direction) => dispatch({ type: 'SKIP', direction }),
      handlePlayPause: () => dispatch({ type: 'TOGGLE_PLAY' }),
      handleReset: () => dispatch({ type: 'RESET' }),
      setReplaySpeed: (speed) => dispatch({ type: 'SET_SPEED', speed }),
      goToWelcome: () => dispatch({ type: 'NAVIGATE', screen: 'welcome' }),
      goToMatch: () => dispatch({ type: 'NAVIGATE', screen: 'match' }),
      openCourtroom: (item) => dispatch({ type: 'OPEN_COURTROOM', caseId: item?.case_id || session.selectedCaseId }),
      reviewEvidence: (timestamp) => dispatch({ type: 'REVIEW_EVIDENCE', timestamp }),
    }
  }, [session])

  return <MatchSessionContext.Provider value={value}>{children}</MatchSessionContext.Provider>
}
