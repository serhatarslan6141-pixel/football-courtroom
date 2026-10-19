import { useEffect, useMemo, useRef, useState } from 'react'
import { useMatchSession } from '../session/useMatchSession.js'
import {
  createTrialPresentation,
  scoreAt,
  TRIAL_STAGES,
} from '../domain/courtroom.js'
import { formatClock } from '../domain/formatters.js'
import { clubFor } from '../domain/broadcast.js'
import ClubCrest from '../components/match/ClubCrest.jsx'
import CourtroomSet from '../components/courtroom/CourtroomSet.jsx'
import JudgeBench from '../components/courtroom/JudgeBench.jsx'
import TrialProgress from '../components/courtroom/TrialProgress.jsx'
import CaseIntroduction from '../components/courtroom/CaseIntroduction.jsx'
import EvidencePlayer from '../components/courtroom/EvidencePlayer.jsx'
import CounselPodium from '../components/courtroom/CounselPodium.jsx'
import ArgumentHearing from '../components/courtroom/ArgumentHearing.jsx'
import UserVerdict from '../components/courtroom/UserVerdict.jsx'
import JudgeVerdict from '../components/courtroom/JudgeVerdict.jsx'
import TrialStatus from '../components/courtroom/TrialStatus.jsx'
import TrialConfirmation from '../components/courtroom/TrialConfirmation.jsx'
import AgentTrace from '../components/courtroom/AgentTrace.jsx'
import VerifiedEvidenceFile from '../components/courtroom/VerifiedEvidenceFile.jsx'
import { adaptCourtroomResponse } from '../domain/aiCourtroom.js'
import './CourtroomScene.css'

function TrialRoom({ trial, invalid }) {
  const {
    matchData,
    trialStage,
    trialFurthestStage,
    setTrialStage,
    advanceTrial,
    evidenceTimestamp,
    reviewEvidence,
    caseVote,
    castCaseVote,
    goToMatch,
    aiTrial,
    beginTrial,
    confirmTrial,
    cancelTrial,
  } = useMatchSession()
  const stageElement = useRef(null)
  const beginButton = useRef(null)
  useEffect(() => {
    stageElement.current?.focus({ preventScroll: true })
  }, [trialStage])
  const [side, setSide] = useState('prosecution')
  const [submission, setSubmission] = useState(0)
  const [citationFocus, setCitationFocus] = useState(null)
  useEffect(() => {
    if (!citationFocus || trialStage !== 'evidence') return
    stageElement.current?.focus({ preventScroll: true })
    stageElement.current?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
  }, [citationFocus, trialStage])
  const citeEvent = (eventId) => {
    const event = trial.knownEvents.find((item) => item.event_id === eventId)
    if (!event || event.timestamp < trial.bounds.start || event.timestamp > trial.bounds.end) return
    reviewEvidence(event.timestamp)
    setTrialStage('evidence')
    setCitationFocus((previous) => ({ eventId, sequence: (previous?.sequence ?? 0) + 1 }))
  }
  const changeSide = (value) => {
    setSide(value)
    setSubmission(0)
  }
  const stageIndex = TRIAL_STAGES.findIndex((stage) => stage.id === trialStage)
  const incidentScore = scoreAt(trial.knownEvents, trial.incidentTimestamp)
  const home = clubFor(matchData, 'home'),
    away = clubFor(matchData, 'away')
  const busy = ['preparing', 'loading'].includes(aiTrial?.status)
  return (
    <main className="courtroom-scene">
      <div className="court-docket">
        <span>
          <i /> THE PEOPLE’S GAME. THE PEOPLE’S COURT.
        </span>
        <span>{trial.label}</span>
      </div>
      <div
        className="court-incident-bar"
        aria-label="Match context at the incident"
      >
        <div>
          <ClubCrest club={home} small />
          <span>{home.name}</span>
        </div>
        <strong aria-label="Score at the incident">
          {incidentScore.home} – {incidentScore.away}
        </strong>
        <div>
          <span>{away.name}</span>
          <ClubCrest club={away} small />
        </div>
        <span className="incident-minute">
          INCIDENT <time>{formatClock(trial.incidentTimestamp)}</time>
        </span>
      </div>
      <div className={`court-room stage-${trialStage}`}>
        <CourtroomSet />
        <JudgeBench stage={trialStage} />
        {trialStage !== 'introduction' ? (
          <p className="court-case-caption">{trial.question}</p>
        ) : null}
        <div className="trial-floor">
          <CounselPodium
            side="prosecution"
            count={trial.arguments.prosecution.length}
            interactive={trialStage === 'arguments'}
            active={trialStage === 'arguments' && side === 'prosecution'}
            onSelect={() => changeSide('prosecution')}
          />
          <div
            className="trial-stage"
            key={trialStage}
            ref={stageElement}
            tabIndex={-1}
            role="group"
            aria-label={TRIAL_STAGES[stageIndex].label}
          >
            {trialStage !== 'introduction' ? <TrialStatus trial={trial} request={aiTrial} invalid={invalid} /> : null}
            {trialStage === 'introduction' ? (
              <><CaseIntroduction trial={trial} onBegin={beginTrial} busy={busy} buttonRef={beginButton} />
                <TrialStatus trial={trial} request={aiTrial} invalid={invalid} /></>
            ) : null}
            {trialStage === 'evidence' ? (
              <><EvidencePlayer
                key={citationFocus?.sequence ?? 0}
                trial={trial}
                match={matchData}
                timestamp={evidenceTimestamp}
                onSeek={reviewEvidence}
                citedEventId={citationFocus?.eventId}
              /><VerifiedEvidenceFile trial={trial} onCite={citeEvent} /></>
            ) : null}
            {trialStage === 'arguments' ? (
              <ArgumentHearing
                trial={trial}
                side={side}
                index={submission}
                onSide={changeSide}
                onIndex={setSubmission}
                onEvidence={() => setTrialStage('evidence')}
                onCite={citeEvent}
              />
            ) : null}
            {trialStage === 'vote' ? (
              <UserVerdict vote={caseVote} onVote={castCaseVote} />
            ) : null}
            {trialStage === 'verdict' && caseVote ? (
              <JudgeVerdict
                assessment={trial.assessment}
                vote={caseVote}
                onReturn={goToMatch}
                trial={trial}
                onCite={citeEvent}
              />
            ) : null}
          </div>
          <CounselPodium
            side="defense"
            count={trial.arguments.defense.length}
            interactive={trialStage === 'arguments'}
            active={trialStage === 'arguments' && side === 'defense'}
            onSelect={() => changeSide('defense')}
          />
        </div>
        <AgentTrace trial={trial} loading={aiTrial?.status === 'loading'} onCite={citeEvent} sealed={!caseVote} />
      </div>
      {aiTrial?.status === 'confirmation' ? <TrialConfirmation onConfirm={confirmTrial} onCancel={cancelTrial} returnFocus={beginButton} /> : null}
      <TrialProgress
        stage={trialStage}
        furthest={trialFurthestStage}
        onNavigate={setTrialStage}
      />
      <div className="trial-footer">
        {stageIndex > 0 ? (
          <button
            type="button"
            className="court-text"
            onClick={() => setTrialStage(TRIAL_STAGES[stageIndex - 1].id)}
          >
            ← {TRIAL_STAGES[stageIndex - 1].label}
          </button>
        ) : (
          <span>A MOMENT ON THE PITCH. A QUESTION FOR THE COURT.</span>
        )}
        {trialStage === 'evidence' || trialStage === 'arguments' ? (
          <button
            type="button"
            className="court-primary"
            onClick={advanceTrial}
          >
            {trialStage === 'evidence'
              ? 'Hear the arguments'
              : 'Make your call'}{' '}
            <span aria-hidden="true">→</span>
          </button>
        ) : (
          <small>SIMULATED MATCH · REAL DEBATE</small>
        )}
      </div>
    </main>
  )
}

export default function CourtroomScene() {
  const {
    selectedCase,
    events,
    matchData,
    courtroomReturnPosition,
    goToMatch,
    aiTrial,
  } = useMatchSession()
  const { trial, invalid } = useMemo(
    () => {
      const recorded = createTrialPresentation(
        selectedCase,
        events,
        matchData,
        courtroomReturnPosition,
      )
      if (!aiTrial?.result) return { trial: recorded, invalid: false }
      try {
        return { trial: adaptCourtroomResponse(aiTrial.result, selectedCase, events, matchData, courtroomReturnPosition), invalid: false }
      } catch {
        return { trial: recorded, invalid: true }
      }
    },
    [selectedCase, events, matchData, courtroomReturnPosition, aiTrial],
  )
  if (!trial)
    return (
      <main className="court-empty">
        <h1>The court is waiting.</h1>
        <p>
          Return to the match to discover a case with a complete evidence
          window.
        </p>
        <button className="court-primary" type="button" onClick={goToMatch}>
          Back to match
        </button>
      </main>
    )
  return <TrialRoom key={trial.caseId} trial={trial} invalid={invalid} />
}
