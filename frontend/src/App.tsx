import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { Bench, deriveSeats } from './components/Bench'
import { Docket } from './components/Docket'
import { Memoranda } from './components/Memoranda'
import { Proceedings } from './components/Proceedings'
import { Register } from './components/Register'
import { Signatures } from './components/Signatures'
import { MATTER, STATUS_WORDS, longDate, matterTitle } from './firm'
import type { AgentEvent, Approvals, Cash, Ticket, TicketSummary } from './types'
import './App.css'

const POLL_MS = 1500

function loadSigner() {
  try {
    return localStorage.getItem('desk-signer') ?? ''
  } catch {
    return ''
  }
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [running, setRunning] = useState<{ runId: string; ticketId: number } | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [approvals, setApprovals] = useState<Approvals | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [lastDebit, setLastDebit] = useState<number | null>(null)
  const [signer, setSigner] = useState(loadSigner)
  const [busy, setBusy] = useState<string | null>(null)
  const [stamped, setStamped] = useState<Record<string, 'approved' | 'declined'>>({})
  const [withReturns, setWithReturns] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const selectedRef = useRef<number | null>(null)
  selectedRef.current = selectedId

  const fail = (e: unknown) => setNotice(e instanceof Error ? e.message : String(e))

  const refreshBoard = useCallback(async () => {
    const [t, a, c] = await Promise.all([api.tickets(), api.approvals(), api.cash()])
    setTickets(t.tickets)
    setApprovals(a)
    setCash(c)
    return t
  }, [])

  // Show a ticket's latest finished run: memos and its transcript.
  const loadTicket = useCallback(async (id: number) => {
    const s = await api.summary(id)
    if (selectedRef.current !== id) return
    setSummary(s)
    if (s.run_id) {
      const ev = await api.events({ run_id: s.run_id })
      if (selectedRef.current === id) setEvents(ev.events)
    } else {
      setEvents([])
    }
  }, [])

  // First load: the board, the first ticket, and any run already in session.
  useEffect(() => {
    refreshBoard()
      .then((t) => {
        const live = t.running
        // ?ticket=103 opens that matter directly (handy for links and screenshots).
        const asked = Number(new URLSearchParams(location.search).get('ticket'))
        const linked = t.tickets.some((x) => x.id === asked) ? asked : null
        const first = live?.ticket_id ?? linked ?? t.tickets[0]?.id ?? null
        setSelectedId(first)
        if (live) setRunning({ runId: live.run_id, ticketId: live.ticket_id })
        else if (first !== null) loadTicket(first).catch(fail)
      })
      .catch(() => setNotice('The desk cannot reach the backend. Start it with: cd backend && uvicorn main:app --reload --port 8000'))
  }, [refreshBoard, loadTicket])

  // While the team is in session, follow its events and watch for the end of the run.
  useEffect(() => {
    if (!running) return
    let stopped = false
    const tick = async () => {
      try {
        const [ev, run] = await Promise.all([api.events({ run_id: running.runId }), api.run(running.runId)])
        if (stopped) return
        if (selectedRef.current === running.ticketId) setEvents(ev.events)
        if (run.status === 'finished' || run.status === 'failed') {
          stopped = true
          setRunning(null)
          if (run.status === 'failed') setNotice(`The run stopped: ${run.error}`)
          await refreshBoard()
          if (selectedRef.current === running.ticketId) await loadTicket(running.ticketId)
        }
      } catch (e) {
        // The backend restarted and forgot the run: stop waiting and show the board as it is.
        if (e instanceof Error && e.message.startsWith('No run')) {
          stopped = true
          setRunning(null)
          setNotice('The run was interrupted (the backend restarted). Reconvene the team to try again.')
          await refreshBoard().catch(() => {})
          return
        }
        fail(e)
      }
    }
    tick()
    const timer = setInterval(() => !stopped && tick(), POLL_MS)
    return () => {
      stopped = true
      clearInterval(timer)
    }
  }, [running, refreshBoard, loadTicket])

  const select = (id: number) => {
    setSelectedId(id)
    setSummary(null)
    setEvents([])
    if (running?.ticketId !== id) loadTicket(id).catch(fail)
  }

  const convene = async (id: number) => {
    setNotice(null)
    try {
      const r = await api.runTicket(id)
      setSummary(null)
      setEvents([])
      setRunning({ runId: r.run_id, ticketId: id })
    } catch (e) {
      fail(e)
    }
  }

  const decide = async (kind: 'payment' | 'purchase_order', id: number, approve: boolean) => {
    const key = `${kind}-${id}`
    setBusy(key)
    setNotice(null)
    try {
      const before = cash?.balance ?? 0
      if (approve) await api.approve(kind, id, signer.trim())
      else await api.reject(kind, id, signer.trim(), 'Declined at the desk')
      setStamped((s) => ({ ...s, [key]: approve ? 'approved' : 'declined' }))
      const board = await refreshBoard()
      const after = (await api.cash()).balance
      setLastDebit(before > after ? before - after : null)
      if (selectedId !== null && board) await loadTicket(selectedId)
    } catch (e) {
      fail(e)
    } finally {
      setBusy(null)
    }
  }

  const resetBooks = async () => {
    const who = signer.trim()
    if (!who) return setNotice('Enter your name under “Signing as” before resetting the books.')
    if (!confirm('Reset the shop to its original records? Approvals, drafts, payments and reservations are wiped.')) return
    try {
      await api.reset(who)
      setStamped({})
      setLastDebit(null)
      setSummary(null)
      setEvents([])
      await refreshBoard()
      setNotice('The books are reset to the original records.')
    } catch (e) {
      fail(e)
    }
  }

  const onSigner = (v: string) => {
    setSigner(v)
    try {
      localStorage.setItem('desk-signer', v)
    } catch {
      /* private mode: the name just isn't remembered */
    }
  }

  const ticket = tickets.find((t) => t.id === selectedId) ?? null
  const live = running !== null && running.ticketId === selectedId
  const seats = useMemo(() => deriveSeats(events), [events])
  const drafts = (approvals?.customer_drafts ?? []).filter((d) => d.ticket_id === selectedId)
  const decision = summary?.decision

  return (
    <div className="desk">
      <header className="masthead">
        <div className="masthead__mark" aria-hidden="true">CC</div>
        <div className="masthead__name">
          <p className="eyebrow">Operations Desk · Est. 2026 · New Haven</p>
          <h1>
            Campus Customs <span className="amp">&amp;</span> Co.
          </h1>
        </div>
        <div className="masthead__side">
          <p className="masthead__date">{cash ? longDate(cash.today) : ' '}</p>
          <button type="button" className="link" onClick={resetBooks} disabled={running !== null}>
            Reset the books
          </button>
        </div>
      </header>

      {notice && (
        <p className="notice" role="status">
          {notice}
          <button type="button" className="link" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </p>
      )}

      <main className="desk__grid">
        <Docket tickets={tickets} selectedId={selectedId} runningId={running?.ticketId ?? null} onSelect={select} />

        <div className="desk__center">
          {ticket ? (
            <>
              <section className="matter" aria-labelledby="matter-title">
                <p className="eyebrow">
                  Matter No. {ticket.id} · {MATTER[ticket.type] ?? ticket.type}
                </p>
                <h2 id="matter-title">{matterTitle(ticket)}</h2>
                <dl className="matter__facts">
                  <div>
                    <dt>Client</dt>
                    <dd>{ticket.requester}</dd>
                  </div>
                  {ticket.sku && (
                    <div>
                      <dt>Asks for</dt>
                      <dd>
                        {ticket.qty} × {ticket.sku}
                        {ticket.size ? `, size ${ticket.size}` : ''}
                      </dd>
                    </div>
                  )}
                  {ticket.lease_id !== null && (
                    <div>
                      <dt>Lease</dt>
                      <dd>No. {ticket.lease_id}</dd>
                    </div>
                  )}
                  {ticket.invoice_id !== null && (
                    <div>
                      <dt>Invoice</dt>
                      <dd>No. {ticket.invoice_id}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Standing</dt>
                    <dd>{live ? 'In session' : STATUS_WORDS[ticket.status]}</dd>
                  </div>
                </dl>
                <blockquote className="matter__note">{ticket.notes?.split('\n')[0]}</blockquote>
                <div className="matter__actions">
                  <button
                    type="button"
                    className="btn btn--primary"
                    onClick={() => convene(ticket.id)}
                    disabled={running !== null}
                  >
                    {live ? 'The team is in session…' : ticket.state === 'open' ? 'Convene the team' : 'Reconvene the team'}
                  </button>
                  {running && !live && <span className="hint">Matter No. {running.ticketId} is in session. One at a time; they share the cash.</span>}
                </div>
              </section>

              <Bench seats={seats} live={live} />

              <Proceedings
                events={events}
                live={live}
                withReturns={withReturns}
                onToggleReturns={() => setWithReturns((v) => !v)}
              />

              {decision && !live && (
                <section className="ruling" aria-labelledby="ruling-title">
                  <p className="eyebrow">The final call</p>
                  <h3 id="ruling-title">{decision.decision}</h3>
                  <p className="ruling__why">{decision.rationale}</p>
                  <p className="ruling__status">
                    <span className="stamp stamp--resolved">Resolved</span>
                    <span>{STATUS_WORDS[decision.status]}</span>
                  </p>
                </section>
              )}

              {!live && <Memoranda summary={summary} drafts={drafts} />}
            </>
          ) : (
            <p className="empty">Choose a matter from the docket.</p>
          )}
        </div>

        <aside className="desk__side">
          <Register cash={cash} lastDebit={lastDebit} />
          <Signatures
            approvals={approvals}
            signer={signer}
            onSigner={onSigner}
            busy={busy}
            stamped={stamped}
            onDecide={decide}
          />
        </aside>
      </main>

      <footer className="colophon">
        Every agent runs on gpt-6-luna via Portkey · shop facts come only from the MCP server · nothing is sent to customers or vendors · every step is in the audit trail
      </footer>
    </div>
  )
}
