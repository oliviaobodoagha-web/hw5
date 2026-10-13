# Campus Customs MCP Server

This MCP server is the shop's only data layer. Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) and the FastAPI backend read and change shop data **only** through these tools. Nothing else opens the database. Built with [FastMCP](https://gofastmcp.com).

## Data file

- **Working copy:** `data/campus_customs_new.db`. Every tool reads and writes this file.
- **Original:** `data/campus_customs.db`. It is never written. `reset_shop` copies it over the working copy before each full run.
- **Today:** the shop's "today" is `desk.date_today` (2026-08-31), not the real clock. Due dates, overdue checks, and payment dates all use it.
- **Board tables:** the server adds four tables to the working copy if they are missing: `approval_requests` (the payment approval queue), `board_drafts` (customer messages and purchase orders), `stock_reservations` (units set aside for a ticket), and `price_quotes` (approved customer prices). A reset wipes them and restores the stock counts.
- **No guessing:** tools return only what is in the database. A missing record returns an error, not a guess. Payment amounts and payees always come from the database, never from the caller.

## Tools (16)

### Read the shop
| Tool | What it returns | Tables |
|---|---|---|
| `check_stock(sku, size=None)` | Free on-hand quantity and shelf location for a SKU (one size or all), unit cost, list price, margin per unit, and any reservations | `inventory`, `pricing`, `stock_reservations` |
| `get_vendor_status(vendor_id=None)` | Each vendor's specialty, lead time, open invoices with days overdue, whether it will ship (no open unpaid invoices), and the earliest arrival if ordered today | `vendors`, `invoices`, `desk` |
| `get_bills_and_cash()` | Every open obligation (lease rent and open invoices) with days until due, next to cash balances, total owed, and whether cash covers it all | `leases`, `invoices`, `vendors`, `cash_accounts`, `desk` |
| `list_tickets(status=None)` | Tickets on the board, optionally filtered by status | `tickets` |
| `get_ticket(ticket_id)` | One ticket with its current status and notes | `tickets` |
| `list_pending_requests()` | Payment requests waiting for approval, board drafts, saved price quotes, and cash left if every pending payment is approved | `approval_requests`, `board_drafts`, `price_quotes`, `cash_accounts` |
| `list_payments()` | Payments made, total paid, and every request a human has decided (paid or rejected) | `payments`, `approval_requests` |

### Work the board (agents)
| Tool | What it does | Tables |
|---|---|---|
| `update_ticket(ticket_id, status, note, updated_by)` | Sets a ticket's status (open, resolved, awaiting_approval, blocked, needs_info) and appends a dated note. The original notes are kept | `tickets` |
| `request_payment(ticket_id, kind, ref_id, reason, requested_by, account="checking")` | Queues a rent or invoice payment for human approval. **It pays nothing.** It refuses if the bill is already paid, already pending, or was rejected by a human, or if cash minus all pending requests can't cover it | reads `invoices`, `leases`, `vendors`, `cash_accounts`; writes `approval_requests` |
| `post_draft(ticket_id, kind, recipient, subject, body, created_by)` | Saves a customer message or purchase order on the board. **Nothing is sent.** Purchase orders wait for approval. A customer message is **refused** if it contains any dollar amount that isn't a saved quote, the list price, or the lease rent for that ticket, or if it doesn't name the ticket's product exactly as the catalog does, names a different product, or shows a SKU code | reads `price_quotes`, `pricing`, `leases`, `inventory`, `tickets`; writes `board_drafts` |
| `quote_price(ticket_id, sku, qty, discount_pct, quoted_by, size=None)` | Prices a customer offer from the database (list × (1 − discount%)) and saves it. **Refuses any price at or below unit cost** and says the maximum discount | reads `pricing`, `tickets`; writes `price_quotes` |
| `reserve_stock(ticket_id, sku, size, qty, reserved_by)` | Takes units off the shelf count for one ticket after Boss's final call. Refuses more than is on hand and a second reservation for the same ticket and item | `inventory`, `stock_reservations` |

### Human only (hidden from every agent)
| Tool | What it does | Tables |
|---|---|---|
| `pay(request_id, approved_by)` | Pays a pending request after a human approves. Refuses with no approver, an agent as approver, a non-pending or already-paid bill, or not enough cash. In one transaction it writes the payment, lowers cash, and marks the invoice paid or moves the lease's `next_due` forward a month | `approval_requests`, `payments`, `cash_accounts`, `invoices`, `leases` |
| `reject_request(request_id, rejected_by, reason)` | Rejects a pending payment request. Nothing is paid, and agents can't request that bill again | `approval_requests` |
| `decide_draft(draft_id, approve, decided_by)` | Approves or rejects a draft on the board. Approving doesn't send anything | `board_drafts` |
| `reset_shop(confirm, requested_by)` | Copies the original database over the working copy. Needs `confirm=true` and a human name | `campus_customs.db` (read), `campus_customs_new.db` (replaced) |

## Who can call what

The backend gives each agent only the tools its job needs (`AGENT_TOOLS` in `backend/team.py`). The four human-only tools are filtered out of every agent's toolset (`HUMAN_ONLY_TOOLS`). The backend calls them only when a human acts on the dashboard, or, for `reset_shop`, when a human starts a full run.

| Agent | Tools |
|---|---|
| Boss | `get_ticket`, `list_tickets`, `list_pending_requests`, `list_payments`, `update_ticket`, `get_bills_and_cash`, `check_stock`, `get_vendor_status` |
| Inventory | `get_ticket`, `check_stock`, `get_vendor_status`, `list_tickets`, `list_pending_requests`, `reserve_stock` |
| Accounting | `get_ticket`, `get_bills_and_cash`, `list_pending_requests`, `list_payments`, `request_payment`, `post_draft`, `quote_price`, `get_vendor_status`, `check_stock` |
| Facilities | `get_ticket`, `get_bills_and_cash`, `list_pending_requests`, `list_payments`, `list_tickets` |
| Customer Service | `get_ticket`, `post_draft`, `list_tickets`, `list_pending_requests`, `check_stock` |

## Safety

### Guardrails for real customers and real money
- **Only a human moves money.** `pay`, `reject_request`, `decide_draft`, and `reset_shop` are hidden from agents, and each one refuses a blank name or an agent's name.
- **Amounts and payees come from the database.** `request_payment` takes only a bill id, so an agent can't change how much is paid or who gets paid.
- **No negative balances.** Cash is checked against all pending requests when a payment is requested, and checked again when it is paid.
- **No double payments.** A bill can't be requested twice while pending, and a paid invoice can't be paid again.
- **A human "no" is final.** A rejected bill can't be re-requested by an agent.
- **Atomic payments.** `pay` writes the payment, the cash balance, and the invoice or lease in one transaction, so a failure leaves nothing half done.
- **Nothing leaves the shop.** No tool sends email, texts, or orders. Drafts stay on the board, and approving a draft doesn't send it.
- **Never sell below cost.** `quote_price` refuses any price at or below unit cost, and `post_draft` refuses customer messages with any price that isn't a saved quote (so a made-up price, another product's price, or the shop's internal cost can't reach a customer).
- **Right product, right name.** `post_draft` refuses a customer message that misnames the ticket's product, names a different product, or shows an internal SKU code.
- **No overselling.** Stock can't be reserved past zero.
- **No invented data.** Missing records return errors, not guesses.
- **Recoverable.** The original database is never written, so `reset_shop` can always restore it.
- **Audited.** The backend appends every agent step and tool call to `output/audit_trail.json`, and never wipes it.

### Limits that keep token use in check
These limits are enforced by the backend that calls this server (see `backend/team.py`):
- One model for every agent: `gpt-6-luna` through Portkey.
- Per ticket, across all agents combined: 40 model requests, 60 tool calls, 300,000 tokens, and 8 delegations.
- Delegation chains stop after 3 hand-offs, with no self-delegation and no A → B → A loops.
- Each model call times out after 120 seconds and is retried at most twice.
- Tool results are compact JSON. Agents are told to call each read tool once and reuse the answer.

## Run

```bash
pip install -r requirements.txt
python mcp_server/server.py
```

To use it from Claude Code, the project's `.mcp.json` registers it as `campus-customs`.
