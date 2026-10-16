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
