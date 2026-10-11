// Thin fetch wrapper around the FastAPI backend.
// Dev (npm run dev): Vite proxies /api to localhost:8000.
// Production build: FastAPI serves this app itself, so the API is the same origin.
const BASE = import.meta.env.DEV ? '/api' : ''

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, timeout = 8000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
  } catch (err) {
    throw new ApiError(err.name === 'AbortError' ? 'Request timed out' : 'API unreachable', 0)
  } finally {
    clearTimeout(timer)
  }

  if (res.status === 204) return { data: null, headers: res.headers }
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.slice(1).join('.')}: ${d.msg}`).join('; ')
      : detail || `HTTP ${res.status}`
    throw new ApiError(message, res.status)
  }
  return { data, headers: res.headers }
}

const get = async (path) => (await request(path)).data

export const api = {
  health: () => get('/health'),
  stats: () => get('/cache/stats'),
  events: (after) => get(`/cache/events?after=${after}`),
  lookup: (accountId) => get(`/cache/lookup/${accountId}`),
  accounts: (limit, offset) => get(`/accounts?limit=${limit}&offset=${offset}`),
  securities: (q) => get(`/securities?q=${encodeURIComponent(q)}`),
  benchmark: () => get('/benchmark'),
  clearCache: () => request('/cache', { method: 'DELETE' }),
  trade: (accountId, body) => request(`/accounts/${accountId}/trades`, { method: 'POST', body }).then((r) => r.data),
  updatePrice: (ticker, close) =>
    request(`/securities/${encodeURIComponent(ticker)}/price`, { method: 'PUT', body: { close } }).then((r) => r.data),
  // Plain summary read; returns which tier answered (X-Cache) and server time.
  summary: async (accountId) => {
    const { headers } = await request(`/accounts/${accountId}/summary`)
    return { source: headers.get('X-Cache'), ms: Number(headers.get('X-Response-Time-ms')) }
  },
}
