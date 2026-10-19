import React from 'react'
import { renderMarkdown } from '../lib/markdown'
import { SEEK_TITLE, useEvidence } from '../lib/evidence'

// §9.2 assistant.message.delta — the answer so far, rendered as Markdown, with a blinking block
// cursor while streaming. onTime(seconds): a time in the answer was clicked.
export default function StreamingText({ text, streaming, onTime = null, duration = null, pictures = false, evidence = null }) {
  const cursor = streaming ? <span className="streaming-text__cursor" aria-hidden="true">█</span> : null
  const source = useEvidence() // how moments can be looked at again: original / cache / none
  // The answer's citations as checked by the backend: marker → {ok, reason}; while streaming, none yet.
  const checked = Object.fromEntries((evidence?.items || []).map((i) => [i.marker, i]))
  const body = renderMarkdown(text, { onTime: source.state === 'none' ? null : onTime, duration, tail: cursor, pictures,
    seekTitle: SEEK_TITLE[source.state], checked })
  return <div className="streaming-text">{body.length ? body : cursor}</div>
}
