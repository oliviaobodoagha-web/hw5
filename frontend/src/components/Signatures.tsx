// Awaiting Your Signature: the only place money moves, and only on a human's signature.

import { money } from '../firm'
import type { Approvals } from '../types'

type Kind = 'payment' | 'purchase_order'

export function Signatures({
  approvals,
  signer,
  onSigner,
  busy,
  stamped,
  onDecide,
}: {
  approvals: Approvals | null
  signer: string
  onSigner: (v: string) => void
  busy: string | null
  stamped: Record<string, 'approved' | 'declined'>
  onDecide: (kind: Kind, id: number, approve: boolean) => void
}) {
  const items = [
    ...(approvals?.payments ?? []).map((p) => ({
      key: `payment-${p.id}`,
      kind: 'payment' as Kind,
      id: p.id,
      title: p.kind === 'rent' ? `Rent to ${p.payee}` : `Invoice #${p.ref_id} to ${p.payee}`,
      amount: p.amount,
      note: p.reason,
      ticket: p.ticket_id,
    })),
    ...(approvals?.purchase_orders ?? []).map((d) => ({
      key: `purchase_order-${d.id}`,
      kind: 'purchase_order' as Kind,
      id: d.id,
      title: `Purchase order to ${d.recipient}`,
      amount: null,
      note: d.body,
      ticket: d.ticket_id,
    })),
  ]
  const canSign = signer.trim().length > 1

  return (
    <section className="signatures" aria-labelledby="sig-title">
      <header className="section-head">
        <h3 id="sig-title">Awaiting Your Signature</h3>
        <span className="count">{items.length}</span>
      </header>
      <label className="signer">
        <span>Signing as</span>
        <input value={signer} onChange={(e) => onSigner(e.target.value)} placeholder="Your name" autoComplete="name" />
      </label>
      {items.length === 0 && Object.keys(stamped).length === 0 && <p className="empty">Nothing to sign.</p>}
      <ul>
        {items.map((it) => (
          <li key={it.key} className="sig">
            <p className="sig__title">
              {it.title}
              <span className="sig__docket">No. {it.ticket}</span>
            </p>
            {it.amount !== null && <p className="sig__amount">{money(it.amount)}</p>}
            {it.note && <p className="sig__note">{it.note}</p>}
            <p className="sig__kind">
              {it.kind === 'payment' ? 'Signing pays this from checking.' : 'Approving moves no cash; nothing is sent.'}
            </p>
            <div className="sig__actions">
              <button
                type="button"
                className="btn btn--sign"
                disabled={!canSign || busy !== null}
                onClick={() => onDecide(it.kind, it.id, true)}
              >
                {busy === it.key ? 'Signing…' : 'Sign & approve'}
              </button>
              <button
                type="button"
                className="btn btn--quiet"
                disabled={!canSign || busy !== null}
                onClick={() => onDecide(it.kind, it.id, false)}
              >
                Decline
              </button>
            </div>
            <span className="sig__line" aria-hidden="true">
              {signer || ' '}
            </span>
          </li>
        ))}
        {Object.entries(stamped).map(([key, how]) => (
          <li key={key} className="sig sig--done">
            <span className={`stamp stamp--big stamp--${how}`}>{how === 'approved' ? 'Approved' : 'Declined'}</span>
            <span className="sig__done-note">{key.replace('-', ' #').replace('_', ' ')}</span>
          </li>
        ))}
      </ul>
      {!canSign && items.length > 0 && <p className="hint">Enter your name to sign.</p>}
    </section>
  )
}
