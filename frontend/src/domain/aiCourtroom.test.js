import { describe, expect, it } from 'vitest'
import { adaptCourtroomResponse, trialFailureMessage, trialIdentity } from './aiCourtroom.js'
import { aiCase, aiTrialResponse, AI_COPY } from '../test/aiTrialFixture.js'
import { events, matches } from '../test/fixtures.js'

const adapt = (response) => adaptCourtroomResponse(response, aiCase, events, matches[0], 15)

describe('AI response presentation boundary', () => {
  it.each(['live_ai', 'cached_ai'])('maps %s without replacing the replay record', (source) => {
    const trial = adapt(aiTrialResponse(source))
    expect(trial.source).toBe(source)
    expect(trial.arguments.prosecution[0].text).toBe(AI_COPY.prosecution)
    expect(trial.arguments.defense[0].text).toBe(AI_COPY.defense)
    expect(trial.evidenceFacts[0].text).toBe('1')
    expect(trial.knownEvents[0]).toBe(events[0])
    expect(trial.knownEvents.some((event) => event.event_id === 'later')).toBe(false)
    expect(trial.bounds).toEqual({ start: 0, end: 10 })
    expect(trial.assessment.confidence).toBe('medium')
  })

  it('retains recorded arguments when the backend returns fallback', () => {
    const trial = adapt(aiTrialResponse('deterministic_fallback'))
    expect(trial.source).toBe('recorded-evidence')
    expect(trial.backendSource).toBe('deterministic_fallback')
    expect(trial.arguments.prosecution[0].text).toBe('Attacking evidence')
    expect(trial.assessment.result).toBe('inconclusive')
    expect(trial.fallbackMessage).toContain('switched off')
  })

  it.each(['prosecution_supported', 'defense_supported', 'inconclusive'])(
    'leads a %s ruling with its cited finding, keeping uncertainty separate', (result) => {
      const response = aiTrialResponse()
      response.judge.result = result
      const trial = adapt(response)
      expect(trial.assessment.result).toBe(result)
      expect(trial.assessment.reason).toBe(AI_COPY.judge)
      expect(trial.assessment.reason).not.toBe(response.judge.uncertainty)
      expect(trial.assessment.leadFindingId).toBe(trial.assessment.findings[0].id)
      expect(trial.assessment.findings[0].eventIds).toEqual(['goal'])
      expect(trial.assessment.limitations).toContain(response.judge.uncertainty)
    },
  )

  it.each(['match', 'case', 'seed', 'cutoff', 'start', 'event', 'outcome', 'missing_event', 'duplicate_event',
    'future_citation', 'unknown_fact', 'wrong_quantity', 'mismatched_citation', 'trace', 'cached_attempts', 'live_attempts', 'extra_trigger', 'causation'])(
    'rejects %s corruption instead of partially repairing it', (kind) => {
      const response = aiTrialResponse(kind === 'cached_attempts' ? 'cached_ai' : 'live_ai')
      if (kind === 'match') response.evidence.match_id = 'b'
      if (kind === 'case') response.evidence.case_id = 'case-b'
      if (kind === 'seed') response.evidence.seed = 'unknown'
      if (kind === 'cutoff') response.evidence.evidence_cutoff = 20
      if (kind === 'start') response.evidence.evidence_start = 1
      if (kind === 'event') response.evidence.events[0].event_type = 'red_card'
      if (kind === 'outcome') response.evidence.events[0].outcome = 'goal'
      if (kind === 'missing_event') response.evidence.events.pop()
      if (kind === 'duplicate_event') response.evidence.events[1] = response.evidence.events[0]
      if (kind === 'future_citation') response.judge.findings[0].event_ids.push('later')
      if (kind === 'unknown_fact') response.defense.points[0].fact_ids.push('made-up-fact')
      if (kind === 'wrong_quantity') response.evidence_agent.observations[0].value = '999'
      if (kind === 'mismatched_citation') response.prosecution.points[0].event_ids = ['pass']
      if (kind === 'trace') response.trace[1].agent = 'judge'
      if (kind === 'cached_attempts') response.api_attempts = 4
      if (kind === 'live_attempts') response.api_attempts = 0
      if (kind === 'extra_trigger') response.evidence.trigger_event_ids.push('pass')
      if (kind === 'causation') response.judge.causation_established = true
      expect(() => adapt(response)).toThrow()
    },
  )

  it('scopes session results by match, case, seed and evidence bounds', () => {
    const first = trialIdentity(aiCase, matches[0])
    expect(trialIdentity(aiCase, { ...matches[0], seed: 999 })).not.toBe(first)
    expect(trialIdentity({ ...aiCase, case_id: 'other' }, matches[0])).not.toBe(first)
    expect(trialIdentity({ ...aiCase, available_timestamp: 20 }, matches[0])).not.toBe(first)
  })

  it('normalizes repeated valid observations without losing or repairing citations', () => {
    const response = aiTrialResponse()
    response.evidence_agent.observations.push(response.evidence_agent.observations[0])
    response.prosecution.points[0].fact_ids.push(response.prosecution.points[0].fact_ids[0])
    const trial = adapt(response)
    expect(trial.evidenceFacts).toHaveLength(1)
    expect(trial.arguments.prosecution[0].supports).toHaveLength(1)
  })

  it('rejects malformed failed trace fields and handles unknown categories safely', () => {
    const response = aiTrialResponse('deterministic_fallback')
    response.trace = [{ agent: 'evidence', status: 'failed', handoff_to: null,
      input_digest: 'a'.repeat(64), output_digest: 123, error_category: 'invalid_agent_output' }]
    expect(() => adapt(response)).toThrow()
    expect(typeof trialFailureMessage('__proto__')).toBe('string')
    expect(typeof trialFailureMessage('toString')).toBe('string')
  })
})
