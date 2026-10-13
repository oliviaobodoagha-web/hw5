// The Bench: one seat per agent, lit by what that agent is doing right now.

import { AGENTS, agentTitle, toolWords } from '../firm'
import type { AgentEvent, AgentName } from '../types'

export type SeatState = 'idle' | 'called' | 'working' | 'waiting' | 'done'
export interface Seat {
  state: SeatState
  line: string
  tools: number
}

const IDLE: Seat = { state: 'idle', line: 'Not called on this matter', tools: 0 }

// Replay a run's events into the current state of each seat.
export function deriveSeats(events: AgentEvent[]): Record<AgentName, Seat> {
  const seats = Object.fromEntries(AGENTS.map((a) => [a.name, { ...IDLE }])) as Record<AgentName, Seat>
  for (const e of events) {
    const me = e.agent ? seats[e.agent] : undefined
    switch (e.event) {
      case 'agent_start':
        if (me) Object.assign(me, { state: 'working', line: 'Reviewing the file' })
        break
      case 'model_response': {
        const tools = e.tools.filter((t) => t !== 'ask_teammate')
        if (me && tools.length) {
          me.tools += tools.length
          Object.assign(me, { state: 'working', line: tools.map(toolWords).join(' · ') })
        }
        break
      }
      case 'delegation':
        if (me && e.to_agent) Object.assign(me, { state: 'waiting', line: `Waiting on ${agentTitle(e.to_agent)}` })
        if (e.to_agent) Object.assign(seats[e.to_agent], { state: 'called', line: `Called in by ${agentTitle(e.agent)}` })
        break
      case 'agent_output':
        if (me) Object.assign(me, { state: 'done', line: 'Reported back' })
        break
      case 'ticket_decision':
        Object.assign(seats.boss, { state: 'done', line: 'Made the final call' })
        break
    }
  }
  return seats
}

const STATE_LABEL: Record<SeatState, string> = {
  idle: 'At rest',
  called: 'Called in',
  working: 'At work',
  waiting: 'Waiting',
  done: 'Done',
}

export function Bench({ seats, live }: { seats: Record<AgentName, Seat>; live: boolean }) {
  return (
    <ol className="bench" aria-label="The team">
      {AGENTS.map((a) => {
        const seat = seats[a.name]
        return (
          <li key={a.name} className={`seat seat--${seat.state}${live && seat.state === 'working' ? ' seat--live' : ''}`}>
            <span className="seat__monogram" aria-hidden="true">{a.initials}</span>
            <span className="seat__name">{a.title}</span>
            <span className="seat__role">{a.role}</span>
            <span className="seat__state">{STATE_LABEL[seat.state]}</span>
            <span className="seat__line">{seat.line}</span>
          </li>
        )
      })}
    </ol>
  )
}
