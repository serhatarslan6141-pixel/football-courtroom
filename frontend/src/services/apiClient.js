export function createApiClient({
  baseUrl = import.meta.env.VITE_API_BASE_URL || '',
  fetchImpl = (...args) => fetch(...args),
} = {}) {
  const base = baseUrl.replace(/\/+$/, '')

  async function get(path, signal) {
    const response = await fetchImpl(`${base}${path}`, { signal })
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
    listMatches: (signal) => get('/api/matches', signal),
    async loadMatch(id, signal) {
      const [matchData, payload] = await Promise.all([
        get(matchPath(id), signal),
        get(`${matchPath(id)}/events`, signal),
      ])
      return { matchData, events: payload.events || [] }
    },
    async loadSnapshot(id, timestamp, signal) {
      const query = `through_timestamp=${timestamp}`
      const [statePayload, casePayload] = await Promise.all([
        get(`${matchPath(id)}/state?${query}`, signal),
        get(`${matchPath(id)}/cases?${query}`, signal),
      ])
      return { timestamp, state: statePayload.state, cases: casePayload.cases || [] }
    },
  }
}

export const apiClient = createApiClient()
