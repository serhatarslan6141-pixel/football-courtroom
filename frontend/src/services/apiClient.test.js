import { describe, expect, it, vi } from 'vitest'
import { createApiClient } from './apiClient.js'
import { deferred, snapshot } from '../test/fixtures.js'
import { formatPassRate, formatPercent } from '../domain/formatters.js'

describe('API client', () => {
  it('keeps every fixture and loads its actual team colors for the picker', async () => {
    const matches = ['a', 'b', 'c'].map((match_id) => ({ match_id }))
    const fetchImpl = vi.fn(async (url) => ({
      ok: true,
      json: async () => url === '/api/matches' ? { matches, count: 3 } : {
        match_id: url.split('/').at(-1), teams: [{ team_id: 'home', primary_color: '#123456' }],
      },
    }))
    const catalog = await createApiClient({ baseUrl: '', fetchImpl }).listMatches()
    expect(catalog.matches.map((match) => match.match_id)).toEqual(['a', 'b', 'c'])
    expect(catalog.matches.every((match) => match.teams[0].primary_color === '#123456')).toBe(true)
    expect(fetchImpl).toHaveBeenCalledTimes(4)
  })

  it('requests both snapshot resources at exactly the same timestamp and waits for both', async () => {
    const cases = deferred()
    const fetchImpl = vi.fn((url) => url.includes('/cases') ? cases.promise : Promise.resolve({
      ok: true, json: async () => ({ state: snapshot(10).state }),
    }))
    const client = createApiClient({ baseUrl: 'https://example.test/backend/', fetchImpl })
    const controller = new AbortController()
    const done = vi.fn()
    const promise = client.loadSnapshot('match/id', 10, controller.signal).then(done)
    await Promise.resolve()
    expect(done).not.toHaveBeenCalled()
    expect(fetchImpl.mock.calls.map(([url]) => url)).toEqual([
      'https://example.test/backend/api/matches/match%2Fid/state?through_timestamp=10',
      'https://example.test/backend/api/matches/match%2Fid/cases?through_timestamp=10',
    ])
    for (const [, options] of fetchImpl.mock.calls) expect(options.signal).toBe(controller.signal)
    cases.resolve({ ok: true, json: async () => ({ cases: snapshot(10).cases }) })
    await promise
    expect(done).toHaveBeenCalledWith(snapshot(10))
  })

  it('rejects partial snapshots and reports backend errors', async () => {
    const client = createApiClient({ fetchImpl: async () => ({
      ok: false, status: 503, json: async () => ({ detail: 'Backend unavailable' }),
    }) })
    await expect(client.loadSnapshot('a', 0)).rejects.toThrow('Backend unavailable')
  })

  it('shows missing percentages as N/A while preserving genuine zero', () => {
    for (const value of [null, undefined, '', NaN]) {
      expect(formatPassRate(value)).toBe('N/A')
      expect(formatPercent(value)).toBe('N/A')
    }
    expect(formatPassRate(0)).toBe('0.0%')
    expect(formatPassRate(0.75)).toBe('75.0%')
  })
})

it('creates a match with one explicit POST using the configured origin and abort signal', async () => {
  const metadata = { match_id: 'generated-1', seed: 1 }
  const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => metadata }))
  const controller = new AbortController()
  const client = createApiClient({ baseUrl: 'https://example.test/', fetchImpl })
  expect(await client.createMatch(controller.signal)).toEqual(metadata)
  expect(fetchImpl).toHaveBeenCalledWith('https://example.test/api/matches', { signal: controller.signal, method: 'POST' })
})

it('loads a large catalog with embedded club colors without one request per fixture', async () => {
  const matches = Array.from({ length: 100 }, (_, id) => ({ match_id: String(id), teams: [{ team_id: 'home', primary_color: '#123456' }] }))
  const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({ matches }) }))
  const catalog = await createApiClient({ baseUrl: '', fetchImpl }).listMatches()
  expect(catalog.matches).toHaveLength(100)
  expect(fetchImpl).toHaveBeenCalledTimes(1)
})

it('generates a trial only on explicit invocation using encoded IDs and the minimal contract', async () => {
  const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({ source: 'deterministic_fallback' }) }))
  const client = createApiClient({ baseUrl: 'https://example.test/', fetchImpl })
  expect(fetchImpl).not.toHaveBeenCalled()
  await client.generateAiTrial('match/a', 'case/b', 100)
  expect(fetchImpl).toHaveBeenCalledTimes(1)
  expect(fetchImpl).toHaveBeenCalledWith('https://example.test/api/matches/match%2Fa/cases/case%2Fb/courtroom', {
    signal: undefined, method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ through_timestamp: 100, allow_live: true }),
  })
})

it('prepares a trial with no live opt-in or credentials in the request', async () => {
  const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({ status: 'confirmation_required', result: null }) }))
  const client = createApiClient({ baseUrl: '', fetchImpl })
  const controller = new AbortController()
  await client.prepareTrial('match/a', 'case/b', 100, controller.signal)
  expect(fetchImpl).toHaveBeenCalledExactlyOnceWith('/api/matches/match%2Fa/cases/case%2Fb/courtroom/prepare', {
    signal: controller.signal, method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ through_timestamp: 100 }),
  })
})
