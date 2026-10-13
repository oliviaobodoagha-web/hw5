"""Boss: reads each ticket, routes it to the right teammates, and makes the final call."""

from __future__ import annotations

from ..models import BossDecision, Ticket
from ..team import TeamDeps, call_shop_tool, run_agent, make_agent, ticket_context

agent = make_agent("boss", BossDecision)


async def handle_ticket(ticket: Ticket, deps: TeamDeps | None = None) -> tuple[BossDecision, TeamDeps]:
    """Run Boss on one ticket. Boss delegates as needed and returns its final decision."""
    deps = deps or TeamDeps()
    deps.ticket = ticket
    deps.chain = ["boss"]
    deps.log(kind="ticket_started", to_agent="boss", message=f"#{ticket.id} {ticket.subject}")
    decision: BossDecision = await run_agent(
        "boss", f"{ticket_context(ticket, deps.run_id)}Work this ticket and make the final call.", deps
    )

    # The backend, not the model, records Boss's final call on the board (via MCP), every time.
    current = await call_shop_tool("get_ticket", ticket_id=ticket.id)
    if current.get("ticket", {}).get("status") != decision.status:
        result = await call_shop_tool(
            "update_ticket",
            ticket_id=ticket.id,
            status=decision.status,
            note=decision.decision,
            updated_by="boss",
        )
        deps.audit("board_update_by_backend", agent="boss", tool="update_ticket", result=result)
    deps.log(kind="decision", from_agent="boss", message=decision.decision)
    deps.audit("ticket_decision", agent="boss", decision=decision.model_dump())
    return decision, deps
