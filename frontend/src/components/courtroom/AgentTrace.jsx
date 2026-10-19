import { AGENT_ROLES, isAiSource, trialFailureMessage } from '../../domain/aiCourtroom.js'
import EvidenceCitations from './EvidenceCitations.jsx'

export default function AgentTrace({ trial, loading, onCite, sealed }) {
  const references = {
    evidence: trial.evidenceInterpretation?.eventIds || [],
    prosecution: trial.arguments.prosecution.flatMap((point) => point.eventIds),
    defense: trial.arguments.defense.flatMap((point) => point.eventIds),
    judge: sealed ? [] : trial.assessment.findings.flatMap((point) => point.eventIds),
  }
  return (
    <details className="agent-trace">
      <summary>Behind the verdict</summary>
      {trial.trace?.length ? <>
        <p>Actual backend execution record. No individual progress was shown before this response arrived.</p>
        <ol>{trial.trace.map((entry, index) => <li key={entry.agent}>
          <strong>{AGENT_ROLES[index].name}</strong>
          <span>{entry.status === 'completed' ? 'Submission validated' : 'Stopped; submission withheld'}</span>
          <small>{entry.handoff_to ? `Handed to ${AGENT_ROLES.find((role) => role.id === entry.handoff_to).name}`
            : entry.status === 'completed' ? 'Final ruling returned' : 'No further handoff'}</small>
          {entry.status === 'completed' && isAiSource(trial.source) && (entry.agent === 'judge' && sealed
            ? <small>Ruling and its evidence references sealed until your vote.</small>
            : <EvidenceCitations eventIds={[...new Set(references[entry.agent])]} trial={trial} onCite={onCite} />)}
          <details className="handoff-fingerprints"><summary>Inspect {AGENT_ROLES[index].name} handoff</summary>
            <p>Input fingerprint <code title={entry.input_digest}>{entry.input_digest.slice(0, 12)}…</code></p>
            <p>Validated output <code title={entry.output_digest || ''}>{entry.output_digest ? `${entry.output_digest.slice(0, 12)}…` : 'Withheld'}</code></p>
            {entry.status === 'failed' && <p>{trialFailureMessage(entry.error_category)}</p>}
          </details>
        </li>)}</ol>
        <p>{trial.apiAttempts} model attempts for this request{trial.backendSource === 'cached_ai'
          ? `; ${trial.originalApiAttempts} during original generation. This result was reused from the backend cache.` : '.'}</p>
      </> : <>
        <p>{loading ? 'The workflow is running on the backend; no agent trace has been received yet.'
          : 'No agent execution record is available. This is the planned workflow, not completed work.'}</p>
        <ol aria-label="Planned agent order">{AGENT_ROLES.map((role) => <li key={role.id}>
          <strong>{role.name}</strong><span>{role.task}</span>
        </li>)}</ol>
      </>}
    </details>
  )
}
