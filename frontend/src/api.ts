// Thin client for the FastAPI routes in backend/main.py.
// The backend runs at http://localhost:8000 and allows this page's origin (CORS).

import type { AgentEvent, Approvals, Cash, RunInfo, Ticket, TicketSummary } from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  return body as T
}

const post = <T>(path: string, data?: unknown) =>
  call<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) })

export const api = {
  tickets: () => call<{ tickets: Ticket[]; running: (RunInfo & { run_id: string }) | null }>('/tickets'),
  runTicket: (id: number) => post<{ run_id: string; ticket_id: number }>(`/tickets/${id}/run`),
  run: (runId: string) => call<RunInfo>(`/runs/${runId}`),
  summary: (id: number) => call<TicketSummary>(`/tickets/${id}/summary`),
  events: (params: { after?: number; run_id?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (params.after !== undefined) q.set('after', String(params.after))
    if (params.run_id) q.set('run_id', params.run_id)
    q.set('limit', String(params.limit ?? 500))
    return call<{ events: AgentEvent[]; last_seq: number }>(`/events?${q}`)
  },
  approvals: () => call<Approvals>('/approvals'),
  approve: (kind: 'payment' | 'purchase_order', id: number, by: string) =>
    post<Record<string, unknown>>('/approvals/approve', { kind, id, by }),
  reject: (kind: 'payment' | 'purchase_order', id: number, by: string, reason?: string) =>
    post<Record<string, unknown>>('/approvals/reject', { kind, id, by, reason }),
  cash: () => call<Cash>('/cash'),
  reset: (by: string) => post<{ reset: boolean }>('/reset', { by }),
}
