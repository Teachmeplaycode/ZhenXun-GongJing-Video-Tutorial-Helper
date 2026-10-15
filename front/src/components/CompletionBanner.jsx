import React from 'react'
import { fmtElapsed } from '../lib/format'

// §9.2 run.completed — black info block.
export default function CompletionBanner({ steps, elapsedMs, summary }) {
  return (
    <div className="completion">
      <span className="completion__label">RUN COMPLETE</span>
      <span>{steps} 步</span>
      <span className="completion__sep">·</span>
      <span>{fmtElapsed(elapsedMs)}</span>
      {summary ? <><span className="completion__sep">·</span><span>{summary}</span></> : null}
    </div>
  )
}
