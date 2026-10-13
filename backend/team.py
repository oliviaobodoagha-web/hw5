"""Wiring for the Campus Customs agent team.

Every agent gets:
  - its own prompt from backend/prompts/<name>.md
  - the shop's MCP tools (mcp_server/server.py)
  - an `ask_teammate` tool so it can delegate to ANY other agent (full connectivity)

Delegation guardrails, because multi-agent chats burn tokens fast:
  - an agent cannot ask itself
  - an agent cannot ask someone already waiting on this chain (no A -> B -> A loops)
  - chains stop at MAX_DELEGATION_DEPTH hand-offs
  - at most MAX_DELEGATIONS_PER_TICKET hand-offs per ticket
  - every nested run shares the caller's usage counter, so one request/tool/token limit
    covers the whole ticket

Every agent run goes through `run_agent`, which appends each loop step to
output/audit_trail.json as it happens (see backend/audit.py).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

from pydantic_ai import Agent, CallToolsNode, ModelRequestNode, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage, UsageLimits

from . import audit
from .config import MAX_DELEGATION_DEPTH, MCP_SERVER_PATH, build_model, load_prompt
from .models import AGENT_NAMES, AgentName, TeamEvent, Ticket

ROLES: dict[AgentName, str] = {
    "boss": "Reads each ticket, decides who works on it, and makes the final call.",
    "inventory": "Checks stock by SKU and size, spots shortfalls, and finds which vendor can restock.",
    "accounting": "Watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval.",
    "facilities": "Handles the shop space: leases, rent, and the landlord.",
    "customer_service": "Drafts messages to customers. Drafts stay on the board; nothing is sent.",
}

# One run of a ticket may not exceed these limits, across all agents combined.
TICKET_USAGE_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=300_000)
MAX_DELEGATIONS_PER_TICKET = 8


@dataclass
class TeamDeps:
    """Shared state passed down every delegation chain for one ticket.

    `events`, `budget`, and `run_id` are shared by reference across the chain,
    so every agent working the ticket counts against the same budget.
    """

    ticket: Ticket | None = None
    chain: list[AgentName] = field(default_factory=list)
    events: list[TeamEvent] = field(default_factory=list)
    run_id: str = field(default_factory=audit.new_run_id)
    budget: dict[str, int] = field(default_factory=lambda: {"delegations": 0})

    def log(self, **kwargs: Any) -> None:
        event = TeamEvent(ticket_id=self.ticket.id if self.ticket else None, **kwargs)
        self.events.append(event)
        self.audit(
            event.kind,
            agent=event.from_agent or event.to_agent,
            from_agent=event.from_agent,
            to_agent=event.to_agent,
            message=event.message,
        )

    def audit(self, event: str, agent: str | None = None, **details: Any) -> None:
        audit.record(
            event,
            run_id=self.run_id,
            ticket_id=self.ticket.id if self.ticket else None,
            agent=agent or (self.chain[-1] if self.chain else None),
            chain=list(self.chain),
            **details,
        )


@lru_cache(maxsize=1)
def shop_toolset() -> MCPToolset:
    """The shop's MCP server, launched over stdio with the current Python interpreter."""
    return MCPToolset(MCP_SERVER_PATH)


# Tools no agent may ever see. The backend calls them only when a human acts on the dashboard.
HUMAN_ONLY_TOOLS = {"pay", "reject_request", "decide_draft", "reset_shop"}

# Which MCP tools each agent may use, matching its scope. Everyone also gets ask_teammate.
AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": {
        "get_ticket", "list_tickets", "list_pending_requests", "list_payments",
        "check_stock", "get_vendor_status", "get_bills_and_cash",
    },
    "inventory": {
        "get_ticket", "check_stock", "get_vendor_status", "list_tickets", "list_pending_requests",
        "reserve_stock",
    },
    "accounting": {
        "get_ticket", "get_bills_and_cash", "get_vendor_status", "check_stock",
        "list_pending_requests", "list_payments", "request_payment", "post_draft", "quote_price",
    },
    "facilities": {"get_ticket", "get_bills_and_cash", "list_pending_requests", "list_payments", "list_tickets"},
    "customer_service": {"get_ticket", "list_tickets", "list_pending_requests", "check_stock", "post_draft"},
}


def agent_toolset(name: AgentName):
    """The MCP tools this agent may use. Human-only tools are never included."""
    allowed = AGENT_TOOLS[name] - HUMAN_ONLY_TOOLS
    return shop_toolset().filtered(lambda ctx, tool: tool.name in allowed)


def _roster(for_agent: AgentName) -> str:
    lines = [f"- {name}: {role}" for name, role in ROLES.items() if name != for_agent]
    return (
        "\n\n## Your teammates\n"
        "You can delegate to any teammate with the `ask_teammate` tool. "
        "Ask a specific question and include the ticket facts they need.\n" + "\n".join(lines)
    )


def ticket_context(ticket: Ticket | None, run_id: str | None = None) -> str:
    if ticket is None:
        return ""
    # The run id makes every run's requests unique, so no gateway cache can replay an old run.
    run_line = f"Run: {run_id}\n" if run_id else ""
    return f"{run_line}Ticket on the board (from the tickets table):\n{ticket.model_dump_json(indent=2)}\n\n"


def make_agent(name: AgentName, output_type: type) -> Agent[TeamDeps, Any]:
    """Build one team member with its prompt, the MCP tools, and the delegation tool."""
    agent: Agent[TeamDeps, Any] = Agent(
        build_model(),
        name=name,
        instructions=load_prompt(name) + _roster(name),
        deps_type=TeamDeps,
        output_type=output_type,
        toolsets=[agent_toolset(name)],
    )

    @agent.tool
    async def ask_teammate(ctx: RunContext[TeamDeps], teammate: AgentName, request: str) -> str:
        """Delegate a specific request to another agent on the team and get their report back.

        Args:
            teammate: Who to ask: boss, inventory, accounting, facilities, or customer_service.
            request: The exact question or task, with the ticket facts they need.
        """
        deps = ctx.deps
        refusal = None
        if teammate == name:
            refusal = "You cannot delegate to yourself. Do the work with your own tools."
        elif teammate in deps.chain:
            refusal = (
                f"{teammate} is already waiting on this chain ({' -> '.join(deps.chain)}). "
                "Answer with what you have instead of asking them back."
            )
        elif len(deps.chain) > MAX_DELEGATION_DEPTH:
            refusal = "Delegation depth limit reached. Finish with what you have and list open questions."
        elif deps.budget["delegations"] >= MAX_DELEGATIONS_PER_TICKET:
            refusal = "This ticket's delegation budget is used up. Finish with what you have and list open questions."
        if refusal:
            deps.log(kind="delegation_refused", from_agent=name, to_agent=teammate, message=refusal)
            return refusal

        deps.budget["delegations"] += 1
        deps.log(kind="delegation", from_agent=name, to_agent=teammate, message=request)
        output = await run_agent(
            teammate,
            f"{ticket_context(deps.ticket, deps.run_id)}Request from {name}:\n{request}",
            replace(deps, chain=[*deps.chain, teammate]),
            usage=ctx.usage,
        )
        summary = getattr(output, "summary", None) or getattr(output, "decision", "")
        deps.log(kind="reply", from_agent=teammate, to_agent=name, message=summary)
        return output.model_dump_json()

    return agent


async def run_agent(name: AgentName, prompt: str, deps: TeamDeps, usage: RunUsage | None = None) -> Any:
    """Run one agent's loop, appending every step to the audit trail as it happens.

    Logged per step: the prompt it received, each model response (model name, tokens,
    text, tool calls with arguments), each tool result or retry, and the final output.
    """
    deps.audit("agent_start", agent=name, prompt=prompt)
    async with get_agent(name).iter(
        prompt, deps=deps, usage=usage, usage_limits=TICKET_USAGE_LIMITS
    ) as run:
        async for node in run:
            if isinstance(node, CallToolsNode):
                resp = node.model_response
                deps.audit(
                    "model_response",
                    agent=name,
                    model=resp.model_name,
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                    text=" ".join(p.content for p in resp.parts if isinstance(p, TextPart)) or None,
                    tool_calls=[
                        {"tool": p.tool_name, "args": p.args_as_dict(), "call_id": p.tool_call_id}
                        for p in resp.parts
                        if isinstance(p, ToolCallPart)
                    ],
                )
            elif isinstance(node, ModelRequestNode):
                for part in node.request.parts:
                    if isinstance(part, ToolReturnPart):
                        deps.audit(
                            "tool_result", agent=name, tool=part.tool_name,
                            call_id=part.tool_call_id, result=part.model_response_str(),
                        )
                    elif isinstance(part, RetryPromptPart):
                        deps.audit(
                            "tool_retry", agent=name, tool=part.tool_name,
                            call_id=part.tool_call_id, error=part.model_response(),
                        )
        output = run.result.output
        total = run.usage
    deps.audit(
        "agent_output", agent=name, output=output.model_dump(),
        run_requests=total.requests, run_total_tokens=total.total_tokens,
    )
    return output


async def call_shop_tool(tool: str, **arguments: Any) -> dict:
    """Call an MCP tool directly from the backend (not through an agent).

    Used for steps that must always happen, such as recording Boss's final call,
    and for human-only tools such as `pay`.
    """
    from fastmcp import Client

    async with Client(MCP_SERVER_PATH) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    return result.data if isinstance(result.data, dict) else {"result": result.data}


_AGENTS: dict[AgentName, Agent[TeamDeps, Any]] = {}


def get_agent(name: AgentName) -> Agent[TeamDeps, Any]:
    """Look up an agent by name. Each agent lives in backend/agents/<name>.py as `agent`."""
    if name not in AGENT_NAMES:
        raise ValueError(f"Unknown agent: {name}")
    if name not in _AGENTS:
        _AGENTS[name] = importlib.import_module(f"backend.agents.{name}").agent
    return _AGENTS[name]
