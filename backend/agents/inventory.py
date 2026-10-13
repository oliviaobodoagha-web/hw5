"""Inventory: checks stock by SKU and size, spots shortfalls, and finds the vendor to restock."""

from __future__ import annotations

from ..models import AgentReport
from ..team import make_agent

agent = make_agent("inventory", AgentReport)
