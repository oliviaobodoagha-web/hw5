"""Full team run: reset the working database, then let Boss work every open ticket.

Everything goes through the MCP server: the reset (`reset_shop`), reading the
board (`list_tickets`), and the end-of-run snapshot. The backend never opens the
database itself.

Tickets run one at a time so each one sees the cash, pending payments, drafts,
and reservations left by the ones before it.

    python -m backend.run_team [--operator NAME]

Writes output/team_run.json (this run's summary) and appends every agent-loop
step to output/audit_trail.json (never wiped).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from . import audit
from .agents.boss import handle_ticket
from .config import MODEL_NAME, PROJECT_DIR
from .models import Ticket
from .team import TeamDeps, call_shop_tool

OUTPUT = PROJECT_DIR / "output" / "team_run.json"


async def board_state() -> dict:
    tickets = await call_shop_tool("list_tickets")
    pending = await call_shop_tool("list_pending_requests")
    payments = await call_shop_tool("list_payments")
    bills = await call_shop_tool("get_bills_and_cash")
    return {
        "tickets": [{k: t[k] for k in ("id", "status", "notes")} for t in tickets["tickets"]],
        "pending_payment_requests": pending["pending_payment_requests"],
        "board_drafts": pending["board_drafts"],
        "payments": payments["payments"],
        "decided_requests": payments["decided_requests"],
        "cash_accounts": bills["cash_accounts"],
        "cash_after_pending": pending["cash_after_pending"],
    }


async def main(operator: str) -> None:
    run_id = audit.new_run_id()
    reset = await call_shop_tool("reset_shop", confirm=True, requested_by=operator)
    audit.record("reset_shop", run_id=run_id, agent=None, requested_by=operator, result=reset)
    if not reset.get("reset"):
        raise SystemExit(f"Reset refused: {reset}")

    tickets = [Ticket(**t) for t in (await call_shop_tool("list_tickets", status="open"))["tickets"]]
    audit.record("run_started", run_id=run_id, model=MODEL_NAME, operator=operator,
                 open_tickets=[t.id for t in tickets])
    print(f"Run {run_id}. Database reset. Model: {MODEL_NAME}. Open tickets: {[t.id for t in tickets]}")

    results = []
    for ticket in tickets:
        print(f"\n--- Ticket {ticket.id}: {ticket.subject} ---")
        start = time.perf_counter()
        deps = TeamDeps(run_id=run_id)
        try:
            decision, deps = await handle_ticket(ticket, deps)
        except Exception as exc:  # a usage limit or model error stops this ticket, not the run
            deps.audit("error", agent="boss", error=f"{type(exc).__name__}: {exc}")
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            results.append({"ticket_id": ticket.id, "error": f"{type(exc).__name__}: {exc}"})
            continue
        seconds = round(time.perf_counter() - start, 1)
        for e in deps.events:
            arrow = f"{e.from_agent or ''} -> {e.to_agent or ''}".strip(" ->")
            print(f"  [{e.kind}] {arrow}: {e.message[:110]}")
        print(f"  STATUS: {decision.status} ({seconds}s, {deps.budget['delegations']} delegations)")
        results.append(
            {
                "ticket_id": ticket.id,
                "seconds": seconds,
                "delegations": deps.budget["delegations"],
                "decision": decision.model_dump(),
                "events": [e.model_dump(mode="json") for e in deps.events],
            }
        )

    report = {"run_id": run_id, "model": MODEL_NAME, "results": results, "board_after_run": await board_state()}
    OUTPUT.write_text(json.dumps(report, indent=2, default=str))
    audit.record("run_finished", run_id=run_id, tickets=[r["ticket_id"] for r in results])
    print(f"\nSaved {OUTPUT.relative_to(PROJECT_DIR)}; audit steps appended to output/audit_trail.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", default="Olivia", help="Human who started the run (recorded on reset)")
    asyncio.run(main(parser.parse_args().operator))
