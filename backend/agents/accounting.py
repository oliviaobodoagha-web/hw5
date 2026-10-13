"""Accounting: watches cash and invoices, checks margins, and prepares payments and purchase orders for approval."""

from __future__ import annotations

from ..models import AgentReport
from ..team import make_agent

agent = make_agent("accounting", AgentReport)
