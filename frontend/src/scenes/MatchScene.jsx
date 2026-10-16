import { useMatchSession } from '../session/useMatchSession.js'
import { eligibleCases } from '../domain/broadcast.js'
import { replayVisual } from '../domain/replayVisual.js'
import FixturePicker from '../components/match/FixturePicker.jsx'
import Scorebug from '../components/match/Scorebug.jsx'
import PitchStage from '../components/match/PitchStage.jsx'
import EventCaption from '../components/match/EventCaption.jsx'
import ReplayTransport from '../components/match/ReplayTransport.jsx'
import MatchTimeline from '../components/match/MatchTimeline.jsx'
import CaseAlert from '../components/match/CaseAlert.jsx'
import MatchSideRail from '../components/match/MatchSideRail.jsx'
import './MatchScene.css'

export default function MatchScene() {
  const {
    matches,
    matchData,
    selectedMatchId,
    fixtureConfirmed,
    matchLoading,
    matchError,
    setSelectedMatchId,
    confirmFixture,
    showFixtures,
    loadMatches,
    state,
    events,
    liveEvents,
    replayTimestamp,
    pendingTimestamp,
    cases,
    caseNotifications,
    isPlaying,
    replaySpeed,
    handlePlayPause,
    handleReset,
    setReplaySpeed,
    seekReplay,
    skipReplay,
    openCourtroom,
  } = useMatchSession()

  if (!fixtureConfirmed)
    return (
      <FixturePicker
        matches={matches}
        selectedId={selectedMatchId}
        onSelect={setSelectedMatchId}
        onEnter={confirmFixture}
        loading={matchLoading}
        error={matchError}
        onRetry={loadMatches}
      />
    )

  const availableCases = eligibleCases(cases, replayTimestamp)
  const notification = caseNotifications
    .map((item) =>
      availableCases.find((candidate) => candidate.case_id === item.case_id),
    )
    .find(Boolean)
  const currentEvent = replayVisual(events, replayTimestamp).event
  const duration = events.at(-1)?.timestamp ?? 5400

  return (
    <main className="broadcast-scene">
      <div className="broadcast-scene-heading">
        <div>
          <span className="broadcast-kicker">MATCH CENTRE</span>
          <h1>
            {matchData?.home_team} <span>vs</span> {matchData?.away_team}
          </h1>
        </div>
        <button
          type="button"
          className="broadcast-text-button"
          onClick={showFixtures}
        >
          ← Change fixture
        </button>
      </div>
      {matchError ? (
        <div role="alert" className="broadcast-error">
          {matchError}{' '}
          <button type="button" onClick={loadMatches}>
            Retry
          </button>
        </div>
      ) : null}
      <div className="broadcast-layout">
        <div className="broadcast-main">
          <div className="broadcast-score-row">
            <span className="replay-label">
              <i className="status-dot" /> MATCH REPLAY
            </span>
            <Scorebug
              match={matchData}
              state={state}
              timestamp={replayTimestamp}
            />
            <span className="broadcast-watermark">FC / BROADCAST</span>
          </div>
          <PitchStage
            event={currentEvent}
            events={events}
            timestamp={replayTimestamp}
            match={matchData}
          >
            <CaseAlert
              caseItem={notification}
              match={matchData}
              onOpen={openCourtroom}
            />
          </PitchStage>
          <EventCaption
            event={currentEvent}
            match={matchData}
            timestamp={replayTimestamp}
          />
          <MatchTimeline
            events={liveEvents}
            cases={availableCases}
            timestamp={replayTimestamp}
            pendingTimestamp={pendingTimestamp}
            duration={duration}
            onSeek={seekReplay}
            disabled={!state}
          />
          <ReplayTransport
            playing={isPlaying}
            speed={replaySpeed}
            disabled={!state || !events.length || !!matchError}
            busy={pendingTimestamp !== null}
            onPlayPause={handlePlayPause}
            onRestart={handleReset}
            onSpeed={setReplaySpeed}
            onSkip={skipReplay}
          />
        </div>
        <MatchSideRail
          key={selectedMatchId}
          state={state}
          events={liveEvents}
          cases={availableCases}
          match={matchData}
          onOpen={openCourtroom}
          onSeek={seekReplay}
        />
      </div>
      <footer className="broadcast-footer">
        <span>
          FOOTBALL COURTROOM <b> / </b> REPLAY STUDIO
        </span>
        <span>SIMULATED MATCH · FICTIONAL CLUBS & PLAYERS</span>
      </footer>
    </main>
  )
}
