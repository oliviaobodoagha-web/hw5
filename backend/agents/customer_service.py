"""Customer Service: drafts messages for customers. Drafts stay on the board; nothing is sent."""

from __future__ import annotations

from ..models import AgentReport
from ..team import make_agent

agent = make_agent("customer_service", AgentReport)
