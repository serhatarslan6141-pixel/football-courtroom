import { AGENT_ROLES, isAiSource, trialFailureMessage } from '../../domain/aiCourtroom.js'

export default function AiTrialPanel({ trial, request, available, invalid, onGenerate }) {
  const loading = request?.status === 'loading'
  const error = invalid || request?.status === 'error'
  const ai = isAiSource(trial.source)
  const label = loading ? 'Preparing the AI trial' : error ? 'Using recorded evidence'
    : trial.backendSource === 'cached_ai' ? 'Cached AI trial' : ai ? 'Live AI trial'
      : request?.status === 'fallback' ? 'Recorded-evidence fallback' : 'Recorded evidence'
  const message = loading
    ? 'The backend is preparing the trial. Individual agent progress is not streamed. You can continue reviewing the match record.'
    : error ? 'The response could not be confirmed or verified. It may have used model calls. Continue with the recorded trial; no automatic retry will be made.'
      : trial.fallbackMessage || (ai ? 'Four distinct agents have submitted their readings. Your vote remains independent of the judge.'
        : 'Hear the recorded case, or explicitly ask four AI agents to examine it. Generation may use paid AI; backend limits apply.')
  return (
    <section className={`ai-trial-panel${loading ? ' is-loading' : ''}`} aria-label="AI trial generation" aria-busy={loading}>
      <div className="ai-trial-heading">
        <div><span className="trial-overline">THE CASE. FOUR PERSPECTIVES.</span><h2>Let both sides be heard.</h2></div>
        <span className={`trial-source source-${ai ? 'ai' : 'recorded'}`}>{label}</span>
      </div>
      <ol className="agent-order" aria-label="Agent execution order">
        {AGENT_ROLES.map((role, index) => {
          const trace = trial.trace?.find((entry) => entry.agent === role.id)
          return <li key={role.id}>
            <span aria-hidden="true">{trace?.status === 'completed' ? '✓' : String(index + 1).padStart(2, '0')}</span>
            <div><strong>{role.name}</strong><small>{role.task}</small></div>
          </li>
        })}
      </ol>
      <div className="ai-trial-action">
        <p role={error ? 'alert' : 'status'} aria-live="polite">{message}</p>
        <button type="button" className="court-primary" onClick={onGenerate}
          disabled={!available || !!request || invalid}>
          {loading ? 'Preparing AI trial…' : ai ? 'AI trial ready' : request ? 'Trial request sent' : 'Generate AI Trial'}
        </button>
      </div>
      {!available && <small className="ai-disabled-note">AI generation is unavailable in this connection. The recorded trial remains fully playable.</small>}
      <details className="agent-trace">
        <summary>How the AI reached this decision</summary>
        {trial.trace?.length ? <>
          <p>Actual backend execution record. No individual progress was shown before this response arrived.</p>
          <ol>{trial.trace.map((entry, index) => <li key={entry.agent}>
            <strong>{AGENT_ROLES[index].name}</strong>
            <span>{entry.status === 'completed' ? 'Submission validated' : 'Stopped; submission withheld'}</span>
            <small>{entry.handoff_to ? `Handed to ${AGENT_ROLES.find((role) => role.id === entry.handoff_to).name}`
              : entry.status === 'completed' ? 'Final ruling returned' : 'No further handoff'}</small>
            <details className="handoff-fingerprints"><summary>Inspect {AGENT_ROLES[index].name} handoff</summary>
              <p>Input fingerprint <code title={entry.input_digest}>{entry.input_digest.slice(0, 12)}…</code></p>
              <p>Validated output <code title={entry.output_digest || ''}>{entry.output_digest ? `${entry.output_digest.slice(0, 12)}…` : 'Withheld'}</code></p>
              {entry.status === 'failed' && <p>{trialFailureMessage(entry.error_category)}</p>}
            </details>
          </li>)}</ol>
          <p>{trial.apiAttempts} model attempts for this request{trial.backendSource === 'cached_ai'
            ? `; ${trial.originalApiAttempts} during original generation. This result was reused from the backend cache.` : '.'}</p>
        </> : <p>{loading ? 'The workflow is running on the backend; no agent trace has been received yet.'
          : 'No agent execution record is available. The role order above describes the workflow, not completed work.'}</p>}
      </details>
    </section>
  )
}
