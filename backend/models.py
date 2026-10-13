"""Data types shared by the agent team, the API, and the dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")


# ---------- Board ----------

class Ticket(BaseModel):
    """One row from the tickets table."""

    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


# ---------- Things agents prepare for a human ----------

class PaymentRequest(BaseModel):
    """A payment an agent proposes. Nothing is paid until a human approves it."""

    kind: Literal["invoice", "rent"]
    ref_id: int = Field(description="invoices.id for an invoice, leases.id for rent")
    payee: str
    amount: float
    account: str = "checking"
    reason: str = Field(description="Why this should be paid now, citing due date and ticket")


class PurchaseOrderDraft(BaseModel):
    """A restock order drafted for human approval. Never sent to a real vendor."""

    vendor_id: int
    vendor_name: str
    sku: str
    size: str
    qty: int
    unit_cost: float
    total_cost: float
    expected_arrival: str | None = Field(
        default=None, description="desk.date_today + vendor lead_days, once the vendor can ship"
    )
    blocked_by_invoice_id: int | None = Field(
        default=None, description="Open invoice that must be paid before this vendor will ship"
    )


class PriceQuote(BaseModel):
    """A price saved by the quote_price MCP tool. The tool refuses anything at or below cost."""

    quote_id: int | None = Field(default=None, description="id returned by quote_price")
    sku: str
    size: str | None = None
    qty: int
    list_price: float
    unit_cost: float
    quoted_unit_price: float
    discount_pct: float
    margin_per_unit: float


class CustomerMessageDraft(BaseModel):
    """A message drafted on the board. Never emailed to the customer."""

    to: str
    subject: str
    body: str


# ---------- Agent outputs ----------

class AgentReport(BaseModel):
    """What a specialist agent hands back to whoever asked it."""

    agent: AgentName
    summary: str = Field(description="Two or three sentences: what was found and what is recommended")
    facts: list[str] = Field(
        default_factory=list, description="Facts taken from MCP tool output, each with its number or date"
    )
    payment_requests: list[PaymentRequest] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrderDraft] = Field(default_factory=list)
    price_quotes: list[PriceQuote] = Field(default_factory=list)
    customer_drafts: list[CustomerMessageDraft] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list, description="Anything blocked or needing a human")


TicketStatus = Literal["resolved", "awaiting_approval", "blocked", "needs_info"]


class BossDecision(BaseModel):
    """Boss's final call on one ticket."""

    ticket_id: int
    assigned_to: list[AgentName] = Field(description="Agents Boss involved in this ticket")
    decision: str = Field(description="The final call, in plain language")
    rationale: str = Field(description="Why, citing the facts the team found")
    status: TicketStatus
    payment_requests: list[PaymentRequest] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrderDraft] = Field(default_factory=list)
    price_quotes: list[PriceQuote] = Field(default_factory=list)
    customer_drafts: list[CustomerMessageDraft] = Field(default_factory=list)


# ---------- Activity feed for the dashboard ----------

class TeamEvent(BaseModel):
    at: datetime = Field(default_factory=datetime.now)
    ticket_id: int | None = None
    kind: Literal["ticket_started", "delegation", "reply", "delegation_refused", "decision"]
    from_agent: AgentName | None = None
    to_agent: AgentName | None = None
    message: str
