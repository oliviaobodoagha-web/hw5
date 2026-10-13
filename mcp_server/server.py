"""Campus Customs MCP server.

Exposes read-only shop tools to the agent team. All data comes from the
working copy of the shop database (data/campus_customs_new.db). The original
data/campus_customs.db is never touched.

Run (stdio):
    python mcp_server/server.py
"""

from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs_new.db"
ORIGINAL_DB_PATH = DATA_DIR / "campus_customs.db"  # never written; only copied from on reset

mcp = FastMCP("campus-customs")


TICKET_STATUSES = ("open", "resolved", "awaiting_approval", "blocked", "needs_info")
AGENT_NAMES = ("boss", "inventory", "accounting", "facilities", "customer_service")

# Board tables that live only in the working copy. Resetting from the original
# database wipes them, so a reset clears the approval queue and drafts too.
_BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    kind TEXT NOT NULL,            -- 'invoice' or 'rent'
    ref_id INTEGER NOT NULL,       -- invoices.id or leases.id
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    reason TEXT,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending, paid, rejected
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS board_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- 'customer_message' or 'purchase_order'
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL,          -- 'draft' or 'pending_approval'
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    reserved_by TEXT NOT NULL,
    reserved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT,
    qty INTEGER NOT NULL,
    list_price REAL NOT NULL,
    unit_cost REAL NOT NULL,
    discount_pct REAL NOT NULL,
    unit_price REAL NOT NULL,
    total REAL NOT NULL,
    margin_per_unit REAL NOT NULL,
    quoted_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_BOARD_SCHEMA)
    return conn


def _add_one_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(f"Cannot add a month to {d}")


def _pending_total(conn: sqlite3.Connection, account: str | None = None) -> float:
    query = "SELECT COALESCE(SUM(amount), 0) AS t FROM approval_requests WHERE status = 'pending'"
    params: tuple = ()
    if account:
        query += " AND account = ?"
        params = (account,)
    return round(conn.execute(query, params).fetchone()["t"], 2)


def _today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' comes from desk.date_today, not the real clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None or not row["date_today"]:
        raise ValueError("desk.date_today is missing; cannot determine the shop's today.")
    return date.fromisoformat(row["date_today"])


@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict:
    """Check on-hand stock for a SKU (optionally one size), with its cost and list price.

    Use this to see whether a customer order or bulk request can be filled from
    stock, how big the shortfall is, and what margin room exists for a discount.
    """
    with _connect() as conn:
        query = "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?"
        params: list = [sku]
        if size:
            query += " AND size = ?"
            params.append(size)
        rows = [dict(r) for r in conn.execute(query, params)]
        if not rows:
            target = f"{sku} size {size}" if size else sku
            return {"error": f"No inventory record for {target}."}

        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        res_query = "SELECT * FROM stock_reservations WHERE sku = ?"
        res_params: list = [sku]
        if size:
            res_query += " AND size = ?"
            res_params.append(size)
        reservations = [dict(r) for r in conn.execute(res_query, res_params)]

    # qty is what is free on the shelf; reserved units were already taken off it.
    result: dict = {"sku": sku, "stock": rows, "reservations": reservations}
    if price is None:
        result["pricing"] = None
        result["pricing_note"] = f"No pricing record for {sku}."
    else:
        result["pricing"] = {
            "unit_cost": price["unit_cost"],
            "list_price": price["list_price"],
            "margin_per_unit": round(price["list_price"] - price["unit_cost"], 2),
        }
    return result


@mcp.tool
def get_vendor_status(vendor_id: int | None = None) -> dict:
    """List vendors (or one vendor) with specialty, lead time, open invoices, and whether they will ship.

    A vendor will not ship new product while it has any open unpaid invoice.
    Overdue status is measured against desk.date_today.
    """
    with _connect() as conn:
        today = _today(conn)
        if vendor_id is None:
            vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        else:
            vendors = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchall()
            if not vendors:
                return {"error": f"No vendor with id {vendor_id}."}

        out = []
        for v in vendors:
            invoices = conn.execute(
                "SELECT id, amount, due_date, status, description FROM invoices "
                "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
                (v["id"],),
            ).fetchall()
            open_invoices = []
            for inv in invoices:
                days_until_due = (date.fromisoformat(inv["due_date"]) - today).days
                open_invoices.append(
                    {**dict(inv), "days_until_due": days_until_due, "overdue": days_until_due < 0}
                )
            can_ship = not open_invoices
            out.append(
                {
                    "id": v["id"],
                    "name": v["name"],
                    "specialty": v["specialty"],
                    "lead_days": v["lead_days"],
                    "open_invoices": open_invoices,
                    "can_ship": can_ship,
                    "earliest_arrival_if_ordered_today": (
                        (today + timedelta(days=v["lead_days"])).isoformat() if can_ship else None
                    ),
                    "blocked_reason": (
                        None if can_ship
                        else "Open unpaid invoice(s); vendor will not ship until paid."
                    ),
                }
            )

    return {"today": today.isoformat(), "vendors": out}


@mcp.tool
def get_bills_and_cash() -> dict:
    """List every open obligation (lease rent and open vendor invoices) next to available cash.

    Each bill shows its amount, due date, and days until due versus desk.date_today
    (negative = overdue). Totals show whether cash covers everything owed.
    """
    with _connect() as conn:
        today = _today(conn)
        bills = []

        for lease in conn.execute("SELECT * FROM leases ORDER BY next_due"):
            bills.append(
                {
                    "kind": "rent",
                    "ref_id": lease["id"],
                    "payee": lease["landlord"],
                    "description": f"Rent for {lease['space_name']}",
                    "amount": lease["monthly_rent"],
                    "due_date": lease["next_due"],
                }
            )

        for inv in conn.execute(
            "SELECT i.id, i.amount, i.due_date, i.description, v.name AS vendor_name "
            "FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id "
            "WHERE i.status = 'open' ORDER BY i.due_date"
        ):
            bills.append(
                {
                    "kind": "invoice",
                    "ref_id": inv["id"],
                    "payee": inv["vendor_name"],
                    "description": inv["description"],
                    "amount": inv["amount"],
                    "due_date": inv["due_date"],
                }
            )

        accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]

    for b in bills:
        b["days_until_due"] = (date.fromisoformat(b["due_date"]) - today).days
        b["overdue"] = b["days_until_due"] < 0
    bills.sort(key=lambda b: b["due_date"])

    total_owed = round(sum(b["amount"] for b in bills), 2)
    total_cash = round(sum(a["balance"] for a in accounts), 2)
    return {
        "today": today.isoformat(),
        "bills": bills,
        "cash_accounts": accounts,
        "total_owed": total_owed,
        "total_cash": total_cash,
        "cash_after_paying_all": round(total_cash - total_owed, 2),
        "cash_covers_all": total_cash >= total_owed,
    }


# ---------------------------------------------------------------- board tools


@mcp.tool
def list_tickets(status: str | None = None) -> dict:
    """List tickets on the board, optionally filtered by status
    (open, resolved, awaiting_approval, blocked, needs_info).

    Use this to see the whole board: related tickets, and tickets that depend on each other.
    """
    if status and status not in TICKET_STATUSES:
        return {"error": f"Unknown status '{status}'. Use one of {list(TICKET_STATUSES)}."}
    with _connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,))
        else:
            rows = conn.execute("SELECT * FROM tickets ORDER BY id")
        tickets = [dict(r) for r in rows]
    return {"count": len(tickets), "tickets": tickets}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket from the board by id, with its current status and notes."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"error": f"No ticket with id {ticket_id}."}
    return {"ticket": dict(row)}


@mcp.tool
def list_payments() -> dict:
    """List payments already made and every approval decision a human has taken
    (paid or rejected), so the team can confirm what happened after approval.
    """
    with _connect() as conn:
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
        decided = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM approval_requests WHERE status != 'pending' ORDER BY id"
            )
        ]
    return {
        "payments": payments,
        "total_paid": round(sum(p["amount"] for p in payments), 2),
        "decided_requests": decided,
    }


@mcp.tool
def list_pending_requests() -> dict:
    """List payment requests waiting for human approval, plus drafts on the board,
    and how much cash would remain if every pending payment were approved.

    Check this before requesting a payment so the same bill is never requested twice.
    """
    with _connect() as conn:
        pending = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM approval_requests WHERE status = 'pending' ORDER BY id"
            )
        ]
        drafts = [dict(r) for r in conn.execute("SELECT * FROM board_drafts ORDER BY id")]
        quotes = [dict(r) for r in conn.execute("SELECT * FROM price_quotes ORDER BY id")]
        accounts = [dict(r) for r in conn.execute("SELECT name, balance FROM cash_accounts")]
        pending_total = _pending_total(conn)

    total_cash = round(sum(a["balance"] for a in accounts), 2)
    return {
        "pending_payment_requests": pending,
        "pending_total": pending_total,
        "cash_accounts": accounts,
        "cash_after_pending": round(total_cash - pending_total, 2),
        "board_drafts": drafts,
        "price_quotes": quotes,
    }


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str, updated_by: str) -> dict:
    """Set a ticket's status on the board and append a dated note explaining the call.

    status must be one of: open, resolved, awaiting_approval, blocked, needs_info.
    The ticket's original notes are kept; the new note is appended.
    """
    if status not in TICKET_STATUSES:
        return {"error": f"Unknown status '{status}'. Use one of {list(TICKET_STATUSES)}."}
    if not note.strip():
        return {"error": "A note explaining the status change is required."}
    with _connect() as conn:
        today = _today(conn)
        row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"error": f"No ticket with id {ticket_id}."}
        notes = (row["notes"] or "").rstrip()
        entry = f"[{today.isoformat()} {updated_by}] {note.strip()}"
        new_notes = f"{notes}\n{entry}" if notes else entry
        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, new_notes, ticket_id)
        )
        updated = dict(conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
    return {"updated": True, "ticket": updated}


@mcp.tool
def request_payment(
    ticket_id: int, kind: str, ref_id: int, reason: str, requested_by: str, account: str = "checking"
) -> dict:
    """Put a payment in the approval queue for a human. This does NOT pay anything.

    kind is 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id). The amount and
    payee come from the database, never from the caller. Refuses if the bill is already paid,
    already requested, or if cash minus all pending requests could not cover it.
    """
    if kind not in ("invoice", "rent"):
        return {"error": "kind must be 'invoice' or 'rent'."}
    with _connect() as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id {ticket_id}."}

        if kind == "invoice":
            row = conn.execute(
                "SELECT i.amount, i.status, i.due_date, v.name AS payee FROM invoices i "
                "LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,),
            ).fetchone()
            if row is None:
                return {"error": f"No invoice with id {ref_id}."}
            if row["status"] != "open":
                return {"error": f"Invoice {ref_id} is '{row['status']}', not open. Nothing to pay."}
            amount, payee, due = row["amount"], row["payee"], row["due_date"]
        else:
            row = conn.execute(
                "SELECT monthly_rent, landlord, next_due FROM leases WHERE id = ?", (ref_id,)
            ).fetchone()
            if row is None:
                return {"error": f"No lease with id {ref_id}."}
            amount, payee, due = row["monthly_rent"], row["landlord"], row["next_due"]

        rejected = conn.execute(
            "SELECT id, decided_by, reason FROM approval_requests "
            "WHERE kind = ? AND ref_id = ? AND status = 'rejected' ORDER BY id DESC",
            (kind, ref_id),
        ).fetchone()
        if rejected:
            return {
                "error": f"A human ({rejected['decided_by']}) rejected request #{rejected['id']} "
                f"for {kind} {ref_id}. Do not request it again; escalate to Boss instead.",
                "refused": True,
            }

        dup = conn.execute(
            "SELECT id, ticket_id FROM approval_requests "
            "WHERE kind = ? AND ref_id = ? AND status = 'pending'",
            (kind, ref_id),
        ).fetchone()
        if dup:
            return {
                "error": f"{kind} {ref_id} already has pending request #{dup['id']} "
                f"(ticket {dup['ticket_id']}). Do not request it twice."
            }

        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            return {"error": f"No cash account named '{account}'."}
        already_pending = _pending_total(conn, account)
        available = round(acct["balance"] - already_pending, 2)
        if amount > available:
            return {
                "error": "Refused: not enough cash. "
                f"Balance {acct['balance']}, already pending {already_pending}, "
                f"available {available}, this bill {amount}.",
                "refused": True,
            }

        cur = conn.execute(
            "INSERT INTO approval_requests "
            "(ticket_id, kind, ref_id, payee, amount, account, reason, requested_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, kind, ref_id, payee, amount, account, reason, requested_by, today.isoformat()),
        )
        request_id = cur.lastrowid

    return {
        "requested": True,
        "request_id": request_id,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "payee": payee,
        "amount": amount,
        "due_date": due,
        "account": account,
        "cash_after_all_pending": round(available - amount, 2),
        "note": "Waiting for human approval. Nothing has been paid.",
    }


# "$52.20", "$ 52", "52.20 dollars", "52 USD": every way a price can be written.
_MONEY = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)|(\d[\d,]*(?:\.\d{1,2})?)\s?(?:dollars?|usd|bucks)\b", re.IGNORECASE
)


def _unapproved_amounts(conn: sqlite3.Connection, ticket_id: int, text: str) -> list[str]:
    """Dollar amounts in a customer message that are not allowed.

    Allowed, for this ticket only: a quoted unit price or total (from quote_price),
    the list price of the ticket's own SKU or a quoted SKU, and the rent of the
    ticket's own lease (for landlord acknowledgments). Anything else, including
    made-up discounts, other products' prices, and internal unit costs, is refused.
    """
    ticket = conn.execute("SELECT sku, lease_id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    allowed: set[float] = set()
    skus = {ticket["sku"]} if ticket and ticket["sku"] else set()
    for q in conn.execute("SELECT sku, unit_price, total FROM price_quotes WHERE ticket_id = ?", (ticket_id,)):
        allowed.update({round(q["unit_price"], 2), round(q["total"], 2)})
        skus.add(q["sku"])
    for sku in skus:
        row = conn.execute("SELECT list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if row:
            allowed.add(round(row["list_price"], 2))
    if ticket and ticket["lease_id"] is not None:
        row = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone()
        if row:
            allowed.add(round(row["monthly_rent"], 2))
    bad = []
    for groups in _MONEY.findall(text):
        raw = groups[0] or groups[1]
        amount = round(float(raw.replace(",", "")), 2)
        if amount not in allowed:
            bad.append(f"${raw}")
    return bad


def _product_name_problems(conn: sqlite3.Connection, ticket_id: int, text: str) -> list[str]:
    """Product-naming problems in a customer message.

    For a ticket about a product, the message must use that product's exact catalog
    name (inventory.name), must not name a different catalog product, and must not
    show internal SKU codes.
    """
    ticket = conn.execute("SELECT sku FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    catalog = {r["sku"]: r["name"] for r in conn.execute("SELECT DISTINCT sku, name FROM inventory")}
    lowered = text.lower()
    problems = []
    for sku in catalog:
        if sku.lower() in lowered:
            problems.append(f"internal SKU code '{sku}' (use the product name)")
    if ticket and ticket["sku"] in catalog:
        own = catalog[ticket["sku"]]
        if own.lower() not in lowered:
            problems.append(f"the product must be named exactly '{own}'")
        for sku, name in catalog.items():
            if sku != ticket["sku"] and name.lower() in lowered:
                problems.append(f"names a different product, '{name}'")
    return problems


@mcp.tool
def quote_price(
    ticket_id: int, sku: str, qty: int, discount_pct: float, quoted_by: str, size: str | None = None
) -> dict:
    """Price a customer offer and save it on the board. The code does the math from the
    database: unit price = list price x (1 - discount_pct / 100).

    Refuses any price at or below the shop's unit cost, so the shop never sells at a
    loss. Customer messages may only use prices saved here (post_draft checks).
    """
    if qty <= 0:
        return {"error": "qty must be a positive number of units."}
    if not 0 <= discount_pct < 100:
        return {"error": "discount_pct must be at least 0 and below 100."}
    with _connect() as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id {ticket_id}."}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if price is None:
            return {"error": f"No pricing record for {sku}."}
        cost, list_price = price["unit_cost"], price["list_price"]
        unit_price = round(list_price * (1 - discount_pct / 100), 2)
        if unit_price <= cost:
            max_pct = round((1 - cost / list_price) * 100, 2)
            return {
                "error": f"Refused: ${unit_price:.2f} is at or below the unit cost (${cost:.2f}). "
                f"Discounts on {sku} must stay below {max_pct}%.",
                "refused": True,
            }
        total = round(unit_price * qty, 2)
        margin = round(unit_price - cost, 2)
        cur = conn.execute(
            "INSERT INTO price_quotes (ticket_id, sku, size, qty, list_price, unit_cost, discount_pct, "
            "unit_price, total, margin_per_unit, quoted_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, sku, size, qty, list_price, cost, discount_pct, unit_price, total, margin,
             quoted_by, today.isoformat()),
        )
    return {
        "quoted": True,
        "quote_id": cur.lastrowid,
        "ticket_id": ticket_id,
        "sku": sku,
        "size": size,
        "qty": qty,
        "list_price": list_price,
        "discount_pct": discount_pct,
        "unit_price": unit_price,
        "total": total,
        "unit_cost": cost,
        "margin_per_unit": margin,
        "note": "Saved on the board. Customer messages may use this unit price and total.",
    }


@mcp.tool
def post_draft(
    ticket_id: int, kind: str, recipient: str, subject: str, body: str, created_by: str
) -> dict:
    """Post a draft to the board. Nothing is emailed or sent to anyone.

    kind is 'customer_message' (a reply for a customer or requester) or 'purchase_order'
    (a restock order; it waits for human approval and is never sent to a real vendor).
    """
    if kind not in ("customer_message", "purchase_order"):
        return {"error": "kind must be 'customer_message' or 'purchase_order'."}
    if not body.strip():
        return {"error": "Draft body is empty."}
    status = "pending_approval" if kind == "purchase_order" else "draft"
    with _connect() as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id {ticket_id}."}
        if kind == "customer_message":
            naming = _product_name_problems(conn, ticket_id, f"{subject}\n{body}")
            if naming:
                return {
                    "error": "Refused: product naming in the message: " + "; ".join(naming) + ".",
                    "refused": True,
                }
            bad = _unapproved_amounts(conn, ticket_id, f"{subject}\n{body}")
            if bad:
                return {
                    "error": "Refused: the message contains dollar amounts that are not an approved "
                    f"quote, list price, or lease rent for ticket {ticket_id}: {', '.join(bad)}. "
                    "Prices must come from quote_price (which never goes at or below cost).",
                    "refused": True,
                }
        cur = conn.execute(
            "INSERT INTO board_drafts "
            "(ticket_id, kind, recipient, subject, body, created_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, kind, recipient, subject, body, created_by, status, today.isoformat()),
        )
        draft_id = cur.lastrowid
    return {
        "posted": True,
        "draft_id": draft_id,
        "kind": kind,
        "status": status,
        "note": "Saved on the board only. Not sent.",
    }


@mcp.tool
def reserve_stock(ticket_id: int, sku: str, size: str, qty: int, reserved_by: str) -> dict:
    """Set units aside for a ticket by taking them off the shelf count.

    Use only after Boss has made the final call to fill (or partly fill) an order.
    Refuses if qty is not positive, if it is more than is on hand (no negative stock),
    or if this ticket already holds a reservation for this SKU and size.
    """
    if qty <= 0:
        return {"error": "qty must be a positive number of units."}
    with _connect() as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id {ticket_id}."}
        row = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if row is None:
            return {"error": f"No inventory record for {sku} size {size}."}
        dup = conn.execute(
            "SELECT id, qty FROM stock_reservations WHERE ticket_id = ? AND sku = ? AND size = ?",
            (ticket_id, sku, size),
        ).fetchone()
        if dup:
            return {
                "error": f"Ticket {ticket_id} already holds reservation #{dup['id']} "
                f"for {dup['qty']} x {sku} size {size}. Do not reserve twice."
            }
        on_hand = row["qty"]
        if qty > on_hand:
            return {
                "error": f"Refused: only {on_hand} x {sku} size {size} on hand; cannot reserve {qty}.",
                "refused": True,
            }
        conn.execute(
            "UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, sku, size)
        )
        cur = conn.execute(
            "INSERT INTO stock_reservations (ticket_id, sku, size, qty, reserved_by, reserved_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, sku, size, qty, reserved_by, today.isoformat()),
        )
    return {
        "reserved": True,
        "reservation_id": cur.lastrowid,
        "ticket_id": ticket_id,
        "sku": sku,
        "size": size,
        "qty": qty,
        "on_hand_before": on_hand,
        "on_hand_after": on_hand - qty,
    }


@mcp.tool
def pay(request_id: int, approved_by: str) -> dict:
    """Pay an approval request. ONLY the backend calls this, after a human clicks Approve.

    Refuses if the request isn't pending, if approved_by is missing or is an agent,
    or if the account doesn't have enough cash (no negative balances). On success it
    records the payment, lowers the cash balance, and marks the invoice paid or moves
    the lease's next due date forward one month, all in one transaction.
    """
    approver = (approved_by or "").strip()
    if not approver:
        return {"error": "Refused: a human approver name is required."}
    if approver.lower().replace(" ", "_") in AGENT_NAMES:
        return {"error": "Refused: agents cannot approve payments. A human must approve."}

    conn = _connect()
    try:
        today = _today(conn)
        req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"No approval request with id {request_id}."}
        if req["status"] != "pending":
            return {"error": f"Request {request_id} is '{req['status']}', not pending."}

        acct = conn.execute(
            "SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)
        ).fetchone()
        if acct is None:
            return {"error": f"No cash account named '{req['account']}'."}
        if req["amount"] > acct["balance"]:
            return {
                "error": f"Refused: not enough cash. Balance {acct['balance']}, "
                f"payment {req['amount']}. No negative balances.",
                "refused": True,
            }

        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return {"error": f"Invoice {req['ref_id']} is not open; refusing to pay twice."}

        conn.execute("BEGIN")
        new_balance = round(acct["balance"] - req["amount"], 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today.isoformat(), req["account"]),
        )
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], req["ref_id"], req["amount"], req["account"], today.isoformat(), approver),
        )
        payment_id = cur.lastrowid

        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            effect = f"Invoice {req['ref_id']} marked paid."
        else:
            lease = conn.execute(
                "SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)
            ).fetchone()
            next_due = _add_one_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, req["ref_id"]))
            effect = f"Lease {req['ref_id']} next due moved to {next_due}."

        conn.execute(
            "UPDATE approval_requests SET status = 'paid', decided_by = ?, decided_at = ?, "
            "payment_id = ? WHERE id = ?",
            (approver, today.isoformat(), payment_id, request_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "paid": True,
        "payment_id": payment_id,
        "request_id": request_id,
        "amount": req["amount"],
        "account": req["account"],
        "new_balance": new_balance,
        "approved_by": approver,
        "effect": effect,
    }


# ---------------------------------------------------------- human-only tools
# The backend calls these only when a human acts on the dashboard.
# They are filtered out of every agent's toolset in backend/team.py.


def _require_human(name: str) -> str | None:
    who = (name or "").strip()
    if not who:
        return "Refused: a human name is required."
    if who.lower().replace(" ", "_") in AGENT_NAMES:
        return "Refused: agents cannot make this decision. A human must."
    return None


@mcp.tool
def reject_request(request_id: int, rejected_by: str, reason: str) -> dict:
    """Reject a pending payment request (human only). Nothing is paid, and the
    same bill cannot be requested again by an agent.
    """
    refusal = _require_human(rejected_by)
    if refusal:
        return {"error": refusal}
    with _connect() as conn:
        today = _today(conn)
        req = conn.execute("SELECT status FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"No approval request with id {request_id}."}
        if req["status"] != "pending":
            return {"error": f"Request {request_id} is '{req['status']}', not pending."}
        conn.execute(
            "UPDATE approval_requests SET status = 'rejected', decided_by = ?, decided_at = ?, "
            "reason = COALESCE(reason, '') || ? WHERE id = ?",
            (rejected_by.strip(), today.isoformat(), f" | Rejected: {reason.strip()}", request_id),
        )
    return {"rejected": True, "request_id": request_id, "rejected_by": rejected_by.strip()}


@mcp.tool
def decide_draft(draft_id: int, approve: bool, decided_by: str) -> dict:
    """Approve or reject a draft on the board (human only). Approving a customer
    message or purchase order only marks it approved; nothing is sent.
    """
    refusal = _require_human(decided_by)
    if refusal:
        return {"error": refusal}
    with _connect() as conn:
        row = conn.execute("SELECT status FROM board_drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            return {"error": f"No draft with id {draft_id}."}
        if row["status"] in ("approved", "rejected"):
            return {"error": f"Draft {draft_id} is already '{row['status']}'."}
        status = "approved" if approve else "rejected"
        conn.execute("UPDATE board_drafts SET status = ? WHERE id = ?", (status, draft_id))
    return {"draft_id": draft_id, "status": status, "decided_by": decided_by.strip(),
            "note": "Nothing was sent. A human sends approved drafts outside this system."}


@mcp.tool
def reset_shop(confirm: bool, requested_by: str) -> dict:
    """Reset the working database to the original (human only). Wipes the board,
    approvals, drafts, reservations, and payments made since the last reset.
    The original campus_customs.db is only read, never written.
    """
    refusal = _require_human(requested_by)
    if refusal:
        return {"error": refusal}
    if not confirm:
        return {"error": "Pass confirm=true to reset the working database."}
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    with _connect() as conn:
        open_tickets = conn.execute("SELECT COUNT(*) AS n FROM tickets WHERE status = 'open'").fetchone()["n"]
        today = _today(conn).isoformat()
    return {"reset": True, "today": today, "open_tickets": open_tickets}


if __name__ == "__main__":
    mcp.run()
