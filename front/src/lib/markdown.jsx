import React from 'react'

// A small Markdown subset rendered straight to React elements (never HTML strings): paragraphs,
// headings, bulleted / numbered lists with indentation, **bold**, *italic*, `code`. Times such as
// [04:34] or 06:10 become buttons that point the timeline at that moment. Partial input from a
// stream renders fine: an unclosed marker simply shows as text until its closing half arrives.

const TIME = /\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?/
const INLINE = new RegExp(
  [
    '`([^`]+)`', // 1 code
    '\\*\\*([^*]+)\\*\\*', // 2 bold
    '(?<![*\\w])\\*([^*\\s][^*]*?)\\*(?![*\\w])', // 3 italic
    '(https?://[^\\s<>()（）\\[\\]，。；、"\'“”]+)', // 4 link — before times, which URLs can contain
    `(?<![\\d:])${TIME.source}(?![\\d:])`, // 5 time
    '第\\s*(\\d{1,3})\\s*张', // 6 a picture of a picture set
  ].join('|'),
  'g',
)

const shortUrl = (url) => {
  try {
    const u = new URL(url)
    const path = u.pathname.length > 1 ? u.pathname.slice(0, 24) + (u.pathname.length > 24 ? '…' : '') : ''
    return u.hostname.replace(/^www\./, '') + path
  } catch {
    return url
  }
}
const LIST = /^(\s*)([-*+•]|\d+[.)])\s+(.*)$/
const HEADING = /^(#{1,6})\s+(.*)$/

export const toSeconds = (stamp) => stamp.split(':').reduce((acc, n) => acc * 60 + Number(n), 0)

function inline(text, ctx, keyBase) {
  const out = []
  let last = 0
  let n = 0
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const key = `${keyBase}-${n++}`
    if (m[1] != null) out.push(<code key={key} className="md-code">{m[1]}</code>)
    else if (m[2] != null) out.push(<strong key={key}>{inline(m[2], ctx, key)}</strong>)
    else if (m[3] != null) out.push(<em key={key}>{inline(m[3], ctx, key)}</em>)
    else if (m[4] != null) {
      const url = m[4].replace(/[.,;:]+$/, '')
      out.push(<a key={key} className="md-link" href={url} target="_blank" rel="noreferrer" title={url}>{shortUrl(url)}</a>)
      if (url.length < m[4].length) out.push(m[4].slice(url.length))
    } else if (m[6] != null) {
      // "第 3 张": in a picture set (ctx.pictures) it points the timeline at that picture
      const n = Number(m[6])
      if (ctx.pictures && ctx.onTime && n >= 1) {
        out.push(<button key={key} type="button" className="ts-chip" onClick={() => ctx.onTime(n - 0.5)} title="在时间轴上看这张图">{m[0]}</button>)
      } else out.push(m[0])
    } else {
      const seconds = toSeconds(m[5])
      // Only moments inside the video; other clock-like numbers stay plain text.
      if (ctx.onTime && seconds <= (ctx.duration ?? Infinity) + 1) {
        out.push(
          <button key={key} type="button" className="ts-chip" onClick={() => ctx.onTime(seconds)} title="在时间轴上定位">
            {m[5]}
          </button>,
        )
      } else out.push(m[0])
    }
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

// Lines → blocks: { kind: 'p' | 'h' | 'li', ... }. Consecutive plain lines form one paragraph.
function blocks(text) {
  const result = []
  let para = null
  for (const raw of text.split('\n')) {
    const line = raw.replace(/\s+$/, '')
    const heading = line.match(HEADING)
    const item = line.match(LIST)
    if (!line.trim()) {
      para = null
    } else if (heading) {
      para = null
      result.push({ kind: 'h', level: heading[1].length, text: heading[2] })
    } else if (item) {
      para = null
      const depth = Math.min(3, Math.floor(item[1].replace(/\t/g, '    ').length / 2))
      const marker = /\d/.test(item[2]) ? item[2].replace(')', '.') : '•'
      result.push({ kind: 'li', depth, marker, text: item[3] })
    } else if (para) {
      para.lines.push(line.trim())
    } else {
      para = { kind: 'p', lines: [line.trim()] }
      result.push(para)
    }
  }
  return result
}

/** Render `text`; `tail` (e.g. a streaming cursor) is placed at the end of the last block. */
export function renderMarkdown(text, { onTime = null, duration = null, tail = null, pictures = false } = {}) {
  const ctx = { onTime, duration, pictures }
  const list = blocks(text || '')
  return list.map((b, i) => {
    const end = i === list.length - 1 ? tail : null
    const key = `b${i}`
    if (b.kind === 'h') {
      return <p key={key} className={`md-h md-h--${Math.min(b.level, 3)}`}>{inline(b.text, ctx, key)}{end}</p>
    }
    if (b.kind === 'li') {
      return (
        <div key={key} className="md-li" style={{ '--depth': b.depth }}>
          <span className="md-li__marker" aria-hidden="true">{b.marker}</span>
          <span>{inline(b.text, ctx, key)}{end}</span>
        </div>
      )
    }
    return (
      <p key={key} className="md-p">
        {b.lines.map((line, j) => (
          <React.Fragment key={j}>{j ? <br /> : null}{inline(line, ctx, `${key}-${j}`)}</React.Fragment>
        ))}
        {end}
      </p>
    )
  })
}
