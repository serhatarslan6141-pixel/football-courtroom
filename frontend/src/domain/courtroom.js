import { clubFor } from './broadcast.js'
import { getCaseDisplayTitle } from './formatters.js'

export const TRIAL_STAGES = [
  { id: 'introduction', label: 'The case' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'arguments', label: 'Both sides' },
  { id: 'vote', label: 'Your verdict' },
  { id: 'verdict', label: 'The ruling' },
]
export const VOTE_LABELS = {
  prosecution: 'Agree with the prosecution',
  defense: 'Agree with the defense',
  insufficient: 'Not enough evidence',
}
export const voteKey = (matchId, caseId) => JSON.stringify([matchId, caseId])

export function caseAvailableAt(item) {
  const times = [
    item.detection_timestamp,
    item.available_timestamp ?? 0,
    ...(item.relevant_windows || []).flatMap((window) => [
      window.start,
      window.end,
    ]),
  ]
  if (times.some((value) => !Number.isFinite(value) || value < 0))
    return Infinity
  return Math.max(
    item.detection_timestamp ?? 0,
    item.available_timestamp ?? 0,
    ...(item.relevant_windows || []).map((window) => window.end),
  )
}

export function evidenceBounds(item, returnPosition) {
  const end = Math.min(returnPosition, caseAvailableAt(item))
  const starts = (item.relevant_windows || []).map((window) => window.start)
  return {
    start: Math.max(0, Math.min(end, item.detection_timestamp, ...starts)),
    end,
  }
}

export function scoreAt(events, timestamp) {
  const score = { home: 0, away: 0 }
  for (const event of events) {
    if (
      event.timestamp <= timestamp &&
      event.event_type === 'goal' &&
      event.team_id in score
    )
      score[event.team_id] += 1
  }
  return score
}

const TYPE_LABELS = {
  missed_opportunity: 'The missed chance',
  momentum_shift: 'The turning point',
  substitution_impact: 'The substitution',
}

function plainEvidence(text = '') {
  const outcome = text.match(/^Outcome recorded as (\w+)$/)
  if (outcome)
    return (
      {
        saved: 'The goalkeeper saved the shot.',
        off_target: 'The shot went wide.',
        blocked: 'The shot was blocked.',
        goal: 'The shot resulted in a goal.',
      }[outcome[1]] ||
      `The recorded shot outcome was ${outcome[1].replaceAll('_', ' ')}.`
    )
  const change = text.match(
    /^Pressure \+(-?[\d.]+); completion shift (-?[\d.]+)$/,
  )
  if (change) {
    const pressure = Number(change[1]),
      passing = Number(change[2]) * 100
    return `Pressing actions ${pressure < 0 ? 'fell' : 'rose'} by ${Math.abs(pressure)}; pass completion ${passing < 0 ? 'fell' : 'rose'} by ${Math.abs(passing).toFixed(0)} percentage points.`
  }
  return text
    .replaceAll('threat indicators', 'attacking entries, shots or goals')
    .replaceAll('pressure actions', 'pressing actions')
    .replaceAll('pressing events', 'pressing actions')
    .replaceAll('event stream', 'match record')
    .replaceAll('event-based', 'based on recorded actions')
    .replaceAll('replay cutoff', 'replay position')
    .replaceAll('causal model', 'proof of cause and effect')
    .replace(/\b1 passes\b/g, '1 pass')
    .replace(/\b1 pressing actions\b/g, '1 pressing action')
    .replace(/\b1 attacking actions\b/g, '1 attacking action')
}

/**
 * TrialPresentation v1: presentation-only boundary for a future response service.
 * Submissions carry case-evidence citations; assessment has a separate provenance.
 * Never interpret detector confidence as a judge's probability or causal proof.
 * Future responses must pass the same case, cutoff and citation checks upstream.
 */
export function createTrialPresentation(item, events, match, returnPosition) {
  if (
    !item ||
    !Number.isFinite(returnPosition) ||
    caseAvailableAt(item) > returnPosition
  )
    return null
  if (item.match_id && item.match_id !== match?.match_id) return null
  const bounds = evidenceBounds(item, returnPosition)
  const knownEvents = events.filter((event) => event.timestamp <= bounds.end)
  const knownIds = new Set(knownEvents.map((event) => event.event_id))
  const facts = (item.evidence || []).flatMap((fact, index) => {
    const ids = fact.event_ids || []
    // A text claim may summarize every cited event. Drop it entirely if even
    // one reference is missing/future; filtering citations alone is not enough.
    if (!fact.value || !ids.length || ids.some((id) => !knownIds.has(id)
      || knownEvents.find((event) => event.event_id === id).timestamp < bounds.start))
      return []
    return [
      {
        id: `evidence-${index}`,
        title: fact.label || 'Recorded evidence',
        text: plainEvidence(fact.value),
        context: plainEvidence(fact.context || ''),
        eventIds: ids,
        citation: { kind: 'evidence', index },
      },
    ]
  })
  const defenses = (item.counterevidence || []).map((text, index) => ({
    id: `counterpoint-${index}`,
    title: 'A different reading',
    text: plainEvidence(text),
    citation: { kind: 'counterevidence', index },
    eventIds: [],
  }))
  // Without a complete supporting record, do not repeat a textual counterclaim
  // about it either. The UI presents an explicit missing-record state instead.
  const complete =
    facts.length > 0 &&
    facts.length === (item.evidence || []).length &&
    (item.trigger_event_ids || []).every((id) => knownIds.has(id))
  const team = clubFor(match, item.teams?.team_id || item.team_id || 'home')
  const incident = knownEvents.find((event) =>
    (item.trigger_event_ids || []).includes(event.event_id),
  )
  const descriptions = {
    missed_opportunity: incident?.metadata?.description,
    substitution_impact: incident?.metadata?.description,
    momentum_shift: incident?.metadata?.description,
  }
  const limitations = item.limitations || []
  return {
    version: 1,
    source: 'recorded-evidence',
    caseId: item.case_id,
    question: getCaseDisplayTitle(item, match),
    label: TYPE_LABELS[item.case_type] || 'The disputed moment',
    summary:
      descriptions[item.case_type] ||
      'Examine the recorded moment, hear both sides and make your call.',
    team,
    incidentTimestamp: item.detection_timestamp,
    bounds,
    knownEvents,
    evidenceFacts: complete ? facts : [],
    arguments: {
      prosecution: complete ? facts : [],
      defense: complete ? defenses : [],
    },
    assessment: {
      source: 'recorded-evidence',
      result: 'inconclusive',
      label: 'Inconclusive',
      disclosure:
        'Assessment from recorded evidence. No AI judge has evaluated this case.',
      headline: 'The evidence leaves room for doubt.',
      findings: complete ? facts.slice(0, 2) : [],
      reason: complete
        ? 'The record establishes what happened in this spell. It does not establish how much that moment changed the match.'
        : 'The complete supporting record is not available. There is not enough evidence for a ruling.',
      limitations: limitations.length
        ? limitations.map(plainEvidence)
        : ['This record cannot establish cause and effect.'],
    },
  }
}
