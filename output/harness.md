# Campus Customs Agent Harness

This is the working reference for the Campus Customs agent team. It grows with each problem.

## Contents
1. **Database**: the 9 shop tables and why each matters to the agents, plus the 4 board tables the MCP server adds
2. **MCP Tools**: all 16 tools, the tables each one uses, who may call it, and the ticket it unlocks
3. **Agent Team**: the five agents, their files and tools, and full-connectivity delegation
4. **Audit Trail**: what every agent-loop step records in `output/audit_trail.json`
5. **Safety**: guardrails for real customers and real money, plus the limits that keep token use in check
6. **Runs**: the plan-vs-actual runs from Problems 5–6
7. **Backend Routes**: the FastAPI routes, one line each, and how to start the server
8. **Agent Dashboard**: the React desk
9. **Problem 9: Resolved Tickets**: the clean full run, the human approvals, and the cash ledger

## Database

- Original (never modified): `data/campus_customs.db`
- Working copy (the MCP server and backend use this): `data/campus_customs_new.db`
- Before every full ticket run, reset the working copy by copying the original over it.

### Tables

**desk** (`date_today`, `notes`)
Holds the shop's "today" (2026-08-31). Every agent uses this date, not the real clock, to decide what is overdue or coming due.

**tickets** (`id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`)
The work queue on the board. Boss reads each ticket and routes it. The `sku`, `lease_id` and `invoice_id` fields link the ticket to the records the other agents need.

**inventory** (`sku`, `name`, `size`, `qty`, `location`)
Stock on hand by SKU and size. Inventory checks it to fill orders and to find shortfalls that need a restock.

**pricing** (`sku`, `unit_cost`, `list_price`)
Cost and list price per SKU. Accounting uses it to check margins and to decide how far a discount can go. Inventory uses it to price purchase orders.

**vendors** (`id`, `name`, `specialty`, `lead_days`)
Who can restock what, and how long delivery takes. Inventory picks a vendor and estimates arrival from `lead_days`.

**invoices** (`id`, `vendor_id`, `amount`, `due_date`, `status`, `description`)
Bills the shop owes vendors. An open invoice blocks that vendor from shipping. Accounting flags overdue invoices and prepares them for payment.

**leases** (`id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`)
The shop's space and its rent. Facilities tracks when rent is due and passes the payment request to Accounting.

**cash_accounts** (`name`, `balance`, `date`)
Cash available to spend. The pay tool checks this first and refuses any payment that would make the balance negative. No revenue is modeled, so cash only goes out.

**payments** (`id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`)
The record of every payment. Each row is written only after a human approves, and `approved_by` records who did.

## MCP Tools

The server is `mcp_server/server.py` (FastMCP). Every shop fact the agents and the backend use comes through it, from `data/campus_customs_new.db`. The backend has no other route to the data: it has no database code of its own and calls MCP tools for everything, including the reset and the end-of-run snapshot. The original `data/campus_customs.db` is only ever read, by `reset_shop`.

### All 16 tools at a glance

| # | Tool | Tables it uses | Who can call it | Tickets |
|---|---|---|---|---|
| 1 | `check_stock` | reads `inventory`, `pricing`, `stock_reservations` | Boss, Inventory, Accounting, Customer Service | 101, 103 |
| 2 | `get_vendor_status` | reads `vendors`, `invoices`, `desk` | Boss, Inventory, Accounting | 101, 103 |
| 3 | `get_bills_and_cash` | reads `leases`, `invoices`, `vendors`, `cash_accounts`, `desk` | Boss, Accounting, Facilities | 101, 102 |
| 4 | `list_tickets` | reads `tickets` | Boss, Inventory, Facilities, Customer Service | all |
| 5 | `get_ticket` | reads `tickets` | all five agents | all |
| 6 | `list_pending_requests` | reads `approval_requests`, `board_drafts`, `price_quotes`, `cash_accounts` | all five agents | 101, 102 |
| 7 | `list_payments` | reads `payments`, `approval_requests` | Boss, Accounting, Facilities | 101, 102 |
| 8 | `update_ticket` | writes `tickets` | the backend (records Boss's final call in code; no agent calls it) | all |
| 9 | `request_payment` | reads `invoices`, `leases`, `vendors`, `cash_accounts`; writes `approval_requests` | Accounting | 101, 102 |
| 10 | `post_draft` | writes `board_drafts`; reads `price_quotes`, `pricing`, `leases`, `inventory` for the price and product-name checks | Accounting (purchase orders), Customer Service (messages) | 101, 103 |
| 11a | `quote_price` | reads `pricing`, `tickets`; writes `price_quotes` | Accounting | 103 |
| 11 | `reserve_stock` | writes `inventory`, `stock_reservations` | Inventory | 103 |
| 12 | `pay` | writes `payments`, `cash_accounts`, `invoices`, `leases`, `approval_requests` | **human only** | 101, 102 |
| 13 | `reject_request` | writes `approval_requests` | **human only** | 101, 102 |
| 14 | `decide_draft` | writes `board_drafts` | **human only** | 101, 103 |
| 15 | `reset_shop` | copies `campus_customs.db` over `campus_customs_new.db` | **human only** | all |

### Read tools

**1. `check_stock(sku, size=None)`**
- **Reads:** `inventory`, `pricing`, `stock_reservations`
- **Unlocks:** 101 and 103
- **Why it fits:**
  - Ticket 101 asks for one CC-TEE-WHITE in size S. This tool returns qty 0, so the agents know the order can't be filled from the shelf and has to go to restock.
  - Ticket 103 asks for 20 CC-HOOD-NAVY in size M. This tool returns 8 on hand, a 12-unit shortfall. It also returns the $22 cost against the $58 list price ($36 margin per unit), which is the room Accounting has to approve or limit the bulk discount.

**2. `get_vendor_status(vendor_id=None)`**
- **Reads:** `vendors`, `invoices`, `desk`
- **Unlocks:** 101 (and the 12-hoodie shortfall in 103)
- **Why it fits:** Restocking the size S tee for ticket 101 depends on Bulldog Print Co (apparel reprint, 5-day lead time). This tool shows the vendor has invoice #501 ($840) open and 3 days overdue against desk date 2026-08-31, so `can_ship` is false. That tells the agents #501 has to be paid before the tee can be reordered, with arrival about 5 days after that.

**3. `get_bills_and_cash()`**
- **Reads:** `leases`, `invoices`, `vendors`, `cash_accounts`, `desk`
- **Unlocks:** 102 (and the payment side of 101)
- **Why it fits:** Ticket 102 is the landlord's notice that rent is due. This tool shows the Chapel Street rent ($2,400, due 2026-09-02, 2 days out) next to the overdue invoice #501 ($840) and the $3,400 in checking. Accounting can see that both fit (leaving $160) before asking a human to approve either payment, and it works the same way for any future lease or invoice.

**4. `list_tickets(status=None)`**
- **Reads:** `tickets`
- **Unlocks:** 101, 102, 103 together
- **Why it fits:** Boss has to see the whole board to notice that tickets 101 and 102 draw on the same $3,400. Paying invoice #501 for ticket 101 and rent for ticket 102 leaves only $160 for anything ticket 103 needs.

**5. `get_ticket(ticket_id)`**
- **Reads:** `tickets`
- **Unlocks:** 101, 102, 103
- **Why it fits:** After Boss's run, the backend calls `get_ticket` to check whether Boss already recorded its decision. In the latest run Boss hadn't recorded any of the three, so the backend wrote each status (for example, 103 → `needs_info`) through `update_ticket`. Agents use it to re-read one ticket's status and notes, for example to confirm ticket 101 is still awaiting approval, without listing the whole board.

**6. `list_pending_requests()`**
- **Reads:** `approval_requests`, `board_drafts`, `cash_accounts`
- **Unlocks:** 101 and 102
- **Why it fits:** Invoice #501 is involved in ticket 101 (it blocks the tee restock) and is also a bill Accounting would pay. This tool shows whether #501 is already pending, so it is never requested twice, and how much cash is left once pending payments are counted.

**7. `list_payments()`**
- **Reads:** `payments`, `approval_requests` (decided ones)
- **Unlocks:** 101 and 102, after the human acts
- **Why it fits:** Once a human approves rent for ticket 102 or invoice #501 for ticket 101, Facilities and Accounting use it to confirm the payment row exists and who approved it. If a human rejects #501, it shows the rejection, so no agent asks for it again (`request_payment` also refuses).

### Board tools

These tools let the team act on the board. Three board tables, `approval_requests`, `board_drafts`, and `stock_reservations`, are created in the working copy only. A reset from the original wipes them and restores the stock counts.

**8. `update_ticket(ticket_id, status, note, updated_by)`**
- **Writes:** `tickets.status`, `tickets.notes`
- **Unlocks:** 101, 102, 103
- **Why it fits:** Boss's final call has to show on the board. For example, ticket 101 is "blocked until invoice #501 is paid", and ticket 102 is "awaiting approval of $2,400 rent". The human can then see each ticket's state without reading the agent chat.

**9. `request_payment(ticket_id, kind, ref_id, reason, requested_by)`**
- **Reads:** `invoices` or `leases`, plus `cash_accounts`. **Writes:** `approval_requests`
- **Unlocks:** 102 (rent for lease 1) and 101 (invoice #501)
- **Why it fits:** Ticket 102 needs the $2,400 rent paid by 2026-09-02, and ticket 101's restock is blocked until the $840 invoice #501 is paid. This tool queues each payment for human approval with the amount taken from the database. It pays nothing, and it refuses a duplicate or any request that cash minus pending payments can't cover.

**10. `post_draft(ticket_id, kind, recipient, subject, body, created_by)`**
- **Writes:** `board_drafts`
- **Unlocks:** 101 and 103
- **Why it fits:**
  - Tauhid Zaman (ticket 101) needs a reply explaining that size S is out of stock and when it can arrive.
  - The Yale AI Club (ticket 103) needs a reply with the hoodie offer.
  - The 12-hoodie shortfall needs a purchase order.
  - The shop must not email customers or contact vendors, so all of these are saved as drafts on the board. Purchase orders wait for approval.

**11a. `quote_price(ticket_id, sku, qty, discount_pct, quoted_by, size)`** (added to lock the price rule in code)
- **Reads:** `pricing`, `tickets`. **Writes:** `price_quotes`
- **Unlocks:** 103
- **Why it fits:** The Yale AI Club wants a bulk discount on CC-HOOD-NAVY ($22 cost, $58 list). Accounting saves each option here, and the code does the math: 10% off = $52.20, 20% off = $46.40. It refuses 62.07% or more (at or below $22). The customer message for ticket 103 can then only use those saved prices, because `post_draft` checks every dollar amount.

**11. `reserve_stock(ticket_id, sku, size, qty, reserved_by)`**
- **Reads:** `inventory`, `tickets`. **Writes:** `inventory.qty`, `stock_reservations`
- **Unlocks:** 103 (and 101 once the tee is restocked)
- **Why it fits:** Ticket 103 wants 20 CC-HOOD-NAVY in size M and only 8 are on the shelf. Once Boss decides to send the 8 now, this tool takes them off the count and logs them against ticket 103, so no other ticket can promise the same hoodies. It refuses to reserve 20 (more than on hand), refuses the tee in size S at 0 on hand, and refuses a second reservation for the same ticket.

### Human-only tools

These four tools are hidden from every agent (`HUMAN_ONLY_TOOLS` in `backend/team.py`). Each one also refuses if the human name is blank or is an agent's name.

**12. `pay(request_id, approved_by)`**
- **Reads/writes:** `approval_requests`, `payments`, `cash_accounts`, `invoices`, `leases`
- **Unlocks:** 101 and 102, once the human approves
- **Why it fits:**
  - Paying invoice #501 marks it paid, which lets Bulldog Print Co ship the tee for ticket 101.
  - Paying rent moves lease 1's due date to 2026-10-02, which resolves ticket 102.
- **Safeguards:**
  - It refuses without a human approver, if the approver is an agent, or if the balance would go negative.
  - It is filtered out of every agent's toolset; only the dashboard's Approve button triggers it.

**13. `reject_request(request_id, rejected_by, reason)`**
- **Writes:** `approval_requests` (status `rejected`, who, why)
- **Unlocks:** 101 and 102, when a human says no
- **Why it fits:** If the human won't pay invoice #501 (for example, it's disputed), rejecting it records the decision, nothing is paid, and `request_payment` then refuses to queue #501 again, so ticket 101 is escalated to Boss instead of looping.

**14. `decide_draft(draft_id, approve, decided_by)`**
- **Writes:** `board_drafts` (status `approved` or `rejected`)
- **Unlocks:** 101 and 103
- **Why it fits:** The tee purchase order for ticket 101 and the replies to Tauhid Zaman and the Yale AI Club wait on the board until a human approves them. Approving only marks them approved; nothing is sent. A human sends them outside the system.

**15. `reset_shop(confirm, requested_by)`**
- **Reads:** `campus_customs.db` (original). **Writes:** replaces `campus_customs_new.db`
- **Unlocks:** every ticket, before a full run
- **Why it fits:** The rules require a reset to the original values before every full run. `run_team` calls this first, so tickets 101–103 start open with $3,400 in cash and nothing pending. It needs `confirm=true` and a human name, and the original file is never written.

## Agent Team

Built with Pydantic AI in `backend/`. Every agent runs on `gpt-6-luna` through Portkey (`backend/config.py`), reads its prompt from `backend/prompts/<agent>.md`, and returns a typed result from `backend/models.py`. Every agent's loop runs through `run_agent` in `backend/team.py`, which writes the audit trail.

**Full connectivity.** Every agent has an `ask_teammate` tool and can delegate to any other agent, with the guardrails in the Safety section.

| Agent | File | Job | MCP tools |
|---|---|---|---|
| Boss | `agents/boss.py`, `prompts/boss.md` | Reads each ticket, routes it, and makes the final call. The backend records the call on the board | `get_ticket`, `list_tickets`, `list_pending_requests`, `list_payments`, `get_bills_and_cash`, `check_stock`, `get_vendor_status` |
| Inventory | `agents/inventory.py`, `prompts/inventory.md` | Stock by SKU and size, shortfalls, restock vendor and lead time; reserves stock after Boss's call | `get_ticket`, `check_stock`, `get_vendor_status`, `list_tickets`, `list_pending_requests`, `reserve_stock` |
| Accounting | `agents/accounting.py`, `prompts/accounting.md` | Cash, bills, margins; queues payment requests, prices offers, and posts purchase orders for approval | `get_ticket`, `get_bills_and_cash`, `list_pending_requests`, `list_payments`, `request_payment`, `post_draft`, `quote_price`, `get_vendor_status`, `check_stock` |
| Facilities | `agents/facilities.py`, `prompts/facilities.md` | Leases and rent; checks each notice against the lease before rent goes to Accounting | `get_ticket`, `get_bills_and_cash`, `list_pending_requests`, `list_payments`, `list_tickets` |
| Customer Service | `agents/customer_service.py`, `prompts/customer_service.md` | Drafts customer messages on the board; never sends, never shares internal finances | `get_ticket`, `post_draft`, `list_tickets`, `list_pending_requests`, `check_stock` |

All five also have `ask_teammate`. None has `pay`, `reject_request`, `decide_draft`, or `reset_shop`, and none has `update_ticket` (Boss lost it after three runs hung right after calling it; the backend now records every final call).

Each prompt has the same sections: role, in scope, not in scope, tools, step-by-step workflow, shop rules, after the human decides, escalation, when to ask a teammate, report format, and keeping it lean.

## Audit Trail

Every agent-loop step is appended to `output/audit_trail.json` as it happens (`backend/audit.py`). The file is one JSON array that only grows: runs are never wiped, and each run has its own `run_id`. Every entry has `at` (timestamp), `run_id`, `step`, `ticket_id`, `agent`, `chain` (who delegated to whom), `event`, and `details`.

| Event | What is recorded |
|---|---|
| `reset_shop`, `run_started`, `run_finished` | Who reset the shop, the model, and the open tickets |
| `ticket_started` | The ticket Boss picked up |
| `agent_start` | The exact prompt an agent received |
| `model_response` | The model name actually used, input and output tokens, any text, and each tool call with its arguments |
| `tool_result` / `tool_retry` | The tool's output (clipped at 4,000 characters), or the error that made the model retry |
| `delegation` / `reply` / `delegation_refused` | Who asked whom, what they asked, the answer, or why it was refused |
| `agent_output` | The agent's full structured report, and its request and token totals |
| `board_update_by_backend` | When the backend recorded Boss's status because Boss didn't |
| `ticket_decision` | Boss's final decision |
| `error` | A usage limit or model error that stopped a ticket |

With this an auditor can answer: which model ran (every `model_response` shows `gpt-6-luna-global`), who requested each payment and why, what each agent saw before it acted, and how many tokens each ticket cost.

## Safety

### Guardrails for real customers and real money

**Money**
- **No agent can move money.** `pay` is hidden from every agent and refuses an agent's name as approver. A payment needs a human click on the dashboard.
- **Amounts come from the database, not the agent.** `request_payment` takes a bill id and looks up the amount and payee itself, so an agent can't inflate or redirect a payment.
- **No negative balances.** `request_payment` refuses if cash minus all pending requests can't cover the bill, and `pay` checks again at the moment of payment.
- **No double payments.** A bill can't be requested twice while pending, and `pay` refuses an invoice that is already paid.
- **A human "no" sticks.** After a rejection, agents can't re-request the same bill; they have to escalate.
- **All-or-nothing writes.** `pay` updates `payments`, `cash_accounts`, and the invoice or lease in one transaction, so a failure leaves nothing half done.
- **Check payees against the record.** Facilities compares every rent notice with the lease and refuses to pass on a different payee, amount, or bank account (it was tested with a fake notice).

**Customers and outside parties**
- **Nothing leaves the shop.** No tool can email, text, or call. Customer messages and purchase orders are drafts on the board, and approving one doesn't send it.
- **No internal data in customer messages.** Customer Service never mentions cash, invoices, vendors, costs, margins, or SKU codes.
- **No promises that depend on pending money.** Dates and full quantities are only promised once the payment that unblocks them is approved.
- **Never sell below cost (enforced in code).** `quote_price` refuses any price at or below unit cost. `post_draft` refuses a customer message containing any dollar amount that isn't a saved quote, list price, or lease rent for that ticket, so a made-up discount, another product's price, or the shop's $22 cost can't reach a customer. Before this lock, the rule was only in the prompts.
- **Right product, right name (enforced in code).** `post_draft` refuses a customer message that doesn't use the ticket's exact catalog name (for example, “Basic Hoodie Big Yale”, not “Classic Navy Hoodies”), names another product, or shows a SKU code. This was added after the final run's draft misnamed the hoodies.
- **No overselling.** `reserve_stock` refuses more than is on hand, so two tickets can't promise the same units.
- **No made-up facts.** Tools return an error instead of a guess, and prompts tell agents to say what's missing.

**Accountability**
- **Least privilege.** Each agent sees only the tools its job needs (`AGENT_TOOLS` in `backend/team.py`).
- **One data path.** All reads and writes go through the MCP server. The backend has no database code of its own.
- **Recoverable.** `reset_shop` restores the original data, and the original file is never written.
- **Full audit trail.** Every step, tool call, and decision is logged with who, what, and when, and the log is never wiped.

### Limits that keep token use in check

| Limit | Value | Where |
|---|---|---|
| One model for every agent | `gpt-6-luna` (a fixed constant, no fallback) | `backend/config.py` |
| Model requests per ticket (all agents combined) | 40 | `TICKET_USAGE_LIMITS` |
| Tool calls per ticket | 60 | `TICKET_USAGE_LIMITS` |
| Tokens per ticket | 300,000 | `TICKET_USAGE_LIMITS` |
| Delegations per ticket | 8 | `MAX_DELEGATIONS_PER_TICKET` |
| Delegation chain depth | 3 hand-offs | `MAX_DELEGATION_DEPTH` |
| No self-delegation and no A → B → A loops | refused with a message | `ask_teammate` |
| Tool output in the audit log | clipped at 4,000 characters | `backend/audit.py` |
| Model call timeout | 120 seconds, then up to 2 retries (a hung call can't stall a ticket) | `MODEL_TIMEOUT_SECONDS`, `MODEL_MAX_RETRIES` in `backend/config.py` |
| Prompts | "ask once, with a specific question"; Customer Service writes once the plan is settled | `backend/prompts/*.md` |

Nested agents share one usage counter, so the limits cover the whole team on a ticket, not each agent separately. If a ticket hits a limit, it stops with an `error` entry in the audit trail and the run moves on to the next ticket.

## Full team run (`python -m backend.run_team`)

`reset_shop` runs first. Boss then works each open ticket in order. The summary is saved to `output/team_run.json`, and every step is appended to `output/audit_trail.json`.

Latest run (`20261011-214812-497a02`, 166 audit entries, only `gpt-6-luna-global` in every model response). `output/desk_tickets.html` compares it step by step with the plan in `output/ticket_plan.md`.

| Ticket | Boss called first | Specialists | Delegations (plan → actual) | Tokens | Board status | Outcome |
|---|---|---|---|---|---|---|
| 101 Bulldog tee | Inventory ✓ | 3 of 4 | 3 → 3 | 96k | awaiting_approval | Tee size S at 0. Invoice #501 requested (#1, $840), and the $8 PO drafted. Accounting also queued the rent here (#2), ahead of ticket 102. The customer draft gives no date. |
| 102 Rent due | Facilities ✓ | 2 of 4 | 2 → 2 (Boss sent both directly) | 30k | awaiting_approval | The notice matches lease 1. Rent was already pending as #2, so no duplicate. $160 left after pending. |
| 103 Bulk hoodies | Inventory ✓ | 3 of 4 | 4 → 5 | 80k | blocked (plan: needs_info) | 8 reserved and offered at $52.20 (10% off, above the $22 cost). No second #501 request, and no PO for the 12 ($264 against $160). |

After the run: 0 payments, cash still $3,400, 2 pending requests ($3,240), 3 drafts, 8 hoodies reserved, and nothing sent. Delegations fell from 14 to 10 and tokens from 235k to 206k after the Boss prompt change.

### After tightening the prompts (run `20261011-220409-cddb6d`)

The prompts were changed in Problem 6 to fix gaps the run above exposed. Accounting now stays on its own ticket, rent notices go to Facilities first, dependent questions are asked in order, and Boss uses clearer status rules. The same reset start then gave:

| Ticket | Delegations (plan / before / after) | Status (plan / after) | Tokens before → after | What changed |
|---|---|---|---|---|
| 101 | 3 / 3 / 3 | awaiting_approval / **needs_info** | 96k → 74k | Rent is no longer requested here. The status overcorrected, because Customer Service asked the customer a question. |
| 102 | 2 / 2 / 2 | awaiting_approval / awaiting_approval | 30k → 39k | Exactly the planned path: Boss → Facilities → Accounting. Rent is requested on this ticket. |
| 103 | 4 / 5 / **4** | needs_info / needs_info | 80k → 75k | Delegations match the plan exactly, and the status is fixed. The offer was 20% off this time (still above cost). |

Total: 9 delegations (the plan's 9), 187k tokens (down from 206k), 0 payments, cash still $3,400. Boss still doesn't call `update_ticket` itself; the backend records the status every time.

Follow-up check (run `20261011-220946-3596ba-t101`, ticket 101 only): after adding "Approval comes first" to Boss's prompt, ticket 101 is `awaiting_approval` again, matching the plan, with 3 delegations and only invoice #501 requested.


### Final full run (`20261013-095927-762bb6`)

This run has every fix in place: the tightened prompts, "approval comes first", the price lock (`quote_price` plus the price check in `post_draft`), a 120s model timeout, and fresh model calls (the Portkey cache is skipped, and each run's prompts carry its run id). Two earlier attempts that day are in the audit trail as `run_aborted` and `run_note`: a cached model call hung, which is how the cache problem was found.

| Ticket | First call | Delegations (plan → actual) | Status (plan → actual) | Tokens |
|---|---|---|---|---|
| 101 | Inventory ✓ | 3 → 3 ✓ | awaiting_approval → awaiting_approval ✓ | 72k |
| 102 | Facilities ✓ | 2 → 2 ✓ (Boss → Facilities → Accounting) | awaiting_approval → awaiting_approval ✓ | 45k |
| 103 | Inventory ✓ | 4 → 4 ✓ | needs_info → **awaiting_approval** | 84k |

Total: 9 delegations (the plan's 9), 201k tokens, 0 payments, cash $3,400, 2 pending requests ($3,240), quotes #1 $52.20 and #2 $46.40 (both above the $22 cost), and 8 hoodies reserved. Ticket 103 still differs: its status is "awaiting approval", Boss offered both quotes instead of picking one, and the customer draft misnames the product.


After the final run, the product-name check was added to `post_draft`. In a Customer Service-only test (run `…-cs-namecheck`), the ticket 103 offer used “Basic Hoodie Big Yale” and passed on the first try.

## Backend Routes (`backend/main.py`, FastAPI)

**Start the server from the `backend/` folder:**

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

This turns on the backend at **http://localhost:8000**, so the React dashboard can call these routes. The backend allows the Vite page origin (`http://localhost:5173` and `http://127.0.0.1:5173`) through CORS, so the browser is allowed to call the routes, and other origins are refused. Interactive docs are at http://localhost:8000/docs. Every shop fact goes through the MCP server, and every human action is appended to `output/audit_trail.json`.

**Routes (one line each)**
- `GET  http://localhost:8000/tickets`: returns the three tickets and whether each is open or resolved.
- `POST http://localhost:8000/tickets/{ticket_id}/run`: runs the agent team on that ticket (Boss decides who to call) in the background and returns a `run_id`.
- `GET  http://localhost:8000/tickets/{ticket_id}/summary`: returns what each agent did on that ticket in its latest run since the last reset (a short memo, the tools it used, who it asked) and Boss's decision.
- `GET  http://localhost:8000/runs/{run_id}`: shows whether that run is queued, running, finished, or failed, and Boss's final decision.
- `GET  http://localhost:8000/events?after={seq}`: returns recent agent events (what each agent said and which tools it used), so the board can refresh.
- `GET  http://localhost:8000/approvals`: lists the payments and purchase orders waiting for a human to approve.
- `POST http://localhost:8000/approvals/approve`: a human approves a payment or purchase order. Agents only prepare a payment; this route is what actually changes cash, through the `pay` tool.
- `POST http://localhost:8000/approvals/reject`: a human rejects a payment or purchase order (agents can't re-request a rejected bill).
- `GET  http://localhost:8000/cash`: returns the current checking balance from `cash_accounts`, plus pending payments.
- `POST http://localhost:8000/reset`: resets the database to the original values, so you can try a fresh run.
- `GET  http://localhost:8000/health`: confirms the server is up and shows the model (`gpt-6-luna`).

**Guardrails in the routes**
- Only one ticket runs at a time, because all tickets share one bank account. A second run, or a reset during a run, gets `409`.
- Approve, reject, and reset need a human name. An agent's name or a blank name gets `400`.
- A purchase-order approval must point at a purchase order, not a customer message.
- MCP refusals (not enough cash, already paid, rejected bill) come back as HTTP errors with the reason.

**Tested against a live server:**
- `/reset` refused "boss" and accepted "Olivia".
- `/tickets` showed 3 open tickets, and `/cash` showed $3,400.
- `POST /tickets/102/run` ran Boss → Facilities → Accounting, and rent was queued as request #1. A second run during it got `409`.
- `/events` showed every step, and `after=` returned 0 new events once caught up.
- Approving as "accounting" got `400`. Approving as Olivia paid $2,400: cash went to $1,000, the payment row was recorded with `approved_by = Olivia`, and lease 1 is now next due 2026-10-02. Approving again was refused.
- A purchase-order approval didn't move cash, and approving a customer message as a PO got `400`.
- `/reset` brought cash back to $3,400.


## Agent Dashboard (`frontend/`, React + Vite + TypeScript)

Start it with `cd frontend && npm run dev`. This opens the desk at http://localhost:5173 in the browser, and the page calls the backend at http://localhost:8000. Design choices are in `output/design.md`.

Tested end to end in the browser:
- Signed in as Olivia and convened the team on ticket 101.
- The Bench showed Boss "waiting on Inventory", then Inventory at work, then Accounting "filing a payment request", then Customer Service "drafting correspondence", with the transcript filling in live.
- The run finished in about 85 s, and ticket 101's folder flipped to **RESOLVED**, with "Awaiting your signature" underneath.
- Signing the $840 payment stamped it APPROVED, and the balance counted down from $3,400.00 to $2,560.00. The ledger showed "Invoice #501, signed by Olivia".

Fix found while testing: three runs had hung right after Boss called `update_ticket` itself. `update_ticket` was removed from Boss's tools, and the backend now records Boss's final call on the board in code every time.


## Problem 9: Resolved Tickets

**Clean start.** The working database was reset through `POST /reset` (MCP `reset_shop`). Starting checking balance: **$3,400.00** (`cash_accounts`).

**Runs** (all appended to `output/audit_trail.json`, and every model call is `gpt-6-luna-global`):

| Ticket | First run | Delegations | Status after the run | Follow-up after approvals | Final status |
|---|---|---|---|---|---|
| 101 | `20261013-154100-ab970a-api-t101` | Boss → Inventory, Boss → Accounting, Accounting → Inventory, Boss → Customer Service | awaiting_approval | `20261013-165653-7a6514-api-t101` | needs_info (#501 paid; waiting on Tauhid's go-ahead) |
| 102 | `20261013-154247-723c89-api-t102` | Boss → Facilities, Facilities → Accounting | awaiting_approval | `20261013-165804-7f5edb-api-t102` | **resolved** (rent paid; next due 2026-10-02) |
| 103 | `20261013-154323-2e4168-api-t103` | Boss → Inventory, Boss → Accounting, Boss → Inventory (reserve), Boss → Customer Service | awaiting_approval | `20261013-165830-a271bb-api-t103` | awaiting_approval (PO #5 for 12 hoodies, $264, advised against) |

All three show **RESOLVED** on the board: the team finished and made its call.

**Human approvals.** Olivia signed in the React desk as "Olivia Obodoagha":

| Time | Item | Ticket | Amount | Checking after |
|---|---|---|---|---|
| 16:55:54 | Pay invoice #501 to Bulldog Print Co | 101 | −$840.00 | $2,560.00 |
| 16:56:00 | Approve purchase order #1 (1 tee, $8; nothing sent) | 101 | $0.00 | $2,560.00 |
| 16:56:06 | Pay rent, lease 1, to Elm City Properties | 102 | −$2,400.00 | $160.00 |

**Ending checking balance: $160.00.** $3,400.00 − $840.00 − $2,400.00 = $160.00, which matches `cash_accounts.balance` in `data/campus_customs_new.db`. Both rows in `payments` have `approved_by = Olivia Obodoagha`. The balance never went below zero.

**Deliverables**
- `output/desk_tickets.html`: each ticket tab now has the Problem 9 **Actual** (agents, delegations, MCP tools, writes, approvals, follow-up) next to the **Expected** plan. Earlier test runs are folded underneath. The **Cash** tab itemizes the money from reset to the ending balance.
- `output/resolved_tickets.json`: for each ticket, the id, final status, short outcome, what each agent contributed (tools, delegations, memo) for both runs, human approvals, and the cash change. It also has the starting and ending balances, with a check that the ending balance matches `cash_accounts`.
- `output/resolved_board.html`: a double-clickable page with a screenshot of the React desk for each resolved ticket (`output/screens/board_101.png`, `board_102.png`, `board_103.png`, captured with headless Chrome at 1440 px using the desk's `?ticket=` link).
