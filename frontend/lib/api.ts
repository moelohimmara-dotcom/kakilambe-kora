// Couche d'accès API KORA — toutes les requêtes vers le backend FastAPI

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const BASE_URL = BASE

// ── Agent ────────────────────────────────────────────────────────────────────
export const agentApi = {
  run: (mode: 'auto' | 'semi') =>
    request<{ cycle_id: string; status: string }>('/api/agent/run', {
      method: 'POST',
      body: JSON.stringify({ mode }),
    }),
  status: (cycleId?: string) =>
    request<Record<string, unknown>>(`/api/agent/status${cycleId ? `?cycle_id=${cycleId}` : ''}`),
  resume: (cycleId: string) =>
    request<{ status: string }>(`/api/agent/resume/${cycleId}`, { method: 'POST' }),
  reject: (cycleId: string) =>
    request<{ status: string }>(`/api/agent/reject/${cycleId}`, { method: 'POST' }),
  cancel: (cycleId: string) =>
    request<{ status: string }>(`/api/agent/cancel/${cycleId}`, { method: 'POST' }),
  streamUrl: (cycleId?: string) =>
    `${BASE}/api/agent/stream${cycleId ? `?cycle_id=${cycleId}` : ''}`,
}

// ── Articles ─────────────────────────────────────────────────────────────────
export const articleApi = {
  list: (status?: string, page = 1) =>
    request<{ items: import('./types').Article[]; total: number; page: number }>(
      `/api/articles?${status ? `status=${status}&` : ''}page=${page}`
    ),
  get: (id: string) => request<import('./types').Article>(`/api/articles/${id}`),
  patch: (id: string, data: Record<string, unknown>) =>
    request<import('./types').Article>(`/api/articles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  approve: (id: string) =>
    request<{ status: string }>(`/api/articles/${id}/approve`, { method: 'POST' }),
  reject: (id: string) =>
    request<{ status: string }>(`/api/articles/${id}/reject`, { method: 'POST' }),
  delete: (id: string) =>
    request<void>(`/api/articles/${id}`, { method: 'DELETE' }),
  regenerateImage: (id: string) =>
    request<{ image_url: string; wp_media_id: number }>(`/api/articles/${id}/regenerate-image`, { method: 'POST' }),
}

// ── Cycles ───────────────────────────────────────────────────────────────────
export const cycleApi = {
  list: (page = 1) =>
    request<{ items: import('./types').Cycle[]; total: number }>(
      `/api/cycles?page=${page}`
    ),
  get: (id: string) => request<import('./types').Cycle>(`/api/cycles/${id}`),
}

// ── Providers ─────────────────────────────────────────────────────────────────
export const providerApi = {
  list: () => request<import('./types').Provider[]>('/api/providers'),
  override: (name: string, status: string) =>
    request(`/api/providers/${name}/override`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
  reset: () => request('/api/providers/reset', { method: 'POST' }),
}

// ── Chat ──────────────────────────────────────────────────────────────────────
export const chatApi = {
  send: (messages: { role: string; content: string }[], opts?: { temperature?: number }) =>
    request('/api/chat', { method: 'POST', body: JSON.stringify({ messages, ...opts }) }),
  improve: (prompt: string) =>
    request('/api/chat/improve', { method: 'POST', body: JSON.stringify({ prompt }) }),
  streamUrl: (sessionId: string, message: string) =>
    `${BASE}/api/chat/stream?session_id=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(message)}`,
  sessions: () => request<import('./types').ChatSession[]>('/api/chat/sessions'),
  session: (id: string) =>
    request<{ session: import('./types').ChatSession; messages: import('./types').ChatMessage[] }>(
      `/api/chat/sessions/${id}`
    ),
  createSession: () =>
    request<import('./types').ChatSession>('/api/chat/sessions', { method: 'POST' }),
  updateSession: (id: string, data: Partial<Pick<import('./types').ChatSession, 'title' | 'is_pinned' | 'status'>>) =>
    request<import('./types').ChatSession>(`/api/chat/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteSession: (id: string) =>
    request<void>(`/api/chat/sessions/${id}`, { method: 'DELETE' }),
}

// ── Settings ──────────────────────────────────────────────────────────────────
export const settingsApi = {
  get: () => request<Record<string, unknown>>('/api/settings'),
  patch: (data: Record<string, unknown>) =>
    request('/api/settings', { method: 'PATCH', body: JSON.stringify(data) }),
  prompts: () => request<import('./types').SystemPrompt[]>('/api/settings/prompts'),
  updatePrompt: (id: string, data: Partial<import('./types').SystemPrompt>) =>
    request(`/api/settings/prompts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  resetPrompt: (id: string) =>
    request<{ reset: boolean; content: string; temperature: number }>(
      `/api/settings/prompts/${id}/reset`,
      { method: 'POST' }
    ),
  testEmail: () =>
    request<{ sent: boolean; to: string; provider: string }>('/api/settings/test-email', { method: 'POST' }),
  sources: () => request<import('./types').RSSSource[]>('/api/settings/sources'),
  createSource: (data: { name: string; url: string; category?: string }) =>
    request('/api/settings/sources', { method: 'POST', body: JSON.stringify(data) }),
  updateSource: (id: string, data: Partial<import('./types').RSSSource>) =>
    request(`/api/settings/sources/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSource: (id: string) =>
    request(`/api/settings/sources/${id}`, { method: 'DELETE' }),
  wpCategories: () => request<import('./types').WpCategory[]>('/api/settings/wp-categories'),
  syncWpCategories: () =>
    request<{ synced: number }>('/api/settings/wp-categories/sync', { method: 'POST' }),
  updateWpCategoryMapping: (wpId: number, koraLabel: string | null) =>
    request<import('./types').WpCategory>(`/api/settings/wp-categories/${wpId}`, {
      method: 'PATCH',
      body: JSON.stringify({ kora_label: koraLabel }),
    }),
}

// ── Health ────────────────────────────────────────────────────────────────────
export const healthApi = {
  check: () => request<{ status: string; services: Record<string, string> }>('/health'),
}
