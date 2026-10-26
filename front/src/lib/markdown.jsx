import React from 'react'

// A small Markdown subset rendered straight to React elements (never HTML strings): paragraphs,
// headings, bulleted / numbered lists with indentation, tables, code blocks, quotes, rules,
// **bold**, *italic*, `code`. Times such as
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
    // 7, 8 a typed citation (backend modules/agent/evidence.py): [画面 01:19] [原声 01:13-01:24]
    // [画面文字 01:26] [资料 https://…] [知识] [推断]. It starts at its "[", before any time or link inside it.
    '\\[(画面文字|画面|原声|资料|知识|推断)([^\\[\\]\\n]*)\\]',
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
    } else if (m[7] != null) {
      out.push(<Evidence key={key} kind={m[7]} rest={m[8].trim()} marker={m[0]} ctx={ctx} />)
    } else if (m[6] != null) {
      // "第 3 张": in a picture set (ctx.pictures) it points the timeline at that picture
      const n = Number(m[6])
      if (ctx.pictures && ctx.onTime && n >= 1) {
        out.push(<button key={key} type="button" className="ts-chip" onClick={() => ctx.onTime(n - 0.5)} title="在时间轴上看这张图">{m[0]}</button>)
      } else out.push(m[0])
    } else {
      const seconds = toSeconds(m[5])
      const check = ctx.checked?.[m[0]]
      // Only moments inside the video; other clock-like numbers stay plain text.
      if (check && !check.ok) {
        out.push(<span key={key} className="ts-chip is-missing" title={`该结论缺少可回看的证据：${check.reason}`}>{m[5]}</span>)
      } else if (ctx.onTime && seconds <= (ctx.duration ?? Infinity) + 1) {
        out.push(
          <button key={key} type="button" className="ts-chip" onClick={() => ctx.onTime(seconds)} title={ctx.seekTitle || '在时间轴上定位'}>
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

const KIND = { 画面: 'frame', 原声: 'speech', 画面文字: 'screentext', 资料: 'source', 知识: 'knowledge', 推断: 'inference' }
const KIND_TITLE = { 画面: '原片画面', 原声: '视频原声（语音转写）', 画面文字: '画面里的文字（文字识别）' }

// One typed citation: what kind of evidence, when, and whether it held up when the answer was checked.
function Evidence({ kind, rest, marker, ctx }) {
  const check = ctx.checked?.[marker]
  const failed = check && !check.ok
  const cls = `ev-chip ev-chip--${KIND[kind]}${failed ? ' is-missing' : ''}`
  if (kind === '推断') return <span className={cls} title="没有直接证据，是根据视频内容推出的判断">推断</span>
  if (kind === '知识') return <span className={cls} title="模型自己的知识：不是视频里讲的，也没有在这次回答里联网核实">知识</span>
  if (kind === '资料') {
    const url = (rest.match(/https?:\/\/\S+/) || [''])[0].replace(/[.,;:]+$/, '')
    if (failed || !url) return <span className={cls} title={`该结论缺少可核对的资料：${check?.reason || '没有给出链接'}`}>资料{url ? ` · ${shortUrl(url)}` : ''}</span>
    return <a className={cls} href={url} target="_blank" rel="noreferrer" title={`外部资料（不是视频内容）：${url}`}>资料 · {shortUrl(url)}</a>
  }
  const stamp = rest.match(TIME_IN)
  const seconds = stamp ? toSeconds(stamp[1]) : null
  const label = `${kind} ${rest}`.trim()
  if (failed || seconds == null || !ctx.onTime || seconds > (ctx.duration ?? Infinity) + 1) {
    return <span className={`${cls} is-missing`} title={`该结论缺少可回看的证据：${check?.reason || '没有可回看的时间点'}`}>{label}</span>
  }
  return (
    <button type="button" className={cls} onClick={() => ctx.onTime(seconds)} title={`${KIND_TITLE[kind]} · ${ctx.seekTitle || '在时间轴上定位'}`}>
      {label}
    </button>
  )
}
const TIME_IN = /(\d{1,2}:\d{2}(?::\d{2})?)/

// Lines → blocks: { kind: 'p' | 'h' | 'li' | 'code' | 'table' | 'quote' | 'hr', ... }. Consecutive plain lines form one paragraph.
const FENCE = /^\s*```\s*([\w+-]*)\s*$/
const ROW = /^\s*\|(.*)\|\s*$/
const RULE_ROW = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/
const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())

function blocks(text) {
  const result = []
  let para = null
  let code = null
  const lines = text.split('\n')
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].replace(/\s+$/, '')
    if (code) { // inside a fenced block until its closing fence (a stream may not have it yet)
      if (FENCE.test(line)) code = null
      else code.lines.push(lines[i])
      continue
    }
    const fence = line.match(FENCE)
    const heading = line.match(HEADING)
    const item = line.match(LIST)
    if (fence) {
      para = null
      code = { kind: 'code', lang: fence[1], lines: [] }
      result.push(code)
    } else if (ROW.test(line) && i + 1 < lines.length && RULE_ROW.test(lines[i + 1])) {
      para = null
      const table = { kind: 'table', head: cells(line), rows: [] }
      i += 1
      while (i + 1 < lines.length && ROW.test(lines[i + 1])) { i += 1; table.rows.push(cells(lines[i])) }
      result.push(table)
    } else if (!line.trim()) {
      para = null
    } else if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      para = null
      result.push({ kind: 'hr' })
    } else if (/^\s*>\s?/.test(line)) {
      const quoted = line.replace(/^\s*>\s?/, '')
      const last = result[result.length - 1]
      if (last?.kind === 'quote' && !para) last.lines.push(quoted)
      else result.push({ kind: 'quote', lines: [quoted] })
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
export function renderMarkdown(text, { onTime = null, duration = null, tail = null, pictures = false, seekTitle = '', checked = null } = {}) {
  const ctx = { onTime, duration, pictures, seekTitle, checked }
  const list = blocks(text || '')
  return list.map((b, i) => {
    const end = i === list.length - 1 ? tail : null
    const key = `b${i}`
    if (b.kind === 'h') {
      return <p key={key} className={`md-h md-h--${Math.min(b.level, 3)}`}>{inline(b.text, ctx, key)}{end}</p>
    }
    if (b.kind === 'code') {
      return <pre key={key} className="md-pre" data-lang={b.lang || undefined}><code>{b.lines.join('\n')}</code>{end}</pre>
    }
    if (b.kind === 'hr') return <hr key={key} className="md-hr" />
    if (b.kind === 'quote') {
      return <blockquote key={key} className="md-quote">{b.lines.map((l, j) => <React.Fragment key={j}>{j ? <br /> : null}{inline(l, ctx, `${key}-${j}`)}</React.Fragment>)}{end}</blockquote>
    }
    if (b.kind === 'table') {
      return (
        <div key={key} className="md-table-wrap">
          <table className="md-table">
            <thead><tr>{b.head.map((c, j) => <th key={j}>{inline(c, ctx, `${key}-h${j}`)}</th>)}</tr></thead>
            <tbody>{b.rows.map((r, j) => <tr key={j}>{b.head.map((_, k) => <td key={k}>{inline(r[k] || '', ctx, `${key}-${j}-${k}`)}</td>)}</tr>)}</tbody>
          </table>
          {end}
        </div>
      )
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
