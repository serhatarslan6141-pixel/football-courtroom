import { isAiSource, trialFailureMessage } from '../../domain/aiCourtroom.js'

export default function TrialStatus({ trial, request, invalid }) {
  if (!request) return null
  const loading = ['preparing', 'loading'].includes(request.status)
  const error = invalid || request.status === 'error'
  const ai = isAiSource(trial.source)
  const label = loading ? 'Preparing the court' : ['confirmation', 'cancelled'].includes(request.status)
    ? 'Awaiting confirmation' : trial.backendSource === 'cached_ai' ? 'Cached AI analysis'
      : ai ? 'Live AI analysis' : 'Deterministic fallback'
  const message = request.status === 'preparing' ? 'Checking trial availability. This step cannot make model requests.'
    : request.status === 'loading' ? 'The agents are preparing this case. Individual agent progress is not streamed.'
      : error ? request.errorCategory === 'preparation_unavailable'
        ? 'Trial availability could not be verified. The court will use recorded analysis; no generation was requested.'
        : 'The response could not be confirmed or verified. The court is using recorded analysis. Model calls may have occurred; no automatic retry will be made.'
        : trial.fallbackMessage || (request.errorCategory ? trialFailureMessage(request.errorCategory) : null)
  return <div className="trial-status" aria-busy={loading}>
    <span className={`trial-source source-${ai ? 'ai' : 'recorded'}`}>{label}</span>
    {message && <p role={error ? 'alert' : 'status'} aria-live="polite">{message}</p>}
  </div>
}
