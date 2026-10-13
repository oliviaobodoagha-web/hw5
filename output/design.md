# The Desk: Design Notes

**Campus Customs & Co., Operations Desk.** This is the React dashboard in `frontend/` (React, Vite, TypeScript), where a person picks a ticket, watches the agent team work it, and signs off on anything that moves money.

## How to open it

```bash
# 1. the backend (from the backend/ folder)
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000

# 2. the desk (from the frontend/ folder, in a second terminal)
cd frontend
npm install        # first time only
npm run dev
```

`npm run dev` serves the desk at **http://localhost:5173** and opens it in the browser. The page calls the backend directly at **http://localhost:8000**. The backend allows that one page origin through CORS (`backend/main.py`), so the browser is allowed to call the routes, and any other site is refused.

## The idea: a law firm's desk with a J.Crew finish

I didn't want it to look like every other AI dashboard: no dark mode with glowing gradients, no chat bubbles, no robot icons. The shop's work is serious: real customers, real rent, real money. So the desk borrows from a law office: matters on a docket, a bench of colleagues, a court-reporter transcript, rulings, memoranda, and a signature line. The J.Crew half keeps it from feeling stuffy: ivory paper, navy ink, generous spacing, small spaced-out capitals, and one deep oxblood red, used only where something matters.

- **Paper:** ivory (`#f3eee4`) with faint laid-paper lines, like letter stock. Manila for the case folders.
- **Ink:** navy-black (`#1c2333`), not pure black.
- **One accent:** oxblood (`#7a1f26`). It appears only on things that need attention: the active matter, an agent at work, a payment amount, a debit, a stamp. If something is red, it matters. No pink anywhere.
- **Type, four voices, each with one job:**
  - *Libre Caslon Display*: headlines and names, like a firm's letterhead.
  - *Libre Caslon Text*: the record (facts, memos, the ruling).
  - *Jost*: small capital labels, the catalog voice.
  - *Courier Prime*: anything an agent "typed" (the live transcript and the drafted letters).

## Layout: three columns, read left to right like a working day

| Column | What's there | Why |
|---|---|---|
| **Left: The Docket** | Each ticket is a manila case folder with a tab ("No. 101"), its type in red small capitals, the subject, who it's from, and a stamp | You choose what to work on first, so the list of matters is the first thing you see, the way files sit on the left of a desk. |
| **Center: The Matter** | The open file. The header shows "Matter No. 101 · Customer Order" and *In re: Bulldog tee*, with the client, what they asked for, any invoice or lease, and the ticket's own note as a pull quote. One button: **Convene the team**. Below it are the Bench, the Proceedings, the Ruling, and the Memoranda | This is where the work happens, so it gets the most room. Everything reads top to bottom in the order it happens: the ask, who's working, what they said, what was decided, who did what. |
| **Right: The Register and Awaiting Your Signature** | The checking balance as a checkbook ledger, and the payments and purchase orders waiting for a human | Money and approvals stay pinned on the right (they stay in view as you scroll), because they're what a person is actually responsible for. You never have to hunt for the balance or for what needs signing. |

On a laptop the right column folds under the center. On a phone everything stacks, and the docket becomes a row of folders you swipe through.

## How the agents read differently

Each agent has a **seat on the Bench**: a row of five places, each with a monogram (B, In, Ac, Fa, CS), a name, and a title written as a firm role:

| Agent | Title on the desk |
|---|---|
| Boss | *Managing Partner* |
| Inventory | *Stock & Supply* |
| Accounting | *Treasury* |
| Facilities | *Premises* |
| Customer Service | *Client Relations* |

Each seat shows its **state** in plain words, updated live while a ticket runs:
- **At rest:** faded and in italics, "Not called on this matter". An agent Boss didn't need stays visibly out of it, which shows the team isn't sending every specialist on every ticket.
- **Called in:** "Called in by Boss".
- **At work:** the seat warms to a pale red, the monogram fills with oxblood and breathes, and the line says what the agent is doing in words, not tool names ("checking the shelf · calling on the vendors").
- **Waiting:** "Waiting on Inventory", when an agent has delegated and is waiting for an answer.
- **Done:** a red check mark, "Reported back" (Boss: "Made the final call").

Every MCP tool has a plain-English phrase: `check_stock` → *checking the shelf*, `get_bills_and_cash` → *reviewing the books*, `quote_price` → *pricing the offer*, `reserve_stock` → *setting stock aside*, and so on. A person watching sees what is happening without reading code.

**The Proceedings** is the live transcript, typed in Courier on a ruled legal pad with a red margin line. Each line has a time, a speaker, and what was said:
- **Delegations** are in red: *BOSS → INVENTORY: "Can we fill 1 CC-TEE-WHITE size S?…"*
- **Replies** are in ink.
- **Tool use** is in grey italics: *checking the shelf; reviewing the books*.
- **The ruling** closes the record under a dashed line.

A blinking red cursor shows the reporter is still typing while the team is in session. A "Show tool returns" switch reveals the raw tool output for anyone who wants to audit.

**Memoranda** appear after the run: one card per agent that worked the matter, headed "From: Accounting · *Treasury*", with that agent's own summary, who it asked, and the tools it used. A line underneath names who was **not** called. Drafted customer letters sit below as typed letters marked **"drafts, not sent"**.

## How resolved tickets show up, and why

- Each folder carries an inked **stamp**, set slightly crooked like a real rubber stamp: **OPEN** in navy, or **RESOLVED** in oxblood. While the team works, the folder reads **IN SESSION** and gently pulses.
- A ticket is marked **resolved** as soon as the run finishes and Boss has made the final call. Resolved doesn't always mean nothing is left to do, so the folder says what's next in italics under the stamp: *Awaiting your signature*, *Awaiting the client*, or *Blocked*. A person can scan the docket and know both what's been handled and what's waiting on *them*.
- **The Ruling** appears under the transcript in a bordered box with a stamp, like a judgment entered on the record: the decision, the reasoning with real numbers, and what's next.
- The docket header keeps count: *"2 open · 1 resolved"*.

## How cash shows up, and why

- **The Register** is written like a checkbook. The balance is big at the top in the display serif, the ledger lists *Opening balance*, then each payment with who signed it, the debit in red, and the running balance, and a double rule closes it with *Pending signature* and the balance after pending.
- **When a payment is signed, the balance visibly counts down** (about a second, easing out), and a red **−$840.00** appears under it. The drop is the moment money leaves, so the desk makes it noticeable instead of silently swapping a number.
- A line of fine print states the rules plainly: *no revenue is booked; cash only goes out; payments never take the balance below zero.*

## Signing, the human's part

- **Awaiting Your Signature** lists every payment and purchase order the agents prepared. Payments show the amount in large red figures, with the agent's reason. Each card says what signing does: *"Signing pays this from checking"* or *"Approving moves no cash; nothing is sent."*
- You type your name once under **Signing as** (the desk remembers it), and it appears on each card's **signature line**: "X *Olivia*".
- **Sign & approve** calls the one backend route that can move cash. The card is replaced by a big oxblood **APPROVED** stamp that lands with a small "thump" (or a grey **DECLINED**).
- You can't sign without a name, and agents can't sign at all: the backend refuses agent names, and the MCP `pay` tool refuses them again.

## Small things that make it a desk people want to sit at

- **Words over codes.** "Matter No. 101", "In re: Bulldog tee", "Convene the team", "Reconvene the team", "Reset the books". It sounds like a place, not a database.
- **One run at a time, explained.** If another matter is in session, the button is disabled and says why: *"They share the cash."*
- **It survives a refresh.** If you reload during a run, the desk finds the run in progress and keeps following it. If the backend restarts mid-run, it says so plainly instead of spinning forever.
- **Quiet motion only where it means something:** the working seat breathes, the transcript lines settle in as they're "typed", the stamp thumps, and the balance counts down. Everything is turned off for people who prefer reduced motion.
- **Accessible:** real buttons and labels, a live-region transcript for screen readers, keyboard focus in oxblood, and no meaning carried by color alone. Every state also has words.
- **Honest footer:** *Every agent runs on gpt-6-luna via Portkey · shop facts come only from the MCP server · nothing is sent to customers or vendors · every step is in the audit trail.*

## Files

| File | What it holds |
|---|---|
| `frontend/src/App.tsx` | The desk: loads the board, runs a ticket, follows its events every 1.5 s, and handles signing and reset |
| `frontend/src/components/Docket.tsx` | The case folders and their stamps |
| `frontend/src/components/Bench.tsx` | The five seats and how each agent's live state is worked out from the events |
| `frontend/src/components/Proceedings.tsx` | The court-reporter transcript |
| `frontend/src/components/Memoranda.tsx` | Per-agent memos and drafted letters |
| `frontend/src/components/Signatures.tsx` | Approvals with the signature line and stamps |
| `frontend/src/components/Register.tsx` | The checkbook ledger and the balance count-down |
| `frontend/src/firm.ts` | The desk's vocabulary: agent titles, tool phrases, statuses |
| `frontend/src/api.ts` | Calls to `http://localhost:8000` |
| `frontend/src/index.css`, `App.css` | Paper, ink, oxblood, and the four typefaces |
