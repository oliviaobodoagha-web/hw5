// Memoranda: what each agent did on this matter, plus the correspondence drafted.

import { AGENTS, agentTitle, toolWords } from '../firm'
import type { Draft, TicketSummary } from '../types'

export function Memoranda({ summary, drafts }: { summary: TicketSummary | null; drafts: Draft[] }) {
  if (!summary?.run_id) return null
  const seated = AGENTS.filter((a) => summary.agents.some((m) => m.agent === a.name))
  const notCalled = AGENTS.filter((a) => !summary.agents.some((m) => m.agent === a.name))
  return (
    <section className="memoranda" aria-labelledby="memo-title">
      <header className="section-head">
        <h3 id="memo-title">Memoranda</h3>
        <span className="count">
          {seated.length} of 5 called
          {summary.tokens ? ` · ${Math.round(summary.tokens / 1000)}k tokens` : ''}
        </span>
      </header>
      <div className="memo-grid">
        {seated.map((a) => {
          const m = summary.agents.find((x) => x.agent === a.name)!
          return (
            <article key={a.name} className="memo">
              <p className="memo__head">
                <span className="memo__from">From: {a.title}</span>
                <span className="memo__role">{a.role}</span>
              </p>
              <p className="memo__body">{m.memo ?? 'No report filed.'}</p>
              <p className="memo__meta">
                {m.asked.length > 0 && <>Asked {m.asked.map(agentTitle).join(', ')}. </>}
                {m.tools.length > 0 && <>Tools: {m.tools.map(toolWords).join(', ')}.</>}
              </p>
            </article>
          )
        })}
      </div>
      {notCalled.length > 0 && (
        <p className="not-called">Not called on this matter: {notCalled.map((a) => a.title).join(', ')}.</p>
      )}
      {drafts.length > 0 && (
        <div className="letters">
          <p className="eyebrow">Correspondence on file · drafts, not sent</p>
          {drafts.map((d) => (
            <article key={d.id} className="letter">
              <p className="letter__to">To {d.recipient}</p>
              <p className="letter__re">Re: {d.subject}</p>
              <p className="letter__body">{d.body}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
