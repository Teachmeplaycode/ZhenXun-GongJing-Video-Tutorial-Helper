import React, { useState } from 'react'
import ToolCallCard from './ToolCallCard'
import { IconChevron } from './Icons'

const GROUP_THRESHOLD = 10

// Renders tool calls as collapsed cards; 10+ calls fold into a single "N 步操作" row (§9.2 ui_rules).
export default function TraceGroup({ calls }) {
  const [open, setOpen] = useState(false)
  if (!calls.length) return null
  if (calls.length < GROUP_THRESHOLD) {
    return <div className="trace">{calls.map((c) => <ToolCallCard key={c.id} call={c} />)}</div>
  }
  const running = calls.some((c) => c.status === 'running')
  return (
    <div className="trace">
      <button type="button" className="trace__group" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className={`tool-card__chevron ${open ? 'is-open' : ''}`}><IconChevron size={12} /></span>
        {calls.length} 步操作{running ? ' · 运行中...' : ''}
      </button>
      {open ? calls.map((c) => <ToolCallCard key={c.id} call={c} />) : null}
    </div>
  )
}
