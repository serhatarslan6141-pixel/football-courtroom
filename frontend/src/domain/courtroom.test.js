import { describe, expect, it } from 'vitest'
import {
  caseAvailableAt,
  createTrialPresentation,
  scoreAt,
} from './courtroom.js'
import { caseItem, events, matches } from '../test/fixtures.js'

const build = (item = caseItem, log = events, cutoff = 10) =>
  createTrialPresentation(item, log, matches[0], cutoff)

describe('evidence-grounded trial presentation', () => {
  it('keeps incident context separate from the score at courtroom entry', () => {
    const trial = build()
    expect(trial.question).toBe('Did Alpha gain momentum?')
    expect(scoreAt(events, trial.incidentTimestamp)).toEqual({
      home: 0,
      away: 0,
    })
    expect(scoreAt(events, 10)).toEqual({ home: 1, away: 0 })
    expect(trial.knownEvents.some((event) => event.event_id === 'later')).toBe(
      false,
    )
    expect(trial.bounds).toEqual({ start: 0, end: 10 })
  })

  it('requires every observation window to mature, even if available_timestamp is inconsistent', () => {
    expect(build(caseItem, events, 9)).toBeNull()
    const altered = {
      ...caseItem,
      available_timestamp: 5,
      relevant_windows: [{ start: 0, end: 20 }],
    }
    expect(caseAvailableAt(altered)).toBe(20)
    expect(build(altered)).toBeNull()
    expect(build({ ...caseItem, detection_timestamp: NaN })).toBeNull()
  })

  it('never presents claims whose citations include missing or future events', () => {
    for (const id of ['later', 'unknown']) {
      const trial = build({
        ...caseItem,
        evidence: [
          {
            label: 'Hidden',
            value: 'A future result',
            event_ids: ['goal', id],
          },
        ],
      })
      expect(trial.arguments.prosecution).toEqual([])
      expect(trial.arguments.defense).toEqual([])
      expect(trial.assessment.findings).toEqual([])
      expect(JSON.stringify(trial)).not.toContain('A future result')
      expect(trial.assessment.reason).toContain(
        'complete supporting record is not available',
      )
    }
  })

  it('presents existing evidence and counterevidence with traceable sources', () => {
    const trial = build()
    expect(trial.arguments.prosecution[0].text).toBe(caseItem.evidence[0].value)
    expect(trial.arguments.prosecution[0].eventIds).toEqual(['goal'])
    expect(trial.arguments.prosecution[0].citation).toEqual({
      kind: 'evidence',
      index: 0,
    })
    expect(trial.arguments.defense[0].text).toBe(caseItem.counterevidence[0])
    expect(trial.arguments.defense[0].citation).toEqual({
      kind: 'counterevidence',
      index: 0,
    })
  })

  it('translates outcome and comparison shorthand without changing the recorded quantities', () => {
    const trial = build({
      ...caseItem,
      evidence: [
        {
          label: 'Outcome',
          value: 'Outcome recorded as saved',
          event_ids: ['goal'],
        },
        {
          label: 'Change',
          value: 'Pressure +-4; completion shift 0.22',
          event_ids: ['pass'],
        },
      ],
    })
    expect(trial.arguments.prosecution[0].text).toBe(
      'The goalkeeper saved the shot.',
    )
    expect(trial.arguments.prosecution[1].text).toContain('fell by 4')
    expect(trial.arguments.prosecution[1].text).toContain(
      'rose by 22 percentage points',
    )
  })

  it.each(['missed_opportunity', 'momentum_shift', 'substitution_impact'])(
    'does not convert high %s detector confidence into a conclusive judgment',
    (type) => {
      const trial = build({ ...caseItem, confidence: 'high', case_type: type })
      expect(trial.assessment.result).toBe('inconclusive')
      expect(trial.assessment.source).toBe('recorded-evidence')
      expect(trial.assessment.limitations).toEqual(caseItem.limitations)
      expect(trial.assessment.findings).toHaveLength(1)
    },
  )
})

it('does not accept uncited claims or evidence belonging to another match', () => {
  const uncited = build({
    ...caseItem,
    evidence: [{ label: 'Claim', value: 'An unsupported assertion' }],
  })
  expect(uncited.arguments.prosecution).toEqual([])
  expect(uncited.assessment.result).toBe('inconclusive')
  expect(build({ ...caseItem, match_id: 'b' })).toBeNull()
})
