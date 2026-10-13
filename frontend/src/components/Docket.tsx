// The Docket: every ticket as a case file.

import { MATTER, STATUS_WORDS } from '../firm'
import type { Ticket } from '../types'

export function Docket({
  tickets,
  selectedId,
  runningId,
  onSelect,
}: {
  tickets: Ticket[]
  selectedId: number | null
  runningId: number | null
  onSelect: (id: number) => void
}) {
  const open = tickets.filter((t) => t.state === 'open').length
  return (
    <nav className="docket" aria-label="The docket">
      <header className="section-head">
        <h3>The Docket</h3>
        <span className="count">
          {open} open · {tickets.length - open} resolved
        </span>
      </header>
      <ul>
        {tickets.map((t) => (
          <li key={t.id}>
            <button
              type="button"
              className={`folder${t.id === selectedId ? ' folder--active' : ''}`}
              aria-current={t.id === selectedId}
              onClick={() => onSelect(t.id)}
            >
              <span className="folder__tab">No. {t.id}</span>
              <span className="folder__kind">{MATTER[t.type] ?? t.type}</span>
              <span className="folder__subject">{t.subject}</span>
              <span className="folder__from">from {t.requester}</span>
              <span className="folder__foot">
                {t.id === runningId ? (
                  <span className="stamp stamp--live">In session</span>
                ) : (
                  <span className={`stamp stamp--${t.state}`}>{t.state === 'open' ? 'Open' : 'Resolved'}</span>
                )}
                {t.state === 'resolved' && t.status !== 'resolved' && (
                  <span className="folder__next">{STATUS_WORDS[t.status]}</span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
