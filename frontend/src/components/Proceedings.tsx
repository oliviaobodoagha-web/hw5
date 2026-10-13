// The Proceedings: a court-reporter transcript of the run, newest at the bottom.

import { useEffect, useRef } from 'react'
import { agentTitle, clock, toolWords, STATUS_WORDS } from '../firm'
import type { AgentEvent, Ticket } from '../types'

interface Line {
  seq: number
  at: string
  who: string
  kind: 'said' | 'asked' | 'tools' | 'ruling' | 'refused' | 'error' | 'return'
  text: string
  tools?: string[]
}

function toLines(events: AgentEvent[], withReturns: boolean): Line[] {
  const lines: Line[] = []
  for (const e of events) {
    const who = agentTitle(e.agent)
    const base = { seq: e.seq, at: e.at, who }
    switch (e.event) {
      case 'delegation':
        lines.push({ ...base, kind: 'asked', who: `${who} → ${agentTitle(e.to_agent)}`, text: e.said ?? '' })
        break
      case 'reply':
        lines.push({ ...base, kind: 'said', text: e.said ?? '' })
        break
      case 'model_response': {
        const tools = e.tools.filter((t) => t !== 'ask_teammate')
        if (e.said) lines.push({ ...base, kind: 'said', text: e.said })
        if (tools.length) lines.push({ ...base, kind: 'tools', text: tools.map(toolWords).join('; '), tools })
        break
      }
      case 'tool_result':
        if (withReturns && e.tools[0] !== 'ask_teammate') {
          lines.push({ ...base, kind: 'return', who: `${who} · ${e.tools[0]}`, text: e.said ?? '' })
        }
        break
      case 'delegation_refused':
        lines.push({ ...base, kind: 'refused', text: e.said ?? '' })
        break
      case 'ticket_decision': {
        const m = /^\[(\w+)\]\s*(.*)$/s.exec(e.said ?? '')
        const status = (m?.[1] ?? '') as Ticket['status']
        lines.push({ ...base, kind: 'ruling', who: 'Ruling', text: `${STATUS_WORDS[status] ?? status}. ${m?.[2] ?? e.said ?? ''}` })
        break
      }
      case 'error':
        lines.push({ ...base, kind: 'error', who: 'Clerk', text: e.said ?? 'The run stopped with an error.' })
        break
    }
  }
  return lines
}

export function Proceedings({
  events,
  live,
  withReturns,
  onToggleReturns,
}: {
  events: AgentEvent[]
  live: boolean
  withReturns: boolean
  onToggleReturns: () => void
}) {
  const lines = toLines(events, withReturns)
  const end = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (live) end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [lines.length, live])

  return (
    <section className="proceedings" aria-labelledby="proceedings-title">
      <header className="section-head">
        <h3 id="proceedings-title">The Proceedings</h3>
        <label className="toggle">
          <input type="checkbox" checked={withReturns} onChange={onToggleReturns} />
          Show tool returns
        </label>
      </header>
      {lines.length === 0 ? (
        <p className="empty">No proceedings yet. Convene the team to begin.</p>
      ) : (
        <ol className="transcript" aria-live={live ? 'polite' : 'off'}>
          {lines.map((l, i) => (
            <li key={`${l.seq}-${i}`} className={`tline tline--${l.kind}`}>
              <time>{clock(l.at)}</time>
              <span className="tline__who">{l.who}</span>
              <span className="tline__text">{l.kind === 'tools' ? <em>{l.text}</em> : l.text}</span>
            </li>
          ))}
          {live && (
            <li ref={end} className="tline tline--cursor" aria-hidden="true">
              <time />
              <span className="tline__who" />
              <span className="tline__text">
                <span className="caret">▍</span>
              </span>
            </li>
          )}
        </ol>
      )}
    </section>
  )
}
