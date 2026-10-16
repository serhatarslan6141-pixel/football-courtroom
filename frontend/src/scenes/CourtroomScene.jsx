import { useMatchSession } from '../session/useMatchSession.js'
import { formatClock, getCaseDisplayTitle, getMatchHeadline } from '../domain/formatters.js'

export default function CourtroomScene() {
  const { selectedCase, goToMatch, matchData, scoreText, replayTimestamp } = useMatchSession()

  if (!selectedCase) {
    return (
      <main className="page-shell">
        <section className="panel empty-panel">
          <p className="eyebrow">No case selected</p>
          <h2>No courtroom case is available yet.</h2>
          <p className="empty-state">Return to the match, keep replaying, and a case will appear when the evidence is strong enough.</p>
          <button type="button" className="primary-btn" onClick={goToMatch}>Back to match</button>
        </section>
      </main>
    )
  }

  const caseEvidence = selectedCase.evidence || []
  const counterEvidence = selectedCase.counterevidence || []
  const limitations = selectedCase.limitations || []
  const relevantWindows = selectedCase.relevant_windows || []

  return (
    <main className="page-shell courtroom-page">
      <section className="courtroom-hero panel">
        <div>
          <p className="eyebrow">The case</p>
          <h1>{getCaseDisplayTitle(selectedCase, matchData)}</h1>
        </div>
        <button type="button" className="secondary-btn" onClick={goToMatch}>Return to match</button>
      </section>

      <section className="panel scoreboard-panel">
        <div className="team-side">
          <span className="team-crest purple">{matchData?.home_team?.slice(0, 1)?.toUpperCase() || 'H'}</span>
          <div>
            <small>Home</small>
            <strong>{matchData?.home_team || 'Home club'}</strong>
          </div>
        </div>

        <div className="score-wrap">
          <span className="score">{scoreText}</span>
          <small>{formatClock(replayTimestamp)} • {getMatchHeadline(matchData)}</small>
        </div>

        <div className="team-side team-side-right">
          <div>
            <small>Away</small>
            <strong>{matchData?.away_team || 'Away club'}</strong>
          </div>
          <span className="team-crest gold">{matchData?.away_team?.slice(0, 1)?.toUpperCase() || 'A'}</span>
        </div>
      </section>

      <section className="courtroom-layout">
        <article className="panel main-case-panel">
          <div className="panel-header">
            <p className="eyebrow">Central question</p>
            <h3>{getCaseDisplayTitle(selectedCase, matchData)}</h3>
          </div>

          <div className="question-box">
            <p>Was this the moment that swung the match, or just a short spell that looked bigger in the replay?</p>
          </div>

          <div className="side-grid">
            <div className="side-panel prosecutor">
              <span className="side-label">Prosecution case</span>
              <ul>
                {caseEvidence.length ? caseEvidence.map((item) => <li key={`${selectedCase.case_id}-support-${item.label}`}>{item.value}</li>) : <li>Supportive facts will appear here as the evidence is weighed.</li>}
              </ul>
            </div>

            <div className="side-panel defense">
              <span className="side-label">Defence case</span>
              <ul>
                {counterEvidence.length ? counterEvidence.map((item) => <li key={`${selectedCase.case_id}-defense-${item}`}>{item}</li>) : <li>Counter-points will appear here as the evidence is weighed.</li>}
              </ul>
            </div>
          </div>
        </article>

        <aside className="panel side-case-panel">
          <div className="panel-header">
            <p className="eyebrow">Match context</p>
            <h3>What mattered</h3>
          </div>

          <div className="fact-grid">
            <div className="fact-box">
              <span>Case type</span>
              <strong>{selectedCase.case_type.replace(/_/g, ' ')}</strong>
            </div>
            <div className="fact-box">
              <span>Fixture</span>
              <strong>{getMatchHeadline(matchData)}</strong>
            </div>
            <div className="fact-box">
              <span>Minute</span>
              <strong>{formatClock(selectedCase.detection_timestamp)}</strong>
            </div>
            <div className="fact-box">
              <span>Confidence</span>
              <strong>{selectedCase.confidence || 'N/A'}</strong>
            </div>
          </div>

          <div className="judge-panel">
            <span className="side-label">Match official view</span>
            <ul>
              {limitations.length ? limitations.map((item) => <li key={`${selectedCase.case_id}-limit-${item}`}>{item}</li>) : <li>Official notes will be added here as the case is reviewed.</li>}
            </ul>
          </div>
        </aside>
      </section>

      <section className="panel timeline-panel">
        <div className="panel-header">
          <p className="eyebrow">Relevant moments</p>
          <h3>Context windows</h3>
        </div>
        <div className="window-grid">
          {relevantWindows.length ? relevantWindows.map((windowItem, index) => (
            <div key={`${selectedCase.case_id}-window-${index}`} className="window-card">
              <span>{windowItem.label}</span>
              <strong>{formatClock(windowItem.start)} - {formatClock(windowItem.end)}</strong>
            </div>
          )) : <p className="empty-state">No timeline windows are available yet.</p>}
        </div>
      </section>
    </main>
  )
}
