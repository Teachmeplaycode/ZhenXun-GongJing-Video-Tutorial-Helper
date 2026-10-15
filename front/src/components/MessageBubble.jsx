import React from 'react'
import Avatar from './Avatar'
import ProgressPill from './ProgressPill'
import TraceGroup from './TraceGroup'
import BrowserViewport from './BrowserViewport'
import StreamingText from './StreamingText'
import CompletionBanner from './CompletionBanner'
import { fmtTime, frameNo } from '../lib/format'

const MAX_THUMBS = 5

function Attachments({ frames }) {
  if (!frames?.length) return null
  if (frames.length > MAX_THUMBS) {
    return <div className="attach-summary">已选 {frames.length} 帧 · {fmtTime(frames[0].time)} – {fmtTime(frames[frames.length - 1].time)}</div>
  }
  return (
    <div className="attach-row">
      {frames.map((f) => (
        <figure key={f.index} className="attach-thumb">
          <img src={f.src} alt={frameNo(f.index)} />
          <figcaption>{fmtTime(f.time)}</figcaption>
        </figure>
      ))}
    </div>
  )
}

// onTime(seconds): a time in the answer was clicked; duration bounds which times count.
export default function MessageBubble({ message, onStop, onTime = null, duration = null }) {
  if (message.role === 'user') {
    return (
      <div className="msg msg--user">
        <div className="bubble bubble--user">
          <Attachments frames={message.attachments} />
          <div className="bubble__text">{message.text}</div>
        </div>
        <Avatar role="user" />
      </div>
    )
  }
  const streaming = message.status === 'running'
  return (
    <div className="msg msg--assistant">
      <Avatar role="assistant" />
      <div className="bubble bubble--assistant">
        {message.progress ? <ProgressPill step={message.progress.step} percent={message.progress.percent} /> : null}
        <TraceGroup calls={message.calls} />
        {message.browser ? <BrowserViewport session={message.browser} onStop={onStop} /> : null}
        {message.text || streaming ? <StreamingText text={message.text} streaming={streaming} onTime={onTime} duration={duration} /> : null}
        {message.error ? <div className="bubble__error">{message.error}</div> : null}
        {message.completed ? <CompletionBanner {...message.completed} /> : null}
      </div>
    </div>
  )
}
