export function createApiClient({
  baseUrl = import.meta.env.VITE_API_BASE_URL || '',
  fetchImpl = (...args) => fetch(...args),
} = {}) {
  const base = baseUrl.replace(/\/+$/, '')

  async function request(path, signal, options = {}) {
    const response = await fetchImpl(`${base}${path}`, { signal, ...options })
    if (!response.ok) {
      let message = `Request failed with status ${response.status}`
      try {
        const body = await response.json()
        if (typeof body.detail === 'string') message = body.detail
      } catch { /* Keep the HTTP status when the server returns a non-JSON error. */ }
      throw new Error(message)
    }
    return response.json()
  }

  const matchPath = (id) => `/api/matches/${encodeURIComponent(id)}`

  return {
    async listMatches(signal) {
      const catalog = await request('/api/matches', signal)
      // Current catalogs embed club colors; older name-only responses still work.
      const matches = await Promise.all((catalog.matches || []).map(async (match) => ({
        ...match, ...(match.teams?.length ? {} : await request(matchPath(match.match_id), signal)),
      })))
      return { ...catalog, matches }
    },
    createMatch(signal) {
      return request('/api/matches', signal, { method: 'POST' })
    },
    generateAiTrial(id, caseId, timestamp, signal) {
      return request(`${matchPath(id)}/cases/${encodeURIComponent(caseId)}/courtroom`, signal, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ through_timestamp: timestamp, allow_live: true }),
      })
    },
    async loadMatch(id, signal) {
      const [matchData, payload] = await Promise.all([
        request(matchPath(id), signal),
        request(`${matchPath(id)}/events`, signal),
      ])
      return { matchData, events: payload.events || [] }
    },
    async loadSnapshot(id, timestamp, signal) {
      const query = `through_timestamp=${timestamp}`
      const [statePayload, casePayload] = await Promise.all([
        request(`${matchPath(id)}/state?${query}`, signal),
        request(`${matchPath(id)}/cases?${query}`, signal),
      ])
      return { timestamp, state: statePayload.state, cases: casePayload.cases || [] }
    },
  }
}

export const apiClient = createApiClient()
