"""Campus Customs API: the routes the React dashboard calls.

Every shop fact goes through the MCP server (`call_shop_tool`); this file never
opens the database. Human actions (run, approve, reject, reset) are appended to
output/audit_trail.json like every agent step.

Start it from the backend/ folder (with the project's .venv active):

    cd backend
    uvicorn main:app --reload --port 8000

This turns on the backend at http://localhost:8000 so the dashboard can call these routes.

Routes
  GET  /tickets                  the tickets, each open or resolved
  POST /tickets/{id}/run         run the agent team on one ticket (in the background)
  GET  /tickets/{id}/summary     what each agent did on that ticket in its latest run
  GET  /runs/{run_id}            progress and result of a run
  GET  /events                   recent agent events: who said what, which tools they used
  GET  /approvals                payments and purchase orders waiting for a human
  POST /approvals/approve        a human approves a payment (moves cash) or a purchase order
  POST /approvals/reject         a human rejects one
  GET  /cash                     checking balance from cash_accounts
  POST /reset                    reset the working database to the original values
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# `uvicorn main:app` from inside backend/ loads this file on its own, so make the
# project folder importable and use the `backend` package by name.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.agents.boss import handle_ticket  # noqa: E402
from backend.config import MODEL_NAME  # noqa: E402
from backend.models import AGENT_NAMES, Ticket  # noqa: E402
from backend.team import TeamDeps, call_shop_tool  # noqa: E402

app = FastAPI(title="Campus Customs API", version="1.0")

# The React dev server (Vite) runs on its own port and calls this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# All tickets share one bank account, so only one agent run may change the board at a time.
_run_lock = asyncio.Lock()
_runs: dict[str, dict[str, Any]] = {}


def _require_ok(result: dict) -> dict:
    """Turn an MCP tool refusal into an HTTP error the dashboard can show."""
    if "error" in result:
        status = 409 if result.get("refused") or "Refused" in result["error"] else 400
        raise HTTPException(status_code=status, detail=result["error"])
    return result


async def _require_purchase_order(draft_id: int) -> None:
    drafts = (await call_shop_tool("list_pending_requests"))["board_drafts"]
    draft = next((d for d in drafts if d["id"] == draft_id), None)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"No draft with id {draft_id}.")
    if draft["kind"] != "purchase_order":
        raise HTTPException(status_code=400, detail=f"Draft {draft_id} is a {draft['kind']}, not a purchase order.")


def _require_human(name: str) -> str:
    who = (name or "").strip()
    if not who or who.lower().replace(" ", "_") in AGENT_NAMES:
        raise HTTPException(status_code=400, detail="A human name is required for this action.")
    return who


# ---------------------------------------------------------------- tickets


@app.get("/tickets")
async def list_tickets() -> dict:
    """The tickets on the board, each marked open or resolved.

    A ticket is resolved once the agent team has finished its run and Boss has made the
    final call (its status is no longer `open`). `status` still says what happens next,
    for example `awaiting_approval` when a human must sign off on a payment.
    """
    data = await call_shop_tool("list_tickets")
    tickets = [
        {**t, "state": "open" if t["status"] == "open" else "resolved"} for t in data["tickets"]
    ]
    return {"tickets": tickets, "running": _current_run()}


async def _run_ticket(run_id: str, ticket: Ticket) -> None:
    run = _runs[run_id]
    async with _run_lock:
        run["status"] = "running"
        run["started_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            decision, deps = await handle_ticket(ticket, TeamDeps(run_id=run_id))
            run.update(
                status="finished",
                decision=decision.model_dump(),
                delegations=deps.budget["delegations"],
            )
        except Exception as exc:  # usage limit, model timeout, ...
            run.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            audit.record("error", run_id=run_id, ticket_id=ticket.id, agent="boss", error=run["error"])
        finally:
            run["finished_at"] = datetime.now().isoformat(timespec="seconds")


def _current_run() -> dict | None:
    return next(({"run_id": k, **v} for k, v in _runs.items() if v["status"] in ("queued", "running")), None)


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict:
    """Start the agent team on one ticket. Boss decides who to delegate to.

    Runs in the background (a ticket takes 1-3 minutes). Poll /runs/{run_id} or /events.
    """
    if _current_run():
        raise HTTPException(status_code=409, detail="Another ticket is already running. Wait for it to finish.")
    data = _require_ok(await call_shop_tool("get_ticket", ticket_id=ticket_id))
    ticket = Ticket(**data["ticket"])
    run_id = f"{audit.new_run_id()}-api-t{ticket_id}"
    _runs[run_id] = {"ticket_id": ticket_id, "status": "queued", "model": MODEL_NAME}
    audit.record("run_started", run_id=run_id, ticket_id=ticket_id, model=MODEL_NAME, via="api")
    asyncio.create_task(_run_ticket(run_id, ticket))
    return {"run_id": run_id, "ticket_id": ticket_id, "status": "queued"}


@app.get("/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int) -> dict:
    """What each agent did on this ticket in its latest finished run: a short memo per
    agent, the tools it used, who it delegated to, and Boss's final decision."""
    trail = json.loads(audit.AUDIT_PATH.read_text()) if audit.AUDIT_PATH.exists() else []
    # Only runs since the last reset describe the current board.
    last_reset = max((i for i, e in enumerate(trail) if e["event"] == "reset_shop"), default=-1)
    trail = trail[last_reset + 1:]
    finished = [e["run_id"] for e in trail if e.get("ticket_id") == ticket_id and e["event"] == "ticket_decision"]
    if not finished:
        return {"ticket_id": ticket_id, "run_id": None, "agents": [], "decision": None}
    run_id = finished[-1]
    entries = [e for e in trail if e.get("run_id") == run_id and e.get("ticket_id") == ticket_id]
    agents: dict[str, dict] = {}
    order: list[str] = []
    tokens = 0
    for e in entries:
        name, d = e.get("agent"), e["details"]
        if not name or name not in AGENT_NAMES:
            continue
        if name not in agents:
            agents[name] = {"agent": name, "memo": None, "tools": [], "asked": [], "model_calls": 0}
            order.append(name)
        a = agents[name]
        if e["event"] == "model_response":
            a["model_calls"] += 1
            tokens += (d.get("input_tokens") or 0) + (d.get("output_tokens") or 0)
            for c in d.get("tool_calls", []):
                if c["tool"] not in ("final_result", "ask_teammate") and c["tool"] not in a["tools"]:
                    a["tools"].append(c["tool"])
        elif e["event"] == "delegation" and d.get("from_agent") == name and d.get("to_agent") not in a["asked"]:
            a["asked"].append(d.get("to_agent"))
        elif e["event"] == "agent_output":
            out = d.get("output", {})
            a["memo"] = out.get("summary") or out.get("decision")
    decision = next((e["details"]["decision"] for e in reversed(entries) if e["event"] == "ticket_decision"), None)
    return {
        "ticket_id": ticket_id,
        "run_id": run_id,
        "decision": decision,
        "agents": [agents[n] for n in order],
        "tokens": tokens,
    }


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"No run {run_id} in this server session.")
    return {"run_id": run_id, **_runs[run_id]}


# ---------------------------------------------------------------- events


def _summarize(entry: dict) -> dict:
    """One audit-trail entry as a dashboard row: who, what they said, which tools."""
    d = entry.get("details", {})
    event = entry["event"]
    said, tools = None, []
    if event in ("delegation", "reply", "delegation_refused", "ticket_started", "decision"):
        said = d.get("message")
    elif event == "model_response":
        said = d.get("text")
        tools = [c["tool"] for c in d.get("tool_calls", []) if c["tool"] != "final_result"]
    elif event == "tool_result":
        tools = [d.get("tool")]
        said = d.get("result")
    elif event == "agent_output":
        out = d.get("output", {})
        said = out.get("summary") or out.get("decision")
    elif event == "ticket_decision":
        said = f"[{d['decision']['status']}] {d['decision']['decision']}"
    elif event in ("human_approve", "human_reject", "reset_shop", "error", "run_aborted", "run_note"):
        said = d.get("message") or d.get("error") or d.get("reason") or d.get("note") or json.dumps(d.get("result"))
    return {
        "seq": entry["seq"],
        "at": entry["at"],
        "run_id": entry["run_id"],
        "ticket_id": entry["ticket_id"],
        "agent": entry["agent"],
        "to_agent": d.get("to_agent"),
        "event": event,
        "said": said,
        "tools": tools,
        "model": d.get("model"),
    }


@app.get("/events")
async def events(
    after: int = Query(-1, description="Only events with seq greater than this (for refresh)"),
    ticket_id: int | None = None,
    run_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Recent agent events from the audit trail, oldest first. `seq` is the position in the
    trail; pass the last one you saw as `after` to get only new events."""
    trail = json.loads(audit.AUDIT_PATH.read_text()) if audit.AUDIT_PATH.exists() else []
    rows = []
    for seq, entry in enumerate(trail):
        if seq <= after:
            continue
        if ticket_id is not None and entry.get("ticket_id") != ticket_id:
            continue
        if run_id and entry.get("run_id") != run_id:
            continue
        rows.append({**entry, "seq": seq})
    rows = rows[-limit:]
    return {"events": [_summarize(r) for r in rows], "last_seq": len(trail) - 1}


# ---------------------------------------------------------------- approvals


@app.get("/approvals")
async def approvals() -> dict:
    """What is waiting for a human: payment requests and purchase orders."""
    data = await call_shop_tool("list_pending_requests")
    pos = [d for d in data["board_drafts"] if d["kind"] == "purchase_order" and d["status"] == "pending_approval"]
    messages = [d for d in data["board_drafts"] if d["kind"] == "customer_message"]
    return {
        "payments": data["pending_payment_requests"],
        "purchase_orders": pos,
        "customer_drafts": messages,
        "price_quotes": data.get("price_quotes", []),
        "pending_total": data["pending_total"],
        "cash_after_pending": data["cash_after_pending"],
    }


class Decision(BaseModel):
    kind: Literal["payment", "purchase_order"]
    id: int = Field(description="Payment request id, or purchase order draft id")
    by: str = Field(description="Name of the human making the decision")
    reason: str | None = None


@app.post("/approvals/approve")
async def approve(body: Decision) -> dict:
    """A human approves. For a payment this is the ONLY place cash changes: it calls the
    human-only `pay` tool, which refuses if cash is short and records the payment."""
    who = _require_human(body.by)
    if body.kind == "payment":
        result = _require_ok(await call_shop_tool("pay", request_id=body.id, approved_by=who))
    else:
        await _require_purchase_order(body.id)
        result = _require_ok(await call_shop_tool("decide_draft", draft_id=body.id, approve=True, decided_by=who))
    audit.record("human_approve", run_id=None, agent=None, by=who, kind=body.kind, id=body.id, result=result)
    return result


@app.post("/approvals/reject")
async def reject(body: Decision) -> dict:
    who = _require_human(body.by)
    if body.kind == "payment":
        result = _require_ok(
            await call_shop_tool("reject_request", request_id=body.id, rejected_by=who, reason=body.reason or "Rejected on the dashboard")
        )
    else:
        await _require_purchase_order(body.id)
        result = _require_ok(await call_shop_tool("decide_draft", draft_id=body.id, approve=False, decided_by=who))
    audit.record("human_reject", run_id=None, agent=None, by=who, kind=body.kind, id=body.id, result=result)
    return result


# ---------------------------------------------------------------- cash and reset


@app.get("/cash")
async def cash() -> dict:
    """The checking balance from cash_accounts, plus what is pending."""
    bills = await call_shop_tool("get_bills_and_cash")
    pending = await call_shop_tool("list_pending_requests")
    paid = await call_shop_tool("list_payments")
    checking = next((a for a in bills["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "today": bills["today"],
        "pending_total": pending["pending_total"],
        "balance_after_pending": pending["cash_after_pending"],
        "register": paid["payments"],
    }


class ResetBody(BaseModel):
    by: str = Field(description="Name of the human resetting the shop")


@app.post("/reset")
async def reset(body: ResetBody) -> dict:
    """Reset the working database to the original values (before a fresh run)."""
    who = _require_human(body.by)
    if _current_run():
        raise HTTPException(status_code=409, detail="A ticket is running. Reset after it finishes.")
    result = _require_ok(await call_shop_tool("reset_shop", confirm=True, requested_by=who))
    audit.record("reset_shop", run_id=None, agent=None, requested_by=who, result=result)
    return result


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "model": MODEL_NAME}
