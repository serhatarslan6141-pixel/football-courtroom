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
import './CourtroomScene.css'

function TrialRoom({ trial }) {
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
  } = useMatchSession()
  const stageElement = useRef(null)
  useEffect(() => {
    stageElement.current?.focus({ preventScroll: true })
  }, [trialStage])
  const [side, setSide] = useState('prosecution')
  const [submission, setSubmission] = useState(0)
  const changeSide = (value) => {
    setSide(value)
    setSubmission(0)
  }
  const stageIndex = TRIAL_STAGES.findIndex((stage) => stage.id === trialStage)
  const incidentScore = scoreAt(trial.knownEvents, trial.incidentTimestamp)
  const home = clubFor(matchData, 'home'),
    away = clubFor(matchData, 'away')
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
            {trialStage === 'introduction' ? (
              <CaseIntroduction trial={trial} onBegin={advanceTrial} />
            ) : null}
            {trialStage === 'evidence' ? (
              <EvidencePlayer
                trial={trial}
                match={matchData}
                timestamp={evidenceTimestamp}
                onSeek={reviewEvidence}
              />
            ) : null}
            {trialStage === 'arguments' ? (
              <ArgumentHearing
                trial={trial}
                side={side}
                index={submission}
                onSide={changeSide}
                onIndex={setSubmission}
                onEvidence={() => setTrialStage('evidence')}
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
      </div>
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
  } = useMatchSession()
  const trial = useMemo(
    () =>
      createTrialPresentation(
        selectedCase,
        events,
        matchData,
        courtroomReturnPosition,
      ),
    [selectedCase, events, matchData, courtroomReturnPosition],
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
  return <TrialRoom key={trial.caseId} trial={trial} />
}
