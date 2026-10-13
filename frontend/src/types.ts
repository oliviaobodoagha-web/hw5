// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'resolved' | 'awaiting_approval' | 'blocked' | 'needs_info'
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  status: 'queued' | 'running' | 'finished' | 'failed'
  error?: string
  decision?: Decision
}

export interface Decision {
  ticket_id: number
  assigned_to: AgentName[]
  decision: string
  rationale: string
  status: Ticket['status']
}

export interface AgentEvent {
  seq: number
  at: string
  run_id: string | null
  ticket_id: number | null
  agent: AgentName | null
  to_agent: AgentName | null
  event: string
  said: string | null
  tools: string[]
  model: string | null
}

export interface AgentMemo {
  agent: AgentName
  memo: string | null
  tools: string[]
  asked: AgentName[]
  model_calls: number
}

export interface TicketSummary {
  ticket_id: number
  run_id: string | null
  decision: Decision | null
  agents: AgentMemo[]
  tokens?: number
}

export interface PaymentRequest {
  id: number
  ticket_id: number
  kind: 'invoice' | 'rent'
  ref_id: number
  payee: string
  amount: number
  reason: string | null
  requested_by: string
  status: string
}

export interface Draft {
  id: number
  ticket_id: number
  kind: 'customer_message' | 'purchase_order'
  recipient: string
  subject: string
  body: string
  created_by: string
  status: string
}

export interface Approvals {
  payments: PaymentRequest[]
  purchase_orders: Draft[]
  customer_drafts: Draft[]
  pending_total: number
  cash_after_pending: number
}

export interface Payment {
  id: number
  kind: string
  ref_id: number
  amount: number
  paid_at: string
  approved_by: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  today: string
  pending_total: number
  balance_after_pending: number
  register: Payment[]
}
