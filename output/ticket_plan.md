# Ticket Plan: What We Expect the Team to Do

This is written before the backend is wired. For each open ticket it covers the facts in the database, which agents should work it and in what order, which MCP tools they should call, what should change on the board, where a human must approve, and how the ticket should end. After the run, compare what the team actually did with this plan.

## Starting point (after `reset_shop`)

| Fact | Value | Source |
|---|---|---|
| Shop "today" | 2026-08-31 | `desk.date_today` |
| Cash | checking $3,400 | `cash_accounts` |
| Open bills | Invoice #501, Bulldog Print Co, $840, due 2026-08-28 (**3 days overdue**). Rent for lease 1, Elm City Properties, $2,400, due 2026-09-02 (**2 days away**) | `invoices`, `leases` |
| If both bills are paid | $3,400 − $840 − $2,400 = **$160 left** | |
| Vendors | Bulldog Print Co (apparel, 5 days, **blocked by #501**). Elm City Gifts (mugs and small goods, 3 days). QuickShip CT (courier, 1 day) | `vendors`, `invoices` |
| Payments so far | none | `payments` |

**Order:** Boss works the tickets one at a time, 101 → 102 → 103, so each ticket sees what the earlier ones requested.

**The key link:** invoice #501 affects all three tickets. It blocks the tee for 101, uses cash that 102's rent also needs, and blocks the hoodie restock for 103. It must be requested **once**, on ticket 101, and the other tickets must point to that request rather than make a new one.

---

## Ticket 101: Bulldog tee (customer order)

**The ask:** Tauhid Zaman wants 1 Classic Bulldog Tee (CC-TEE-WHITE), size S. The ticket references invoice 501.

**What the data says:** size S has **0 on hand**. Bulldog Print Co is the apparel vendor, but it **can't ship** while invoice #501 ($840) is open.

**Expected flow**
1. **Boss** reads the ticket and sends Inventory a specific question: stock for CC-TEE-WHITE in size S, and the restock options.
2. **Inventory**:
   - `check_stock("CC-TEE-WHITE", "S")` → 0 on hand, unit cost $8. Shortfall = 1.
   - `list_tickets`: no other ticket wants this tee.
   - `get_vendor_status`: Bulldog Print Co, 5-day lead time, `can_ship = false`, blocked by #501.
   - `list_pending_requests`: no PO is drafted yet.
   - Reports a PO: 1 tee at $8, total $8, arrival unknown, blocked by #501. **No reservation**, since there's nothing to reserve.
3. **Boss → Accounting**: handle the money side.
4. **Accounting**:
   - `get_bills_and_cash` and `list_pending_requests`: $3,400 cash, nothing pending.
   - `request_payment(invoice, 501)` → request **#1**, $840, pending. Cash left after pending: $2,560.
   - `post_draft(purchase_order)` to Bulldog Print Co for 1 tee at $8, status `pending_approval`.
5. **Boss → Customer Service**: draft the reply once the plan is settled.
6. **Customer Service**: `post_draft(customer_message)` to Tauhid Zaman. Size S is out of stock and a restock is being arranged; **no date**. It asks whether they want to wait. No invoices, vendor names or costs.
7. **Boss** makes the final call; the status is recorded with `update_ticket`.

**What Boss does**
1. **Reads** the ticket: type `customer_order`, 1 × CC-TEE-WHITE in size S for Tauhid Zaman, with a reference to invoice 501. A customer order goes to Inventory first, and the invoice reference means money is involved too.
2. **Routes** it to three agents, in order, each with one specific question:
   - Inventory: "Can we fill 1 CC-TEE-WHITE size S? If not, who can restock it, when, and is anything blocking that vendor?"
   - Accounting, after Inventory's answer: "Restock is blocked by invoice #501 ($840, 3 days overdue). Request payment if cash covers it, and post the $8 PO."
   - Customer Service, last, once the plan is settled: "Tell Tauhid size S is out of stock and a restock is being arranged. No date."
   Boss does **not** ask Facilities, since this ticket has nothing to do with the space.
3. **Checks** before deciding: `list_pending_requests` to confirm #501 was requested once (#1) and cash after pending is $2,560, and `list_tickets` to see that 102 and 103 also draw on the same cash and on #501.
4. **Decides:** the tee can't be filled now. Keep the order and wait for approval of #501 and the PO. Promise no date. Nothing to reserve.
5. **Records** it with `update_ticket(101, "awaiting_approval", note)`, with a note that cites 0 on hand, #501 $840 overdue, request #1, and the $8 PO. The backend records it if Boss forgets.

**Boss's judgment call:** paying a $840 overdue invoice to unblock an $8 restock looks lopsided. Boss still backs the request, because #501 is overdue, blocks every apparel restock (including 103's hoodies), and the vendor won't ship until it's paid. Boss requests it; a human decides.

**Expected board changes:** payment request #1 (invoice 501, $840, pending), a PO draft for 1 tee (pending approval), and a customer draft to Tauhid. Cash stays at **$3,400**.

**Expected status:** `awaiting_approval`

**Human approval points:** pay invoice #501, approve the PO, and approve the customer draft.

**After the human decides**
- **#501 approved and paid:** cash → $2,560 (or lower if rent was paid first), #501 → paid, and Bulldog Print Co can ship. If the PO is approved on 2026-08-31, the tee arrives about **2026-09-05** (+5 days). Customer Service then posts a `REVISED` draft with the confirmed date.
- **#501 rejected:** it can't be requested again. The tee stays blocked, and the ticket goes back to Boss to tell Tauhid it isn't available.

**Should NOT happen:** paying #501 without approval, a firm date in the customer message, a guessed SKU, a second request for #501, or mentioning #501 or Bulldog Print Co to the customer.

---

## Ticket 102: Rent due (rent notice)

**The ask:** Elm City Properties says shop rent is due in 2 days. The ticket references lease 1.

**What the data says:** lease 1, Chapel Street shop, landlord Elm City Properties, **$2,400 due 2026-09-02**. That's 2 days after today, so the notice matches.

**Expected flow**
1. **Boss** sends Facilities the rent notice and lease 1.
2. **Facilities**:
   - `get_bills_and_cash`: finds the lease 1 rent.
   - **Checks the notice against the lease:**
     - sender Elm City Properties = landlord ✅
     - "due in 2 days" = 2026-09-02 ✅
     - no different amount or new bank account ✅
   - `list_pending_requests`: rent isn't pending yet. Only #501 from ticket 101 is.
   - Asks Accounting to request the rent.
3. **Accounting**:
   - Checks cash: $3,400 − $840 already pending = $2,560 available, which covers $2,400.
   - `request_payment(rent, lease 1)` → request **#2**, $2,400, pending. Cash left after all pending: **$160**.
4. **Boss** confirms there's no duplicate, makes the final call, and the status is recorded with `update_ticket`.

**What Boss does**
1. **Reads** the ticket: type `rent_notice` from Elm City Properties, lease 1, "rent due in 2 days." A rent notice goes to Facilities.
2. **Routes** it to two agents:
   - Facilities: "Check this notice against lease 1. Is it the right landlord, amount and due date? If it checks out, get the rent requested."
   - Accounting (directly, or through Facilities): "Can cash cover $2,400 on top of what's already pending? If so, request it."
   Boss does **not** ask Inventory or Customer Service. There's no product involved, and no reply to the landlord is needed.
3. **Checks** with `list_pending_requests` that only #501 ($840) is pending and rent isn't, so no duplicate. Then `get_bills_and_cash`: $3,400 cash against $3,240 owed in total, which leaves $160 if both are paid.
4. **Decides:** the notice is real (it matches the lease) and rent is essential because it keeps the shop open. Request the $2,400 rent for approval before 2026-09-02.
5. **Records** it with `update_ticket(102, "awaiting_approval", note)`, citing $2,400 due 2026-09-02, request #2, and $160 left after both pending payments.

**Boss's judgment call:** after both bills, the shop has $160 and no income. Boss still requests rent, because the shop prompt says to never let rent go unpaid if cash allows it, and both bills fit. If cash couldn't cover both, Boss would rank them (the overdue blocking invoice first, then rent), request only what fits, and escalate the rest.

**Expected board changes:** payment request #2 (rent for lease 1, $2,400, pending). No drafts; no reply to the landlord is needed. Cash stays at **$3,400**.

**Expected status:** `awaiting_approval`

**Human approval point:** pay the rent.

**After the human decides**
- **Approved and paid:** cash goes down by $2,400 (to $160 if #501 was also paid), a payment row is recorded with `approved_by`, and lease 1's next due date moves to **2026-10-02**. The ticket is then **resolved**.
- **Rejected:** Boss is told how many days remain before rent is overdue and that the shop space is at risk. The ticket is `blocked`.

**Should NOT happen:** paying rent without approval, a second rent request, passing on a notice that doesn't match the lease, or emailing the landlord.

---

## Ticket 103: Bulk hoodie discount (price override)

**The ask:** Yale AI Club wants **20** navy hoodies (CC-HOOD-NAVY), size M, at a bulk discount.

**What the data says:** **8 on hand** in size M, so the shortfall is 12. Unit cost **$22**, list price **$58**, so the margin is $36 a unit (62%). The restock vendor (Bulldog Print Co) is blocked by #501.

**Expected flow**
1. **Boss** sends Inventory a question about stock for 20 in size M, and Accounting a question about the discount.
2. **Inventory**:
   - `check_stock("CC-HOOD-NAVY", "M")` → 8 on hand, cost $22, list $58.
   - Shortfall is 12.
   - `get_vendor_status`: Bulldog Print Co is blocked by #501.
   - `list_pending_requests`: **#501 is already pending** from ticket 101, so it doesn't ask for it again.
   - A PO for 12 would cost 12 × $22 = **$264**.
3. **Accounting**:
   - `check_stock`, then saves at least two discount options for the 8 available hoodies with `quote_price`, which does the math and **refuses any price at or below $22**. For example:
     - 5% off → $55.10 each, $33.10 margin, $440.80 for 8
     - 10% off → $52.20 each, $30.20 margin, $417.60 for 8
   - It must never price at or below $22.
   - It sees $160 left after pending payments, which is **less than the $264** restock, so the 12-hoodie PO shouldn't be committed now.
4. **Boss** picks the offer (within what the margin supports), then tells Inventory: "final call: reserve the 8."
5. **Inventory**: `reserve_stock(103, CC-HOOD-NAVY, M, 8)` → the shelf count goes 8 → 0, logged against ticket 103.
6. **Customer Service** (once the price is settled): `post_draft(customer_message)` to Yale AI Club. It offers the 8 hoodies at the chosen price with the total, says the other 12 aren't confirmed yet, and asks whether they want the 8 now or would rather wait. No costs, margins, invoices or vendor names.
7. **Boss** makes the final call; the status is recorded with `update_ticket`.

**What Boss does**
1. **Reads** the ticket: type `price_override`, Yale AI Club, 20 × CC-HOOD-NAVY size M, asking for a bulk discount. A discount request needs Inventory (do we have 20?) and Accounting (what price works?).
2. **Routes** it to three agents:
   - Inventory and Accounting, with separate questions:
     - Inventory: "How many CC-HOOD-NAVY size M can we supply, and can we restock the rest?"
     - Accounting: "What bulk discount can the margin support on CC-HOOD-NAVY size M? Give options above cost."
   - Inventory again, **only after the final call**: "Final call: reserve the 8 hoodies for ticket 103."
   - Customer Service, last, once the price is chosen: "Offer the 8 at $<price> each with the total. The other 12 aren't confirmed. Ask the club to choose."
   Boss does **not** ask Facilities.
3. **Checks** with `list_pending_requests` that #501 is **already pending** from ticket 101, so no one requests it again for the hoodie restock. Cash after pending is $160, which is less than the $264 a 12-hoodie restock would cost.
4. **Decides:**
   - **Price:** picks one of Accounting's options, keeping it above the $22 cost (for example, 10% off = $52.20). A bigger order earns a better price, but Boss doesn't go deeper than Accounting recommends.
   - **Quantity:** offers only the 8 in stock. It doesn't promise the other 12, because the restock is blocked by #501 and couldn't be paid for anyway.
   - **No PO** for 12 hoodies now, and **no new payment request**.
   - Reserves the 8, so another ticket can't promise them.
5. **Records** it with `update_ticket(103, "needs_info", note)`, citing 8 of 20 available, the chosen price and total, 8 reserved, and the 12 not confirmed because of #501 and cash. The status is `needs_info` because the club has to choose.

**Boss's judgment call:** Boss could simply turn the club away, or promise all 20 to win the sale. Instead it offers the honest middle: 8 hoodies now at a fair bulk price, and lets the customer decide. It reserves stock only once that's the final call, and it flags to the human that a full 20 would need #501 paid **and** more cash than the shop will have.

**Expected board changes:** a reservation of 8 hoodies in size M for ticket 103 (shelf → 0) and a customer draft to Yale AI Club. **No new payment request**, because #501 is already pending. **No 12-hoodie PO**, because the restock is blocked and not affordable after pending payments. Cash stays at **$3,400**.

**Expected status:** `needs_info`, since the customer has to choose between 8 now or waiting.

**Human approval point:** approve the customer draft. No payment is needed for this ticket.

**After the human decides**
- **The customer takes 8:** the reserved units are theirs, and the ticket can be resolved for those 8.
- **They want all 20:** the 12-hoodie restock needs #501 paid *and* $264 the shop won't have once both bills are paid ($160). This is a cash problem only a human can settle, so it's escalated (`blocked`).

**Should NOT happen:** promising all 20, a price at or below $22 cost, a second request for #501, a PO the cash can't cover, reserving more than 8, or reserving before Boss's final call.

---

## Expected end state of a full run

| | Expected |
|---|---|
| Ticket statuses | 101 `awaiting_approval`, 102 `awaiting_approval`, 103 `needs_info` |
| Payment requests | **2**: #1 invoice 501 ($840) and #2 rent lease 1 ($2,400), both pending. Nothing for 103 |
| Pending total / cash after pending | $3,240 / **$160** |
| Payments made | **0** (no human has approved yet) |
| Cash | **$3,400** (unchanged) |
| Drafts | a customer message to Tauhid Zaman, a PO for 1 tee in size S, and a customer message to Yale AI Club |
| Reservations | 8 × CC-HOOD-NAVY size M for ticket 103 |
| Messages sent / vendors contacted | **none** |
| Model in the audit trail | only `gpt-6-luna` |

## If the human approves everything
Paying #501 and the rent leaves **$160** in checking. Both bills are recorded in `payments` with the approver's name, #501 is marked paid, lease 1 is next due 2026-10-02, and Bulldog Print Co can ship again. Ticket 102 is resolved. Ticket 101 moves forward once its PO is approved, with the tee due about 5 days later. Ticket 103 still needs the club's answer, and the 12-hoodie restock still can't be afforded.
