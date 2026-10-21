import React, { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { fmtTime, frameNo } from '../lib/format'
import { IconCheck, IconClose } from './Icons'
import '../styles/picker.css'

// Picking frames on a phone: the timeline's sheets are a few pixels wide under a finger, so here
// every keyframe is a big tile in a grid (grouped by chapter when there are chapters). Two modes:
//   选作附件  tap tiles to attach them to the next question (and tap again to drop them)
//   框选慢放  tap where a stretch starts and where it ends; then replay it, or attach it to the question
// The stretch is capped at MAX_RANGE seconds like the timeline's (backend modules/frames/replay.py).

const MAX_RANGE = 10

export default function FramePicker({ frames, chapters = [], selected, duration, busy = false, onToggle, onClear, onRange, onClose }) {
  const [mode, setMode] = useState('attach')
  const [ends, setEnds] = useState([]) // the stretch's tapped frames, in tap order (at most two)
  const ready = frames.filter((f) => f.src)
  const chosen = new Set(selected.map((f) => f.index))

  const groups = useMemo(() => {
    if (!chapters.length) return [{ title: '', frames: ready }]
    return chapters.map((c, i) => ({
      title: c.title,
      start: c.start,
      frames: ready.filter((f) => f.time >= c.start && (i === chapters.length - 1 || f.time < chapters[i + 1].start)),
    })).filter((g) => g.frames.length)
  }, [ready, chapters])

  const range = useMemo(() => {
    if (!ends.length) return null
    const times = ends.map((f) => f.time).sort((a, b) => a - b)
    let start = times[0]
    let end = ends.length > 1 ? times[1] : Math.min(start + 2, duration ?? start + 2)
    const clipped = end - start > MAX_RANGE
    if (clipped) end = start + MAX_RANGE
    if (end - start < 1) end = start + 1
    return { start: Math.round(start * 10) / 10, end: Math.round(end * 10) / 10, clipped, complete: ends.length > 1 }
  }, [ends, duration])

  const tap = (frame) => {
    if (mode === 'attach') return onToggle(frame)
    setEnds((list) => (list.length >= 2 ? [frame] : [...list, frame]))
  }
  const inRange = (f) => range && f.time >= range.start && f.time <= range.end
  const act = (action) => {
    if (!range) return
    onRange(range.start, range.end, action)
    onClose()
  }

  return createPortal(
    <div className="picker" role="dialog" aria-modal="true" aria-label="选帧">
      <header className="picker__head">
        <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={16} /></button>
        <div className="picker__modes" role="tablist" aria-label="怎么选">
          <button type="button" role="tab" aria-selected={mode === 'attach'} onClick={() => setMode('attach')}>选作附件</button>
          {onRange ? <button type="button" role="tab" aria-selected={mode === 'range'} onClick={() => { setMode('range'); setEnds([]) }}>框选慢放</button> : null}
        </div>
        <button type="button" className="btn btn--dark picker__done" onClick={onClose}>完成</button>
      </header>
      <p className="picker__hint">
        {mode === 'attach'
          ? (selected.length ? `已选 ${selected.length} 帧，提问时一起带上。` : '点画面选作提问附件，再点一次取消。')
          : range?.complete ? `${fmtTime(range.start)} – ${fmtTime(range.end)} · ${(range.end - range.start).toFixed(1)} 秒${range.clipped ? '（最长 10 秒，已截短）' : ''}`
            : range ? '再点一帧，作为这一段的结尾。' : '先点这一段开始的画面，再点结尾的画面（最长 10 秒）。'}
      </p>
      <div className="picker__grid-wrap">
        {groups.map((g) => (
          <section key={`${g.title}-${g.start ?? 0}`} className="picker__group">
            {g.title ? <h3 className="picker__chapter"><span className="mono-sm">{fmtTime(g.start)}</span> {g.title}</h3> : null}
            <div className="picker__grid">
              {g.frames.map((f) => {
                const on = mode === 'attach' ? chosen.has(f.index) : inRange(f)
                const edge = mode === 'range' && ends.some((e) => e.index === f.index)
                return (
                  <button key={f.index} type="button" className="picker__tile" data-on={on || undefined} data-edge={edge || undefined}
                    aria-pressed={on} onClick={() => tap(f)} aria-label={`${frameNo(f.index)} ${fmtTime(f.time)}`}>
                    <img src={f.src} alt="" loading="lazy" draggable="false" />
                    <span className="picker__time mono-sm">{fmtTime(f.time)}</span>
                    {on ? <span className="picker__check" aria-hidden="true"><IconCheck size={14} /></span> : null}
                  </button>
                )
              })}
            </div>
          </section>
        ))}
        {!ready.length ? <p className="picker__hint">画面还在抓取，稍等一下。</p> : null}
      </div>
      <footer className="picker__foot">
        {mode === 'attach' ? (
          selected.length ? <button type="button" className="btn btn--ghost" onClick={onClear}>清除已选</button> : <span />
        ) : (
          <>
            <button type="button" className="btn btn--ghost" disabled={!range?.complete} onClick={() => act('ask')}>附加到提问</button>
            <button type="button" className="btn btn--dark" disabled={!range?.complete || busy} onClick={() => act('play')}>慢放这一段</button>
          </>
        )}
      </footer>
    </div>,
    document.body,
  )
}
