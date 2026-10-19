// Mock responses only. No model or backend network calls are made by this file.
import { caseItem, events } from './fixtures.js'

export const aiCase = { ...caseItem, match_id: 'a', trigger_event_ids: ['kickoff'] }
export const AI_COPY = {
  prosecution: 'The attacking spell gives the allegation a credible case.',
  defense: 'The same sequence leaves room for an alternative explanation.',
  evidence: 'The completed record supports scrutiny while leaving cause and effect open.',
  judge: 'The prosecution has a plausible reading, but the record cannot isolate its influence.',
}

export function aiTrialResponse(source = 'live_ai') {
  const factId = 'window:0:home:goals'
  const point = (interpretation) => ({ interpretation, fact_ids: [factId], event_ids: ['goal'] })
  return {
    source, disclosure: 'Mock AI reasoning over verified synthetic facts.',
    evidence: {
      source: 'verified_synthetic_match', match_id: 'a', case_id: aiCase.case_id, seed: 7,
      allegation: aiCase.title, case_type: aiCase.case_type, incident_timestamp: 0,
      evidence_start: 0, evidence_cutoff: 10, trigger_event_ids: ['kickoff'],
      events: events.filter((event) => event.timestamp <= 10).map((event) => ({
        event_id: event.event_id, timestamp: event.timestamp, clock: event.minute,
        event_type: event.event_type, team_id: event.team_id, team_name: 'Alpha',
        player_id: event.player_id ?? null, player_name: event.metadata?.player_name ?? null,
        outcome: event.metadata?.outcome ?? null, shot_quality: null, on_target: null,
        player_in: null, player_out: null,
      })),
      facts: [{ fact_id: factId, label: 'After the incident: Alpha: goals', value: '1', event_ids: ['goal'] }],
      limitations: ['Synthetic records cannot establish cause and effect.'], evidence_version: 'courtroom-evidence-v1',
    },
    evidence_agent: source === 'deterministic_fallback' ? null : {
      observations: [{ fact_id: factId, value: '1' }], event_ids: ['kickoff', 'goal'],
      interpretation: point(AI_COPY.evidence), uncertainty: 'The recorded spell does not establish causation.',
    },
    prosecution: { stance: 'support', points: [point(AI_COPY.prosecution)], uncertainty: 'Other influences may explain the pattern.' },
    defense: { stance: 'challenge', points: [point(AI_COPY.defense)], uncertainty: 'The evidence cannot isolate a counterfactual result.' },
    judge: {
      result: source === 'deterministic_fallback' ? 'inconclusive' : 'prosecution_supported',
      findings: [point(AI_COPY.judge)], prosecution_assessment: 'The attacking interpretation is plausible within the case window.',
      defense_assessment: 'The defense reasonably challenges a causal conclusion.',
      confidence: 'medium', uncertainty: 'Alternative explanations remain possible.',
      causation_established: false, counterfactual_outcome: 'unknown',
    },
    trace: source === 'deterministic_fallback' ? [] : ['evidence', 'prosecution', 'defense', 'judge'].map((agent, index, roles) => ({
      agent, status: 'completed', handoff_to: roles[index + 1] ?? null,
      input_digest: String(index + 1).repeat(64), output_digest: String(index + 2).repeat(64), error_category: null,
    })),
    api_attempts: source === 'live_ai' ? 4 : 0, original_api_attempts: source === 'deterministic_fallback' ? 0 : 4,
    error_category: source === 'deterministic_fallback' ? 'live_disabled' : null,
    http_status: source === 'deterministic_fallback' ? null : 200,
    cache_key: source === 'deterministic_fallback' ? null : 'a'.repeat(64), configuration_version: 'mock-courtroom-v2',
  }
}
