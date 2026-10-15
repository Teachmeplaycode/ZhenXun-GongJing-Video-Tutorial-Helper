import React, { useState } from 'react'
import Avatar from './Avatar'
import BrowserViewport from './BrowserViewport'
import StreamingText from './StreamingText'
import StepGroup from './StepGroup'
import { IconCheck, IconCopy, IconRefresh } from './Icons'
import { fmtElapsed, fmtTime, frameNo } from '../lib/format'
import { host, isVisibleStep } from '../lib/steps'

const MAX_THUMBS = 5
const URL_RE = /https?:\/\/[^\s<>()（）[\]，。；、"'“”]+/g

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

// Sources the answer cites: links in its text, titled from what the steps searched, read or found.
function collectSources(message) {
  const known = new Map()
  for (const part of message.parts) {
    if (part.kind !== 'steps') continue
    for (const c of part.calls) {
      const d = c.data || {}
      for (const r of d.results || []) if (r.verdict !== 'irrelevant') known.set(r.url, { title: r.title, url: r.url, kind: '网页' })
      if (c.tool === 'web.fetch' && d.url && !d.blocked) known.set(d.url, { title: d.title, url: d.url, kind: '网页' })
      for (const p of d.papers || []) known.set(p.url, { title: p.title, url: p.url, kind: '论文', meta: [p.year, p.venue].filter(Boolean).join(' · ') })
    }
  }
  const cited = []
  const seen = new Set()
  for (const raw of message.text.match(URL_RE) || []) {
    const url = raw.replace(/[.,;:）)]+$/, '')
    if (seen.has(url)) continue
    seen.add(url)
    const match = known.get(url) || [...known.values()].find((k) => url.startsWith(k.url) || k.url.startsWith(url))
    cited.push(match ? { ...match, url } : { title: host(url), url, kind: '链接' })
  }
  return cited
}

function Sources({ sources }) {
  if (!sources.length) return null
  return (
    <div className="sources">
      <span className="sources__label mono-sm">来源 · {sources.length}</span>
      <div className="sources__list">
        {sources.map((s, i) => (
          <a key={s.url} className="source-card" href={s.url} target="_blank" rel="noreferrer" title={s.url} style={{ '--i': i }}>
            <span className="source-card__index mono-sm">{i + 1}</span>
            <span className="source-card__body">
              <span className="source-card__title">{s.title || host(s.url)}</span>
              <span className="source-card__host mono-sm">{s.kind} · {host(s.url)}{s.meta ? ` · ${s.meta}` : ''}</span>
            </span>
          </a>
        ))}
      </div>
    </div>
  )
}

function Footer({ message, onRegenerate }) {
  const [copied, setCopied] = useState(false)
  const done = message.completed
  // The same count the step groups show (model rounds aren't listed as steps).
  const steps = message.parts.reduce((n, p) => n + (p.kind === 'steps' ? p.calls.filter(isVisibleStep).length : 0), 0)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="msg-footer">
      {done ? (
        <span className="msg-footer__meta mono-sm">
          {steps ? `${steps} 步 · ` : ''}{fmtElapsed(done.elapsedMs)}{done.summary ? ` · ${done.summary.split(' · ').slice(-2).join(' · ')}` : ''}
        </span>
      ) : null}
      <span className="msg-footer__actions">
        {message.text ? (
          <button type="button" className="icon-btn" onClick={copy} title="复制回答" aria-label="复制回答">
            {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
          </button>
        ) : null}
        {onRegenerate ? (
          <button type="button" className="icon-btn" onClick={onRegenerate} title="重新回答" aria-label="重新回答"><IconRefresh size={14} /></button>
        ) : null}
      </span>
    </div>
  )
}

// onTime(seconds): a time in the answer was clicked; duration bounds which times count.
// onRegenerate: ask the same question again (null while another answer is running).
export default function MessageBubble({ message, onStop, onTime = null, duration = null, onRegenerate = null }) {
  if (message.role === 'user') {
    return (
      <div className="msg msg--user">
        <div className="bubble bubble--user">
          <Attachments frames={message.attachments} />
          <div className="bubble__text">{message.text}</div>
          {message.options && (message.options.web === false || message.options.papers === false) ? (
            <div className="bubble__options mono-sm">
              {[message.options.web === false && '不联网', message.options.papers === false && '不查论文'].filter(Boolean).join(' · ')}
            </div>
          ) : null}
        </div>
        <Avatar role="user" />
      </div>
    )
  }
  const streaming = message.status === 'running'
  const parts = message.parts
  const lastText = parts.map((p) => p.kind).lastIndexOf('text')
  const settled = message.status !== 'running'
  return (
    <div className="msg msg--assistant">
      <Avatar role="assistant" />
      <div className="bubble bubble--assistant">
        {parts.map((part, i) => (part.kind === 'steps' ? (
          <StepGroup key={part.id} part={part} working={streaming && i === parts.length - 1}
            progress={message.progress?.step} onSeek={onTime} />
        ) : (
          <StreamingText key={`t${i}`} text={part.text} streaming={streaming && i === lastText && i === parts.length - 1}
            onTime={onTime} duration={duration} />
        )))}
        {streaming && !parts.length ? (
          <StepGroup part={{ id: 'pending', calls: [], from: null, to: null }} working progress={message.progress?.step} />
        ) : null}
        {message.browser ? <BrowserViewport session={message.browser} onStop={onStop} /> : null}
        {message.error ? <div className="bubble__error">{message.error}</div> : null}
        {settled ? <Sources sources={collectSources(message)} /> : null}
        {settled ? <Footer message={message} onRegenerate={onRegenerate} /> : null}
      </div>
    </div>
  )
}
