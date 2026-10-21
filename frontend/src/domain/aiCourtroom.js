import { caseAvailableAt, createTrialPresentation, evidenceBounds } from './courtroom.js'

export const AGENT_ROLES = [
  { id: 'evidence', name: 'Evidence', task: 'Prioritize verified facts' },
  { id: 'prosecution', name: 'Prosecution', task: 'Make the strongest case' },
  { id: 'defense', name: 'Defense', task: 'Challenge the assumptions' },
  { id: 'judge', name: 'Judge', task: 'Weigh both sides' },
]
export const isAiSource = (source) => ['live_ai', 'cached_ai'].includes(source)

export function trialIdentity(item, match) {
  if (!item || !match) return ''
  return JSON.stringify([match.match_id, item.case_id, match.seed ?? null,
    caseAvailableAt(item), evidenceBounds(item, caseAvailableAt(item)).start])
}

function requireValue(condition) {
  if (!condition) throw new Error('The AI trial could not be verified against this case.')
}
function text(value, max = 600) {
  requireValue(typeof value === 'string' && value.trim().length > 0 && value.length <= max)
  return value
}
function refs(ids, known, allowEmpty = false) {
  requireValue(Array.isArray(ids) && (allowEmpty || ids.length > 0)
    && ids.every((id) => typeof id === 'string' && known.has(id)))
}

export function trialFailureMessage(category) {
  const messages = {
    connection_unavailable: 'The agent connection is unavailable. The court is using deterministic recorded analysis.',
    live_disabled: 'AI is switched off on the backend. The recorded-evidence trial is ready to use.',
    live_not_requested: 'The backend returned a recorded-evidence assessment.',
    configuration_unavailable: 'AI is not configured for this trial. Continue with the recorded evidence.',
    framework_unavailable: 'The AI agents are unavailable. Continue with the recorded evidence.',
    daily_budget_unavailable: 'The daily AI request allowance is unavailable or exhausted. No automatic retry will be made.',
    trial_call_limit: 'The trial reached its model-call limit. Partial AI submissions were set aside.',
    trial_in_progress: 'This trial is already being generated on the backend. Continue with the record; this page will not poll or resubmit.',
    previous_trial_failed_or_incomplete: 'An earlier trial did not complete. The backend has blocked repeat generation to avoid duplicate charges.',
    invalid_agent_output: 'An AI submission could not be verified. The court is using the recorded evidence instead.',
    authentication_or_access_denied: 'The backend could not access AI. Your recorded trial is still available.',
    timeout: 'AI generation timed out. The request may have used model calls, so it will not be retried automatically.',
  }
  return Object.hasOwn(messages, category) ? messages[category]
    : 'AI could not complete this trial. The recorded-evidence trial is still available; no automatic retry will be made.'
}

/** Validate the response's identity, cutoff, local event record and citations.
 * Keep the replay's original events; generated text never replaces that log.
 * The backend remains responsible for computing and verifying statistics.
 */
export function adaptCourtroomResponse(response, item, events, match, returnPosition) {
  const base = createTrialPresentation(item, events, match, returnPosition)
  requireValue(base && response && ['live_ai', 'cached_ai', 'deterministic_fallback'].includes(response.source))
  const file = response.evidence
  requireValue(file?.source === 'verified_synthetic_match' && file.match_id === match.match_id
    && file.case_id === item.case_id && file.case_type === item.case_type
    && Number.isInteger(file.seed) && (!Number.isFinite(match.seed) || file.seed === match.seed)
    && file.incident_timestamp === item.detection_timestamp
    && file.evidence_start === base.bounds.start && file.evidence_cutoff === base.bounds.end)
  const local = new Map(base.knownEvents.filter((event) => event.timestamp >= base.bounds.start)
    .map((event) => [event.event_id, event]))
  requireValue(Array.isArray(file.events) && file.events.length === local.size
    && new Set(file.events.map((event) => event.event_id)).size === local.size)
  for (const observed of file.events) {
    const event = local.get(observed.event_id)
    requireValue(event && observed.timestamp === event.timestamp && observed.event_type === event.event_type)
    for (const key of ['team_id', 'player_id']) requireValue((observed[key] ?? null) === (event[key] ?? null))
    for (const key of ['outcome', 'shot_quality', 'on_target', 'player_in', 'player_out']) {
      requireValue((observed[key] ?? null) === (event.metadata?.[key] ?? null))
    }
  }
  refs(file.trigger_event_ids, local)
  requireValue((item.trigger_event_ids || []).every((id) => file.trigger_event_ids.includes(id)))
  if (Array.isArray(item.trigger_event_ids)) requireValue(file.trigger_event_ids.length === item.trigger_event_ids.length)
  requireValue(Array.isArray(file.facts) && file.facts.length > 0)
  const facts = new Map()
  for (const fact of file.facts) {
    text(fact.fact_id, 250); text(fact.label, 500); text(fact.value, 500)
    requireValue(!facts.has(fact.fact_id))
    refs(fact.event_ids, local, true)
    facts.set(fact.fact_id, fact)
  }
  requireValue(Array.isArray(response.trace) && response.trace.length <= 4)
  let failed = false
  for (const [index, entry] of response.trace.entries()) {
    requireValue(!failed && entry.agent === AGENT_ROLES[index].id
      && ['completed', 'failed'].includes(entry.status) && /^[a-f0-9]{64}$/.test(entry.input_digest))
    failed = entry.status === 'failed'
    requireValue(entry.handoff_to === (failed ? null : AGENT_ROLES[index + 1]?.id ?? null))
    if (!failed) requireValue(/^[a-f0-9]{64}$/.test(entry.output_digest) && entry.error_category === null)
    else requireValue(entry.output_digest === null && typeof entry.error_category === 'string')
  }
  const metadata = { backendSource: response.source, trace: response.trace,
    apiAttempts: response.api_attempts, originalApiAttempts: response.original_api_attempts,
    configurationVersion: response.configuration_version }
  requireValue(Number.isInteger(response.api_attempts) && response.api_attempts >= 0 && response.api_attempts <= 4)
  if (!isAiSource(response.source)) {
    return { ...base, ...metadata, fallbackMessage: trialFailureMessage(response.error_category) }
  }
  requireValue(response.trace.length === 4 && !failed && response.evidence_agent)
  requireValue(response.original_api_attempts === 4)
  requireValue(response.api_attempts === (response.source === 'cached_ai' ? 0 : 4))
  const contribution = response.evidence_agent
  refs(contribution.event_ids, local)
  requireValue(file.trigger_event_ids.every((id) => contribution.event_ids.includes(id)))
  requireValue(Array.isArray(contribution.observations) && contribution.observations.length > 0 && contribution.observations.length <= 8)
  const observations = [...new Map(contribution.observations.map((assertion) => {
    const fact = facts.get(assertion.fact_id)
    requireValue(fact && fact.value === assertion.value)
    return [fact.fact_id, { id: fact.fact_id, title: fact.label.replaceAll('_', ' '), text: fact.value, eventIds: fact.event_ids }]
  })).values()]
  function point(value, id, title) {
    refs(value?.fact_ids, facts); refs(value.event_ids, local)
    const supporting = new Set(value.fact_ids.flatMap((factId) => facts.get(factId).event_ids))
    refs(value.event_ids, supporting)
    return { id, title, text: text(value.interpretation), eventIds: value.event_ids,
      supports: [...new Set(value.fact_ids)].map((factId) => ({ id: factId, title: facts.get(factId).label.replaceAll('_', ' '), text: facts.get(factId).value })) }
  }
  const evidenceInterpretation = point(contribution.interpretation, 'evidence-reading', 'The evidence agent’s reading')
  text(contribution.uncertainty)
  const argumentsFor = {}
  for (const side of ['prosecution', 'defense']) {
    const argument = response[side]
    requireValue(argument?.stance === (side === 'prosecution' ? 'support' : 'challenge')
      && Array.isArray(argument.points) && argument.points.length > 0 && argument.points.length <= 3)
    argumentsFor[side] = argument.points.map((value, index) => ({
      ...point(value, `${side}-${index}`, side === 'prosecution' ? 'The case for the allegation' : 'The case against the allegation'),
      context: text(argument.uncertainty),
    }))
  }
  const ruling = response.judge
  const labels = { prosecution_supported: 'Prosecution supported', defense_supported: 'Defense supported', inconclusive: 'Inconclusive' }
  requireValue(ruling && Object.hasOwn(labels, ruling.result) && ['low', 'medium'].includes(ruling.confidence)
    && ruling.causation_established === false && ruling.counterfactual_outcome === 'unknown'
    && Array.isArray(ruling.findings) && ruling.findings.length > 0 && ruling.findings.length <= 3)
  const findings = ruling.findings.map((value, index) => point(value, `finding-${index}`, 'The judge’s finding'))
  text(ruling.uncertainty)
  return {
    ...base, ...metadata, source: response.source, arguments: argumentsFor,
    evidenceFacts: observations, evidenceInterpretation: { ...evidenceInterpretation, context: contribution.uncertainty },
    assessment: {
      source: response.source, result: ruling.result, label: labels[ruling.result],
      headline: ruling.result === 'inconclusive' ? 'The court leaves room for doubt.' : ruling.result === 'prosecution_supported'
        ? 'The allegation has the stronger case.' : 'The defense raises the stronger case.',
      reason: findings[0].text, leadFindingId: findings[0].id, confidence: ruling.confidence,
      findings,
      sides: [{ name: 'Prosecution', text: text(ruling.prosecution_assessment) }, { name: 'Defense', text: text(ruling.defense_assessment) }],
      limitations: [ruling.uncertainty, ...file.limitations.map((value) => text(value))],
      disclosure: 'AI analysis of verified synthetic match facts. This ruling addresses the allegation within the case window.',
    },
  }
}
