import React, { useState } from 'react'
import { fmtClock } from '../lib/format'

// The video's table of contents (backend modules/chapters): titles with time ranges and a one-line
// summary each. data is the polled /chapters answer; onSeek(start) points the timeline at a chapter.
// It folds away (remembered like the timeline) and shows why the build failed or is still running.
export default function ChaptersPanel({ data = null, onSeek = null }) {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem('chapters.open') !== '0'
    } catch {
      return true
    }
  })
  const toggle = () => setOpen((v) => {
    try {
      localStorage.setItem('chapters.open', v ? '0' : '1')
    } catch {
      // private mode: still toggles for this visit
    }
    return !v
  })
  if (!data) return null
  const list = data.status === 'done' ? data.chapters || [] : []
  return (
    <section className="chapters" data-open={open || undefined} aria-label="视频章节目录">
      <header className="chapters__head">
        <span className="eyebrow">章节目录</span>
        {data.status === 'running' ? <span className="mono-sm chapters__note">生成中…</span> : null}
        {data.status === 'failed' ? <span className="mono-sm chapters__error">{data.message || '章节生成失败'}</span> : null}
        {!['done', 'running', 'failed'].includes(data.status) ? <span className="mono-sm chapters__note">{data.message || '暂时无法生成章节'}</span> : null}
        {data.status === 'done' && !list.length ? <span className="mono-sm chapters__note">{data.message || '没有生成章节'}</span> : null}
        {list.length ? <span className="mono-sm muted">{list.length} 章</span> : null}
        <button type="button" className="link-btn chapters__fold" onClick={toggle} aria-expanded={open}>
          {open ? '收起' : '展开'}
        </button>
      </header>
      {open && data.summary ? <p className="chapters__overview body-sm">{data.summary}</p> : null}
      {open && list.length ? (
        <ol className="chapters__list">
          {list.map((c, i) => (
            <li key={`${c.start}-${c.title}`}>
              <button type="button" className="chapters__item" onClick={() => onSeek?.(c.start)}
                title={`${c.title} ${fmtClock(c.start)}–${fmtClock(c.end)}`}>
                <span className="chapters__no mono-sm">{String(i + 1).padStart(2, '0')}</span>
                <span className="chapters__body">
                  <strong>{c.title}</strong>
                  <span className="chapters__summary">{c.summary}</span>
                </span>
                <span className="chapters__time mono-sm muted">{fmtClock(c.start)}–{fmtClock(c.end)}</span>
              </button>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  )
}
