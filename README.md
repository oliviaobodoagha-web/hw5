# Campus Customs: Multi-Agent Operations

An agent team that runs a small campus apparel shop. Tickets land on a board (a customer order, a rent notice, a bulk-discount request), and five agents work them together:
- **Boss** routes each ticket and makes the final call.
- **Inventory** handles stock and restocks.
- **Accounting** handles cash, invoices and pricing.
- **Facilities** handles the lease and rent.
- **Customer Service** drafts replies.

Any agent can delegate to any other. A human watches on a React dashboard and signs off on anything that moves money.

- **MCP server** (`mcp_server/`): FastMCP. It's the only way anything reads or changes the shop database. 16 tools.
- **Backend** (`backend/`): FastAPI plus the Pydantic AI agent team. Every agent uses **gpt-6-luna through Portkey**.
- **Dashboard** (`frontend/`): React, Vite and TypeScript. It's "the desk" where you pick a ticket, watch the agents, and sign payments.

Shop rules the code enforces:
- "Today" is `desk.date_today` (2026-08-31).
- A vendor with an open invoice won't ship.
- Every payment needs a human signature, and payments never take the balance below zero.
- No revenue is modeled, so cash only goes out.
- Nothing is emailed or sent; drafts stay on the board.

## What you need

- Python 3.11+ and Node 18+
- A Portkey API key with access to `gpt-6-luna`

## One-time setup

```bash
git clone <this repo>
cd hw5

# Python (MCP server + backend)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Your key: copy the example and paste your own PORTKEY_API_KEY
cp .env.example .env

# Dashboard
cd frontend && npm install && cd ..
```

The real `.env` is never committed. `.env.example` shows the one variable the app needs.

## The databases (`data/`)

| File | What it is |
|---|---|
| `data/campus_customs.db` | **The original shop.** It's never written to. |
| `data/campus_customs_new.db` | **The working copy.** The MCP server reads and writes only this file. As committed, it holds the end of my Problem 9 run (checking $160). |

### Copy the original to the working copy for a clean run

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

That puts the shop back to its starting state: 3 open tickets, $3,400 in checking, nothing pending. The board tables the MCP server adds (approvals, drafts, reservations, quotes) are recreated empty the next time it runs. Once the backend is running, the same reset is also available as `POST /reset`, or **Reset the books** on the dashboard.

## Run it

Use three terminals, all from the repo folder with `.venv` active.

### 1. Start the MCP server

The backend starts the MCP server itself: each agent connects to `mcp_server/server.py` over stdio, so steps 2 and 3 are all you need to use the app. To start the server on its own (to test its tools, or to use it from an MCP client such as Claude Code, which reads `.mcp.json`):

```bash
python mcp_server/server.py
```

### 2. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The backend runs at **http://localhost:8000**, and interactive docs are at http://localhost:8000/docs. It allows the dashboard's origin (`http://localhost:5173`) through CORS.

| Route | What it does |
|---|---|
| `GET /tickets` | The tickets, each open or resolved |
| `POST /tickets/{id}/run` | Run the agent team on one ticket |
| `GET /runs/{run_id}` | Progress of a run, and Boss's decision |
| `GET /tickets/{id}/summary` | What each agent did on that ticket |
| `GET /events?after=` | Live agent events (who said what, which tools) |
| `GET /approvals` | Payments and purchase orders waiting for a human |
| `POST /approvals/approve` | A human approves. **The only route that moves cash** |
| `POST /approvals/reject` | A human rejects |
| `GET /cash` | Checking balance from `cash_accounts` |
| `POST /reset` | Reset the working database to the original |

### 3. Start the React board

```bash
cd frontend
npm run dev
```

This opens the desk at **http://localhost:5173**. Type your name under **Signing as**, pick a ticket from the Docket, and click **Convene the team**. Watch the Bench and the Proceedings while the team works. When the run finishes, sign any payments under **Awaiting Your Signature**, and the Register's balance drops.

## Before a full three-ticket run: reset

Always start a full run from the original data, or the tickets will see the payments and approvals from the last run. Use one of these:

```bash
# A) by hand
cp data/campus_customs.db data/campus_customs_new.db

# B) through the running backend
curl -X POST http://localhost:8000/reset -H 'content-type: application/json' -d '{"by":"Your Name"}'
```

Or C) click **Reset the books** on the dashboard.

Then run 101, 102 and 103 one at a time from the dashboard (one ticket runs at a time because they share the cash), and sign the payments yourself.

There's also a script that resets the database first and then runs all three tickets back to back from the command line:

```bash
python -m backend.run_team
```

It writes a summary to `output/team_run.json` on your machine (not committed). Payments still wait for a human to approve them on the dashboard.

## What's in `output/`

| File | What it is |
|---|---|
| `harness.md` | The full write-up: tables, all 16 MCP tools, the five agents, the audit trail, safety and token limits, routes, the dashboard, and the Problem 9 results |
| `desk_tickets.html` | Double-click it. One tab per ticket with my **Expected** plan and the **Actual** run, plus the **Cash** ledger and my **Reflection** |
| `resolved_tickets.json` | Per ticket: final status, outcome, what each agent contributed, human approvals, and cash change |
| `resolved_board.html` | Double-click it. Screenshots of the React desk for each resolved ticket, built into the page |
| `audit_trail.json` | Every agent-loop step from every run, append-only |
| `design.md` | Why the dashboard looks and works the way it does |
| `mcp_smoke.json` | The MCP smoke test: my prompts, the tool called, and its output checked against the database |
| `github_url.txt` | This repository's URL |

## Safety, briefly

- **Money:** no agent can pay. `pay` is hidden from every agent and refuses agent names.
- **Amounts:** payment amounts and payees come from the database, never from an agent.
- **No overdrafts or double payments:** cash is checked when a payment is requested and again when it's paid. A rejected bill can't be re-requested.
- **Prices:** `quote_price` refuses anything at or below cost, and customer messages can only use saved quotes and exact catalog product names.
- **Limits:** one model, plus per-ticket limits of 40 requests, 60 tool calls, 300k tokens and 8 delegations, and a 120-second model timeout.

Details are in `output/harness.md` → Safety.

## Layout

```
.
├── README.md
├── requirements.txt
├── .env.example
├── .mcp.json                 # registers the MCP server for Claude Code
├── AI_prompts.md             # the prompts I typed, one section per problem
├── data/
│   ├── campus_customs.db     # original (never written)
│   └── campus_customs_new.db # working copy
├── mcp_server/
│   ├── server.py             # FastMCP: 16 tools
│   └── README.md
├── backend/
│   ├── main.py               # FastAPI routes
│   ├── team.py               # agent wiring, delegation, audited loop, limits
│   ├── config.py             # gpt-6-luna via Portkey
│   ├── models.py             # data types
│   ├── audit.py              # append-only audit trail
│   ├── run_team.py           # reset + run all tickets from the command line
│   ├── agents/               # boss, inventory, accounting, facilities, customer_service
│   └── prompts/              # one prompt file per agent
├── frontend/                 # React + Vite + TypeScript desk
└── output/                   # write-ups, pages, screenshots, audit trail
```
