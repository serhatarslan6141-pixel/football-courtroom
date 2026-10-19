import { useEffect, useReducer, useRef } from 'react'
import { caseAvailableAt, voteKey } from '../domain/courtroom.js'
import { adaptCourtroomResponse, trialIdentity } from '../domain/aiCourtroom.js'
import { apiClient } from '../services/apiClient.js'
import { MatchSessionContext } from './MatchSessionContext.js'
import { initialSession, sessionReducer, visibleEvents } from './sessionReducer.js'

export function MatchSessionProvider({ children, api = apiClient }) {
  const [session, dispatch] = useReducer(sessionReducer, initialSession)
  const preparedTrials = useRef(new Set())
  const submittedTrials = useRef(new Set())
  const trialRequestSequence = useRef(0)
  const activeTrial = () => {
    const item = session.snapshot?.cases.find((entry) => entry.case_id === session.selectedCaseId)
    if (session.screen !== 'courtroom' || !item || !session.matchData
      || !Number.isFinite(session.courtroomReturnPosition)
      || caseAvailableAt(item) > session.courtroomReturnPosition) return null
    return { item, key: trialIdentity(item, session.matchData) }
  }

  // Begin performs only a non-billable lookup. Neither navigation nor an effect
  // invokes this handler. A ref prevents duplicates before React rerenders.
  const beginTrial = () => {
    if (session.trialStage !== 'introduction') return
    const active = activeTrial()
    if (!active) return
    const { item, key } = active
    const current = session.aiTrials[key]
    if (current) {
      if (current.status === 'cancelled') {
        dispatch({ type: 'AI_TRIAL_CONFIRMATION_REQUIRED', key, requestId: current.requestId })
      } else if (['ready', 'fallback', 'error'].includes(current.status)) {
        dispatch({ type: 'ADVANCE_TRIAL' })
      }
      return
    }
    if (preparedTrials.current.has(key)) return
    preparedTrials.current.add(key)
    const requestId = ++trialRequestSequence.current
    dispatch({ type: 'AI_TRIAL_REQUEST', key, requestId })
    if (!api.prepareTrial) {
      dispatch({ type: 'AI_TRIAL_SUCCEEDED', key, requestId, errorCategory: 'connection_unavailable' })
      return
    }
    const prepare = async () => {
      try {
        const prepared = await api.prepareTrial(session.selectedMatchId, item.case_id, Math.floor(session.courtroomReturnPosition))
        if (prepared?.status === 'confirmation_required' && prepared.result === null && api.generateAiTrial) {
          dispatch({ type: 'AI_TRIAL_CONFIRMATION_REQUIRED', key, requestId })
        } else if (prepared?.status === 'ready' && ['cached_ai', 'deterministic_fallback'].includes(prepared.result?.source)
          && prepared.result.api_attempts === 0) {
          adaptCourtroomResponse(prepared.result, item, session.events, session.matchData, session.courtroomReturnPosition)
          dispatch({ type: 'AI_TRIAL_SUCCEEDED', key, requestId, result: prepared.result })
        } else {
          throw new Error('Invalid preparation response')
        }
      } catch {
        dispatch({ type: 'AI_TRIAL_FAILED', key, requestId, errorCategory: 'preparation_unavailable' })
      }
    }
    void prepare()
  }

  // The sole billable path: a click on the charge confirmation, with a current
  // backend preparation result and a second synchronous per-case lock.
  const confirmTrial = () => {
    if (session.trialStage !== 'introduction') return
    const active = activeTrial()
    if (!active) return
    const { item, key } = active
    const current = session.aiTrials[key]
    if (current?.status !== 'confirmation' || submittedTrials.current.has(key) || !api.generateAiTrial) return
    submittedTrials.current.add(key)
    const requestId = current.requestId
    dispatch({ type: 'AI_TRIAL_GENERATING', key, requestId })
    const generate = async () => {
      try {
        const result = await api.generateAiTrial(session.selectedMatchId, item.case_id, Math.floor(session.courtroomReturnPosition))
        adaptCourtroomResponse(result, item, session.events, session.matchData, session.courtroomReturnPosition)
        dispatch({ type: 'AI_TRIAL_SUCCEEDED', key, requestId, result })
      } catch {
        // Never echo arbitrary provider/network error text or retry a request
        // that may have reached Azure. The recorded proceeding remains usable.
        dispatch({ type: 'AI_TRIAL_FAILED', key, requestId })
      }
    }
    void generate()
  }
  const cancelTrial = () => {
    const active = activeTrial()
    if (active) dispatch({ type: 'AI_TRIAL_CONFIRMATION_CANCELLED', key: active.key,
      requestId: session.aiTrials[active.key]?.requestId })
  }
  const { catalogVersion, selectedMatchId, matchVersion, replayVersion, pendingTimestamp,
    dataStatus, screen, isPlaying, replaySpeed, caseNotifications, creationRequest } = session

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
    if (!creationRequest) return
    const controller = new AbortController()
    api.createMatch(controller.signal).then((match) => {
      if (!controller.signal.aborted) dispatch({ type: 'CREATE_MATCH_SUCCEEDED', version: creationRequest.version, match })
    }).catch((error) => {
      if (!controller.signal.aborted) dispatch({ type: 'CREATE_MATCH_FAILED', version: creationRequest.version, error: error.message })
    })
    return () => controller.abort()
  }, [api, creationRequest])

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

  const cases = session.snapshot?.cases || []
  const state = session.snapshot?.state || null
  const value = {
    ...session,
    state,
    cases,
    selectedCase: cases.find((item) => item.case_id === session.selectedCaseId) || null,
    liveEvents: visibleEvents(session),
    scoreText: state ? `${state.score.home} - ${state.score.away}` : 'N/A',
    matchLoading: !session.error && (session.catalogStatus === 'loading' || session.dataStatus === 'loading'
      || (session.dataStatus === 'ready' && !session.snapshot)),
    matchError: session.error,
    createMatch: () => dispatch({ type: 'CREATE_MATCH_REQUEST' }),
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
    caseVote: session.caseVotes[voteKey(session.selectedMatchId, session.selectedCaseId)] || null,
    aiTrial: session.aiTrials[trialIdentity(cases.find((item) => item.case_id === session.selectedCaseId), session.matchData)] || null,
    beginTrial,
    confirmTrial,
    cancelTrial,
    advanceTrial: () => dispatch({ type: 'ADVANCE_TRIAL' }),
    setTrialStage: (stage) => dispatch({ type: 'SET_TRIAL_STAGE', stage }),
    castCaseVote: (vote) => dispatch({ type: 'CAST_CASE_VOTE', vote, caseId: session.selectedCaseId, matchVersion: session.matchVersion }),
    reviewEvidence: (timestamp) => dispatch({ type: 'REVIEW_EVIDENCE', timestamp }),
  }

  return <MatchSessionContext.Provider value={value}>{children}</MatchSessionContext.Provider>
}
