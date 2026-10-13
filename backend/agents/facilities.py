"""Facilities: handles the shop space: leases, rent, and the landlord."""

from __future__ import annotations

from ..models import AgentReport
from ..team import make_agent

agent = make_agent("facilities", AgentReport)
