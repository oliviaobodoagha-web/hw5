// The Register: the checking account, written up like a checkbook ledger.

import { useEffect, useRef, useState } from 'react'
import { money } from '../firm'
import type { Cash } from '../types'

// Count the balance down when a payment clears, so the drop is visible.
function useCountTo(target: number | undefined) {
  const [shown, setShown] = useState(target ?? 0)
  const from = useRef(target ?? 0)
  useEffect(() => {
    if (target === undefined) return
    const start = from.current
    if (start === target) return
    const t0 = performance.now()
    let frame = 0
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / 1100)
      const eased = 1 - Math.pow(1 - k, 3)
      setShown(start + (target - start) * eased)
      if (k < 1) frame = requestAnimationFrame(step)
      else from.current = target
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [target])
  return shown
}

export function Register({ cash, lastDebit }: { cash: Cash | null; lastDebit: number | null }) {
  const shown = useCountTo(cash?.balance)
  if (!cash) return null
  const paid = cash.register.reduce((s, p) => s + p.amount, 0)
  let running = cash.balance + paid
  const opening = running
  return (
    <section className="register" aria-labelledby="reg-title">
      <header className="section-head">
        <h3 id="reg-title">The Register</h3>
        <span className="count">Checking</span>
      </header>
      <p className="balance" aria-live="polite">
        <span className="balance__label">Balance</span>
        <span className="balance__figure">{money(shown)}</span>
        {lastDebit !== null && <span className="balance__debit">−{money(lastDebit)}</span>}
      </p>
      <table className="ledger">
        <thead>
          <tr>
            <th>Entry</th>
            <th className="num">Debit</th>
            <th className="num">Balance</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Opening balance</td>
            <td className="num" />
            <td className="num">{money(opening)}</td>
          </tr>
          {cash.register.map((p) => {
            running -= p.amount
            return (
              <tr key={p.id}>
                <td>
                  {p.kind === 'rent' ? `Rent, lease ${p.ref_id}` : `Invoice #${p.ref_id}`}
                  <small>signed by {p.approved_by}</small>
                </td>
                <td className="num debit">{money(p.amount)}</td>
                <td className="num">{money(running)}</td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr>
            <td>Pending signature</td>
            <td className="num">{cash.pending_total ? money(cash.pending_total) : '—'}</td>
            <td className="num">{money(cash.balance_after_pending)}</td>
          </tr>
        </tfoot>
      </table>
      <p className="fine">No revenue is booked; cash only goes out. Payments never take the balance below zero.</p>
    </section>
  )
}
