import { isAiSource } from '../../domain/aiCourtroom.js'

export default function TrialAnalysisControls({ trial, request, available, invalid, onGenerate }) {
  const loading = request?.status === 'loading'
  const error = invalid || request?.status === 'error'
  const ai = isAiSource(trial.source)
  const label = loading ? 'Preparing the AI trial' : error ? 'Using recorded evidence'
    : trial.backendSource === 'cached_ai' ? 'Cached AI trial' : ai ? 'Live AI trial'
      : request?.status === 'fallback' ? 'Recorded-evidence fallback' : 'Recorded evidence'
  const message = loading
    ? 'Individual agent progress is not streamed. You can continue the recorded trial while the backend prepares the analysis.'
    : error ? 'The response could not be confirmed or verified. It may have used model calls. Continue with the recorded trial; no automatic retry will be made.'
      : trial.fallbackMessage || (ai ? 'AI analysis is now in this trial. Your vote stays independent; the ruling stays sealed until you vote.'
        : available ? 'Optional: ask four AI agents to examine this case. May use paid AI; backend limits apply.'
          : 'AI generation is unavailable in this connection. The recorded trial remains fully playable.')
  return (
    <section className={`trial-analysis${loading ? ' is-loading' : ''}`} aria-label="Trial analysis" aria-busy={loading}>
      <div className="trial-analysis-options">
        <span className={`trial-source source-${ai ? 'ai' : 'recorded'}`}>{label}</span>
        <button type="button" className="court-text trial-generate" onClick={onGenerate}
          disabled={!available || !!request || invalid}>
          {loading ? 'Preparing AI trial…' : ai ? 'AI trial ready' : request ? 'Trial request sent' : 'Generate AI Trial'}
        </button>
      </div>
      <p role={error ? 'alert' : 'status'} aria-live="polite">{message}</p>
    </section>
  )
}
