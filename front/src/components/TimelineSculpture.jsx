import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { fmtClock, fmtTime, frameNo } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'

const NEIGHBOR_RADIUS = 3
const PREVIEW_DELAY = 400 // ms
const PREVIEW_WIDTH = 220
const HOVER_LIFT = -8 // px
const SEEK_HOLD = 2500 // ms a sheet pointed at from an answer stays raised
const REST_ANGLE = -52 // deg, sheets stand obliquely like a deck seen from the side
const HOVER_ANGLE = -12 // deg, hovered sheet turns its face to the viewer
const CARD_HEIGHT = 60 // px
const CARD_DEPTH = 4 // px, sheet thickness

// At rest the sheets stand level and uniform. On hover the target and its neighbours rise and
// turn along a cosine bell, so the lifted group forms one smooth curve.
const bell = (d) => 0.5 + 0.5 * Math.cos((Math.PI * d) / (NEIGHBOR_RADIUS + 1))

// Frames may carry `status` (link jobs): 'pending' sheets are placeholders, 'missing' ones are
// hatched and can't be selected. Local-file frames have no status and are always available.
const isAvailable = (f) => Boolean(f.src) && (!f.status || f.status === 'ok')

// seek: { time, key } from a time clicked in an answer — the nearest sheet rises and shows its preview.
export default function TimelineSculpture({ frames, duration, selected, onToggle, onClear, onRetry = null, retrying = false, seek = null }) {
  const trackRef = useRef(null)
  const deckRef = useRef(null)
  const bodies = useRef([])
  const cards = useRef([])
  const timer = useRef(0)
  const [preview, setPreview] = useState(null)
  const [trackWidth, setTrackWidth] = useState(0)
  const count = frames.length
  const selectedSet = useMemo(() => new Set(selected.map((f) => f.index)), [selected])
  const missingCount = frames.filter((f) => f.status === 'missing').length
  const pendingCount = frames.filter((f) => f.status === 'pending').length

  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setTrackWidth(e.contentRect.width))
    ro.observe(trackRef.current)
    return () => ro.disconnect()
  }, [])

  // §7.1 analyzing_to_chat: sheets distribute from a center stack into time order.
  useLayoutEffect(() => {
    gsap.set(cards.current.filter(Boolean), { rotationY: REST_ANGLE })
    if (prefersReducedMotion()) return undefined
    const items = deckRef.current.querySelectorAll('.tl-sheet')
    const tween = gsap.from(items, {
      x: (i, el) => deckRef.current.clientWidth / 2 - el.offsetLeft,
      opacity: 0,
      duration: 1.4,
      ease: 'power3.inOut',
      stagger: { each: 0.008, from: 'center' },
    })
    const turn = gsap.from(cards.current.filter(Boolean), {
      rotationY: -88,
      duration: 1.4,
      ease: 'power3.inOut',
      stagger: { each: 0.008, from: 'center' },
    })
    return () => { tween.kill(); turn.kill() }
  }, [])

  const hover = (index) => {
    bodies.current.forEach((el, i) => {
      if (!el) return
      const d = index == null ? Infinity : Math.abs(i - index)
      const w = d <= NEIGHBOR_RADIUS ? bell(d) : 0
      const isTarget = d === 0
      const dur = isTarget ? 0.2 : 0.25
      gsap.to(el, { y: HOVER_LIFT * w, scale: isTarget ? 1.05 : 1, duration: dur, ease: 'power2.out', overwrite: 'auto' })
      gsap.to(cards.current[i], {
        rotationY: REST_ANGLE + (HOVER_ANGLE - REST_ANGLE) * w,
        duration: dur,
        ease: 'power2.out',
        overwrite: 'auto',
      })
    })
    clearTimeout(timer.current)
    if (index == null) {
      setPreview(null)
    } else {
      setPreview((p) => (p ? { ...p, index } : p)) // once open, follow the pointer immediately
      timer.current = setTimeout(() => setPreview({ index }), PREVIEW_DELAY)
    }
  }
  useEffect(() => () => clearTimeout(timer.current), [])

  const [seeking, setSeeking] = useState(null) // index raised by a seek, for its accent outline
  useEffect(() => {
    if (!seek || !frames.length) return undefined
    const nearest = frames.reduce((best, f, i) => (Math.abs(f.time - seek.time) < Math.abs(frames[best].time - seek.time) ? i : best), 0)
    hover(nearest)
    clearTimeout(timer.current)
    setPreview({ index: nearest, seek: seek.time })
    setSeeking(nearest)
    const release = setTimeout(() => { hover(null); setSeeking(null) }, SEEK_HOLD)
    return () => clearTimeout(release)
    // Only a new seek should move the timeline, not frames arriving in the background.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seek])

  const slot = trackWidth / Math.max(1, count)
  // Face width ~2 slots: rotated sheets overlap slightly like a fanned deck.
  const cardWidth = Math.round(Math.max(18, Math.min(64, slot * 2)))
  const previewFrame = preview ? frames[preview.index] : null
  const previewX = preview ? (preview.index + 0.5) * slot : 0
  const previewLeft = Math.min(Math.max(previewX - PREVIEW_WIDTH / 2, 0), Math.max(0, trackWidth - PREVIEW_WIDTH))

  return (
    <section className="timeline" aria-label="视频时间轴">
      <header className="timeline__head">
        <span className="eyebrow">TIMELINE</span>
        <span className="mono-sm muted">{count} 帧 · 00:00.0 – {fmtTime(duration)}</span>
        {pendingCount ? <span className="mono-sm timeline__pending">抓取中 {count - pendingCount}/{count}</span> : null}
        {missingCount ? (
          <span className="mono-sm timeline__missing">
            缺 {missingCount} 帧
            {onRetry && !pendingCount ? (
              <button type="button" className="link-btn" onClick={onRetry} disabled={retrying}>{retrying ? '补抓中…' : '补抓'}</button>
            ) : null}
          </span>
        ) : null}
        <span className="timeline__spacer" />
        {selected.length ? (
          <>
            <span className="mono-sm">已选 {selected.length} 帧</span>
            <button type="button" className="link-btn" onClick={onClear}>清除</button>
          </>
        ) : (
          <span className="caption muted">点击薄片选择关键帧作为提问附件</span>
        )}
      </header>
      <div ref={trackRef} className="timeline__track" onPointerLeave={() => hover(null)}>
        <div
          ref={deckRef}
          className="timeline__deck"
          style={{ '--card-w': `${cardWidth}px`, '--card-h': `${CARD_HEIGHT}px`, '--card-d': `${CARD_DEPTH}px` }}
        >
          {frames.map((f, i) => {
            const isSel = selectedSet.has(f.index)
            const available = isAvailable(f)
            return (
              <button
                key={f.index}
                type="button"
                className={`tl-sheet ${isSel ? 'is-selected' : ''} ${seeking === i ? 'is-seeking' : ''} ${f.status === 'missing' ? 'is-missing' : ''} ${f.status === 'pending' ? 'is-pending' : ''}`}
                style={{ left: `${(i / count) * 100}%`, width: `${100 / count}%` }}
                onPointerEnter={() => hover(i)}
                onFocus={() => hover(i)}
                onBlur={() => hover(null)}
                onClick={() => { if (available) onToggle(f) }}
                aria-pressed={isSel}
                aria-disabled={!available}
                aria-label={`${frameNo(f.index)} ${fmtTime(f.time)}${f.status === 'missing' ? ' 未取得画面' : f.status === 'pending' ? ' 抓取中' : ''}`}
              >
                <span ref={(el) => { bodies.current[i] = el }} className="tl-sheet__body">
                  <span ref={(el) => { cards.current[i] = el }} className="tl-card">
                    <span className="tl-card__face tl-card__face--front">{f.src ? <img src={f.src} alt="" draggable="false" /> : null}</span>
                    <span className="tl-card__face tl-card__face--back" />
                    <span className="tl-card__face tl-card__face--side" />
                    <span className="tl-card__face tl-card__face--top" />
                  </span>
                  {isSel ? <span className="tl-sheet__mark" /> : null}
                </span>
              </button>
            )
          })}
        </div>
        {previewFrame ? (
          <div className="sheet-preview" style={{ left: previewLeft, width: PREVIEW_WIDTH, '--arrow-x': `${previewX - previewLeft}px` }}>
            {previewFrame.src ? <img src={previewFrame.src} alt="" /> : (
              <div className="sheet-preview__empty">{previewFrame.status === 'missing' ? previewFrame.reason || '未取得画面' : '正在抓取…'}</div>
            )}
            <div className="sheet-preview__meta">
              <span className="mono-sm">{fmtTime(previewFrame.time)}</span>
              {preview.seek != null && Math.abs(preview.seek - previewFrame.time) >= 1 ? (
                <span className="mono-sm muted">≈ {fmtClock(preview.seek)}</span>
              ) : null}
              <span className="mono-sm muted">{frameNo(previewFrame.index)}</span>
              {selectedSet.has(previewFrame.index) ? <span className="tag tag--active">已选</span> : null}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}
