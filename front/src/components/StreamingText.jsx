import React from 'react'
import { renderMarkdown } from '../lib/markdown'
import { SEEK_TITLE, useEvidence } from '../lib/evidence'

// §9.2 assistant.message.delta — the answer so far, rendered as Markdown, with a blinking block
// cursor while streaming. onTime(seconds): a time in the answer was clicked.
export default function StreamingText({ text, streaming, onTime = null, duration = null, pictures = false }) {
  const cursor = streaming ? <span className="streaming-text__cursor" aria-hidden="true">█</span> : null
  const evidence = useEvidence()
  const body = renderMarkdown(text, { onTime: evidence.state === 'none' ? null : onTime, duration, tail: cursor, pictures, seekTitle: SEEK_TITLE[evidence.state] })
  return <div className="streaming-text">{body.length ? body : cursor}</div>
}
