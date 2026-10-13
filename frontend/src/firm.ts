// How the desk talks about the team, tickets, and tools.

import type { AgentName, Ticket } from './types'

export const AGENTS: { name: AgentName; title: string; role: string; initials: string }[] = [
  { name: 'boss', title: 'Boss', role: 'Managing Partner', initials: 'B' },
  { name: 'inventory', title: 'Inventory', role: 'Stock & Supply', initials: 'In' },
  { name: 'accounting', title: 'Accounting', role: 'Treasury', initials: 'Ac' },
  { name: 'facilities', title: 'Facilities', role: 'Premises', initials: 'Fa' },
  { name: 'customer_service', title: 'Customer Service', role: 'Client Relations', initials: 'CS' },
]

export const agentTitle = (name: AgentName | null | undefined) =>
  AGENTS.find((a) => a.name === name)?.title ?? 'The Desk'

// MCP tool names, in plain words.
const TOOL_WORDS: Record<string, string> = {
  check_stock: 'checking the shelf',
  get_vendor_status: 'calling on the vendors',
  get_bills_and_cash: 'reviewing the books',
  list_tickets: 'reading the docket',
  get_ticket: 'pulling the file',
  list_pending_requests: 'checking what awaits signature',
  list_payments: 'reviewing payments made',
  update_ticket: 'entering the ruling',
  request_payment: 'filing a payment request',
  post_draft: 'drafting correspondence',
  quote_price: 'pricing the offer',
  reserve_stock: 'setting stock aside',
  ask_teammate: 'consulting a colleague',
}

export const toolWords = (tool: string) => TOOL_WORDS[tool] ?? tool.replaceAll('_', ' ')

export const MATTER: Record<string, string> = {
  customer_order: 'Customer Order',
  rent_notice: 'Rent Notice',
  price_override: 'Price Request',
}

export const matterTitle = (t: Ticket) => `In re: ${t.subject}`

export const STATUS_WORDS: Record<Ticket['status'], string> = {
  open: 'Open',
  resolved: 'Closed',
  awaiting_approval: 'Awaiting your signature',
  blocked: 'Blocked',
  needs_info: 'Awaiting the client',
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

export const longDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
