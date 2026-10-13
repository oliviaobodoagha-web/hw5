"""Append-only audit trail: output/audit_trail.json.

Every agent-loop step is appended as it happens: the prompt an agent received,
each model response (with model name and tokens), each tool call and its result,
each delegation, each final output, and each human action. The file holds one
JSON array that only grows. It is never wiped between runs, and each run is
tagged with its own run_id.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any

from .config import PROJECT_DIR

AUDIT_PATH = PROJECT_DIR / "output" / "audit_trail.json"
MAX_TEXT = 4000  # long tool results are clipped in the log so the file stays readable

_lock = threading.Lock()
_step = 0


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def _clip(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + f"... [clipped {len(value) - MAX_TEXT} chars]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value]
    return value


def _load() -> list:
    if not AUDIT_PATH.exists():
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text() or "[]")
    except json.JSONDecodeError:
        # Never destroy an unreadable trail: keep it aside and start a new array.
        AUDIT_PATH.rename(AUDIT_PATH.with_suffix(f".corrupt-{uuid.uuid4().hex[:6]}.json"))
        return []
    return data if isinstance(data, list) else [data]


def record(
    event: str,
    *,
    run_id: str | None,
    ticket_id: int | None = None,
    agent: str | None = None,
    chain: list[str] | None = None,
    **details: Any,
) -> None:
    """Append one step to the audit trail (atomic write, safe across threads)."""
    global _step
    with _lock:
        _step += 1
        entry = {
            "at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "step": _step,
            "ticket_id": ticket_id,
            "agent": agent,
            "chain": chain or [],
            "event": event,
            "details": _clip(details),
        }
        trail = _load()
        trail.append(entry)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(trail, indent=1, default=str))
        os.replace(tmp, AUDIT_PATH)
