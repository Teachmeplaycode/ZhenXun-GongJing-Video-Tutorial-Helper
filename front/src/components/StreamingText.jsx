import React from 'react'

// §9.2 assistant.message.delta — appended text with a blinking block cursor while streaming.
export default function StreamingText({ text, streaming }) {
  return (
    <div className="streaming-text">
      {text}
      {streaming ? <span className="streaming-text__cursor" aria-hidden="true">█</span> : null}
    </div>
  )
}
