import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { fmtClock, fmtTime, frameNo } from '../lib/format'
import { IconChevron } from './Icons'
import { prefersReducedMotion } from '../lib/motion'
import FrameLightbox from './FrameLightbox'
import IntervalForm from './IntervalForm'

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

// Frames read on demand in the chat (see lib/extraFrames): slotted in by time, tinted by kind,
// with a band under the stretch they cover. They can't be attachments; a click enlarges them.
const EXTRA = { replay: '慢放', view: '补看' }
const MAX_RANGE = 10 // s, the longest stretch one replay covers (backend modules/frames/replay.py)
const MIN_RANGE = 0.5 // s, a shorter drag is widened around its middle
const DRAG_START = 6 // px of movement before a press on the track becomes a drag
const LONG_PRESS = 450 // ms a still press on a sheet takes to open the frame viewer
const fine = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`

// seek: { time, key } from a time clicked in an answer — the nearest sheet rises and shows its preview.
// cuts: shot changes (seconds) and cited: [{ time, n }] times the answers point at, both marked above
// the sheets. chapters: [{ start, end, title, summary }] faint bands under the sheets (backend
// modules/chapters), alternating two tints so neighbouring chapters stay apart.
// Dragging across the track frames a stretch (≤ 10 s): onRange(start, end, 'play' | 'ask')
// replays it now or attaches it to the next question; busy disables 'play' while an answer runs.
// open / onOpenChange: the track can fold away to give the chat more height; `pulse` (a changing
// number) flashes the head to show where frames are picked.
export default function TimelineSculpture({ frames, pictures = false, extras = [], onClearExtras = null, onPick = null, cuts = [], cited = [], chapters = [], activeChapter = null, busy = false, onRange = null, duration, selected, onToggle, onClear, onRetry = null, retrying = false, seek = null, open = true, onOpenChange = null, pulse = 0 }) {
  const trackRef = useRef(null)
  const sectionRef = useRef(null)
  const deckRef = useRef(null)
  const bodies = useRef([])
  const cards = useRef([])
  const timer = useRef(0)
  const [preview, setPreview] = useState(null)
  const [trackWidth, setTrackWidth] = useState(0)
  const [zoom, setZoom] = useState(null) // { items: [{ src, time, tag, kind }], at } shown in the frame viewer
  const longPress = useRef(0)
  const [typing, setTyping] = useState(false) // the typed-interval form is open
  const [drag, setDrag] = useState(null) // { x0, x1 } px while framing a stretch
  const [range, setRange] = useState(null) // { start, end, left, right } framed, its menu open
  const press = useRef(null) // { x, id, dragging } of the pointer pressed on the track
  const swallowClick = useRef(false) // the click that ends a drag must not toggle a sheet
  const menuRef = useRef(null)
  // Keyframes and on-demand frames in time order (a keyframe goes first on a tie).
  const items = useMemo(() => {
    const extra = extras.flatMap((g) => g.frames.map((f, k) => ({ ...f, group: g, k })))
    if (!extra.length) return frames
    return [...frames, ...extra].sort((a, b) => a.time - b.time || (a.kind ? 1 : 0) - (b.kind ? 1 : 0))
  }, [frames, extras])
  const count = items.length
  const bands = useMemo(() => extras.map((g) => {
    const first = items.findIndex((f) => f.group === g)
    let last = first
    items.forEach((f, i) => { if (f.group === g) last = i })
    return { g, first, last }
  }).filter((b) => b.first >= 0), [items, extras])
  const extraCount = (kind) => extras.filter((g) => g.kind === kind).reduce((n, g) => n + g.frames.length, 0)
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
    cards.current.forEach((el) => { if (el) el.dataset.posed = '1' })
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

  useLayoutEffect(() => {
    const fresh = cards.current.slice(0, count).filter((el) => el && !el.dataset.posed)
    if (!fresh.length) return
    gsap.set(fresh, { rotationY: REST_ANGLE })
    fresh.forEach((el) => { el.dataset.posed = '1' })
  }, [count])

  const hover = (index) => {
    bodies.current.slice(0, count).forEach((el, i) => {
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
  useEffect(() => () => { clearTimeout(timer.current); clearTimeout(longPress.current) }, [])

  useLayoutEffect(() => {
    const head = sectionRef.current?.querySelector('.timeline__head')
    if (!pulse || !head || prefersReducedMotion()) return undefined
    const tween = gsap.fromTo(head, { backgroundColor: 'var(--accent-active)' }, { backgroundColor: 'rgba(0,0,0,0)', duration: 0.9, ease: 'power2.out', delay: 0.25 })
    return () => tween.kill()
  }, [pulse])

  const [seeking, setSeeking] = useState(null) // index raised by a seek, for its accent outline
  const release = useRef(0)
  const pointAt = (time) => {
    if (!items.length) return
    const nearest = items.reduce((best, f, i) => (Math.abs(f.time - time) < Math.abs(items[best].time - time) ? i : best), 0)
    hover(nearest)
    clearTimeout(timer.current)
    setPreview({ index: nearest, seek: time })
    setSeeking(nearest)
    clearTimeout(release.current)
    release.current = setTimeout(() => { hover(null); setSeeking(null) }, SEEK_HOLD)
  }
  useEffect(() => () => clearTimeout(release.current), [])
  useEffect(() => {
    if (seek) pointAt(seek.time)
    // Only a new seek should move the timeline, not frames arriving in the background.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seek])

  const slot = trackWidth / Math.max(1, count)
  // Face width ~2 slots: rotated sheets overlap slightly like a fanned deck.
  const cardWidth = Math.round(Math.max(18, Math.min(64, slot * 2)))
  const previewFrame = preview ? items[preview.index] : null
  const previewX = preview ? (preview.index + 0.5) * slot : 0
  const previewLeft = Math.min(Math.max(previewX - PREVIEW_WIDTH / 2, 0), Math.max(0, trackWidth - PREVIEW_WIDTH))

  // Sheets sit in equal slots by order, not by time, so times map to x through the neighbouring sheets.
  const end = duration || items[items.length - 1]?.time || 0
  const xOfTime = (t) => {
    if (!count || !slot) return 0
    const first = items[0].time
    if (t <= first) return first > 0 ? (t / first) * slot * 0.5 : slot * 0.5
    for (let i = 0; i < count - 1; i++) {
      const a = items[i].time
      const b = items[i + 1].time
      if (t <= b) return (i + 0.5 + (b > a ? (t - a) / (b - a) : 0)) * slot
    }
    const last = items[count - 1].time
    const lastX = (count - 0.5) * slot
    return end > last ? lastX + ((t - last) / (end - last)) * (trackWidth - lastX) : lastX
  }
  const timeOfX = (x) => {
    if (!count || !slot) return 0
    const pos = x / slot - 0.5
    if (pos <= 0) return Math.max(0, items[0].time * (x / (slot * 0.5)))
    const i = Math.floor(pos)
    if (i >= count - 1) {
      const last = items[count - 1].time
      const lastX = (count - 0.5) * slot
      return Math.min(end, last + ((x - lastX) / Math.max(1, trackWidth - lastX)) * Math.max(0, end - last))
    }
    return items[i].time + (pos - i) * (items[i + 1].time - items[i].time)
  }

  // Framing a stretch: press on the track and drag; a press that doesn't move stays a click.
  const localX = (e) => {
    const box = trackRef.current.getBoundingClientRect()
    return Math.min(Math.max(e.clientX - box.left, 0), box.width)
  }
  // Long press on a sheet: every frame with a picture in the viewer, starting at that one.
  const openViewer = (i) => {
    const shown = items.map((f, k) => ({ f, k })).filter(({ f }) => f.src && isAvailable(f))
    const at = shown.findIndex(({ k }) => k === i)
    if (at < 0) return
    hover(null)
    setZoom({ at, items: shown.map(({ f }) => ({ src: f.src, time: f.time, kind: f.kind, tag: f.kind ? EXTRA[f.kind] : pictures ? undefined : frameNo(f.index), label: pictures ? `第 ${f.index + 1} 张` : undefined })) })
  }
  const cancelLongPress = () => clearTimeout(longPress.current)
  const onPointerDown = (e) => {
    if (e.button !== 0 || !count || e.target.closest('.tl-range__menu, .tl-mark')) return
    const sheet = e.target.closest('.tl-sheet')
    cancelLongPress()
    if (sheet) {
      longPress.current = setTimeout(() => {
        press.current = null // the press is a long press now, not a drag
        swallowClick.current = true // nor a click on release
        openViewer(Number(sheet.dataset.i))
      }, LONG_PRESS)
    }
    if (onRange) press.current = { x: localX(e), id: e.pointerId, dragging: false }
  }
  const onPointerMove = (e) => {
    const p = press.current
    if (!p || p.id !== e.pointerId) return
    const x = localX(e)
    if (!p.dragging) {
      if (Math.abs(x - p.x) < DRAG_START) return
      cancelLongPress()
      p.dragging = true
      trackRef.current.setPointerCapture?.(e.pointerId)
      hover(null)
      setRange(null)
    }
    setDrag({ x0: p.x, x1: x })
  }
  const onPointerUp = (e) => {
    cancelLongPress()
    if (swallowClick.current) setTimeout(() => { swallowClick.current = false }, 0) // after a long press
    const p = press.current
    press.current = null
    if (!p || !p.dragging) return
    swallowClick.current = true
    setTimeout(() => { swallowClick.current = false }, 0)
    setDrag(null)
    const x = localX(e)
    let start = timeOfX(Math.min(p.x, x))
    let stop = timeOfX(Math.max(p.x, x))
    if (stop - start > MAX_RANGE) {  // keep the end the drag started from
      if (x >= p.x) stop = start + MAX_RANGE
      else start = stop - MAX_RANGE
    }
    if (stop - start < MIN_RANGE) {
      const mid = (start + stop) / 2
      start = Math.max(0, mid - MIN_RANGE / 2)
      stop = start + MIN_RANGE
    }
    start = Math.round(start * 10) / 10
    stop = Math.round(stop * 10) / 10
    setRange({ start, end: stop, clipped: timeOfX(Math.max(p.x, x)) - timeOfX(Math.min(p.x, x)) > MAX_RANGE })
  }
  const choose = (action) => {
    if (!range) return
    onRange?.(range.start, range.end, action)
    setRange(null)
  }
  // The menu closes on Esc or a press elsewhere; its first choice takes the focus.
  useEffect(() => {
    if (!range) return undefined
    menuRef.current?.querySelector('button:not([disabled])')?.focus()
    const onKey = (e) => { if (e.key === 'Escape') setRange(null) }
    const onDown = (e) => { if (!menuRef.current?.contains(e.target)) setRange(null) }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onDown)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('pointerdown', onDown) }
  }, [range])

  // What the overlay shows: the live drag (clamped like the result), or the framed stretch.
  let shade = null
  if (drag) {
    const a = timeOfX(Math.min(drag.x0, drag.x1))
    const b = timeOfX(Math.max(drag.x0, drag.x1))
    const over = b - a > MAX_RANGE
    const [s0, s1] = !over ? [a, b] : drag.x1 >= drag.x0 ? [a, a + MAX_RANGE] : [b - MAX_RANGE, b]
    shade = { left: xOfTime(s0), right: xOfTime(s1), label: `${fine(s0)} – ${fine(s1)} · ${(s1 - s0).toFixed(1)} 秒${over ? '（最长 10 秒）' : ''}` }
  } else if (range) {
    shade = { left: xOfTime(range.start), right: xOfTime(range.end), label: `${fine(range.start)} – ${fine(range.end)} · ${(range.end - range.start).toFixed(1)} 秒${range.clipped ? '（已截到 10 秒）' : ''}` }
  }
  const menuLeft = shade ? Math.min(Math.max((shade.left + shade.right) / 2 - 110, 0), Math.max(0, trackWidth - 220)) : 0

  return (
    <section ref={sectionRef} className="timeline" data-open={open || undefined} aria-label="视频时间轴">
      <header className="timeline__head">
        <span className="eyebrow">TIMELINE</span>
        <span className="mono-sm muted">{pictures ? `${frames.length} 张图片` : `${frames.length} 帧 · 00:00.0 – ${fmtTime(duration)}`}</span>
        {['replay', 'view'].map((kind) => (extraCount(kind) ? (
          <span key={kind} className="mono-sm timeline__legend" data-kind={kind}><i aria-hidden="true" />{EXTRA[kind]} {extraCount(kind)} 帧
            {onClearExtras ? <button type="button" className="link-btn timeline__legend-clear" onClick={() => onClearExtras(kind)}
              title={`从时间轴上去掉${EXTRA[kind]}的帧（对话里的${EXTRA[kind]}结果还在）`}>清除</button> : null}
          </span>
        ) : null))}
        {chapters.length ? <span className="mono-sm timeline__legend" data-kind="chapter"><i aria-hidden="true" />章节 {chapters.length}</span> : null}
        {cuts.length ? <span className="mono-sm timeline__legend" data-kind="cut"><i aria-hidden="true" />镜头切换 {cuts.length}</span> : null}
        {cited.length ? <span className="mono-sm timeline__legend" data-kind="cite"><i aria-hidden="true" />回答提到 {cited.length}</span> : null}
        {pendingCount ? <span className="mono-sm timeline__pending">抓取中 {frames.length - pendingCount}/{frames.length}</span> : null}
        {missingCount ? (
          <span className="mono-sm timeline__missing">
            缺 {missingCount} 帧
            {onRetry && !pendingCount ? (
              <button type="button" className="link-btn" onClick={onRetry} disabled={retrying}>{retrying ? '补抓中…' : '补抓'}</button>
            ) : null}
          </span>
        ) : null}
        {onRange ? (
          <span className="timeline__interval">
            <button type="button" className="link-btn timeline__interval-btn" onClick={() => setTyping((v) => !v)} aria-expanded={typing}
              title="输入起止时间慢放，长视频比拖动更准">输入区间</button>
            {typing ? <IntervalForm duration={duration} busy={busy} onRange={onRange} onClose={() => setTyping(false)} /> : null}
          </span>
        ) : null}
        {onPick ? <button type="button" className="link-btn timeline__pick" onClick={onPick}>大图选帧</button> : null}
        <span className="timeline__spacer" />
        {selected.length ? (
          <>
            <span className="mono-sm">已选 {selected.length} 帧</span>
            <button type="button" className="link-btn" onClick={onClear}>清除</button>
          </>
        ) : (
          <span className="caption muted">{open ? (pictures ? '点击图片选作提问附件；长按放大查看' : `点击薄片选择关键帧作为提问附件${onRange ? '；拖动框选一段可以慢放；长按薄片放大' : ''}`) : '已收起'}</span>
        )}
        {onOpenChange ? (
          <button type="button" className="timeline__fold" onClick={() => onOpenChange(!open)} aria-expanded={open}
            title={open ? '收起时间轴，让对话区更高' : '展开时间轴'}>
            <IconChevron size={12} /> {open ? '收起' : '展开'}
          </button>
        ) : null}
      </header>
      <div className="timeline__body"><div className="timeline__fold-inner">
      <div ref={trackRef} className="timeline__track" data-framing={drag ? '' : undefined}
        onPointerLeave={() => { if (!press.current?.dragging) hover(null) }}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onPointerCancel={() => { cancelLongPress(); press.current = null; setDrag(null) }}
        onContextMenu={(e) => { if (e.target.closest('.tl-sheet')) e.preventDefault() }}>
        {chapters.map((c, i) => (
          <span key={`ch${c.start}`} className="tl-chapterband" data-alt={i % 2 || undefined} data-active={activeChapter === i || undefined}
            style={{ left: xOfTime(c.start), width: Math.max(0, xOfTime(c.end) - xOfTime(c.start)) }}
            title={`${i + 1}. ${c.title}`} aria-hidden="true" />
        ))}
        <div
          ref={deckRef}
          className="timeline__deck"
          style={{ '--card-w': `${cardWidth}px`, '--card-h': `${CARD_HEIGHT}px`, '--card-d': `${CARD_DEPTH}px` }}
        >
          {items.map((f, i) => {
            if (f.kind) {
              return (
                <button
                  key={f.src}
                  type="button"
                  className={`tl-sheet is-extra ${seeking === i ? 'is-seeking' : ''}`}
                  data-kind={f.kind}
                  style={{ left: `${(i / count) * 100}%`, width: `${100 / count}%` }} data-i={i}
                  onPointerEnter={() => hover(i)}
                  onFocus={() => hover(i)}
                  onBlur={() => hover(null)}
                  onClick={() => { if (!swallowClick.current) setZoom({ items: f.group.frames.map((x) => ({ ...x, tag: EXTRA[x.kind] })), at: f.k }) }}
                  aria-label={`${EXTRA[f.kind]}帧 ${fmtTime(f.time)}，点击放大`}
                >
                  <span ref={(el) => { bodies.current[i] = el }} className="tl-sheet__body">
                    <span ref={(el) => { cards.current[i] = el }} className="tl-card">
                      <span className="tl-card__face tl-card__face--front"><img src={f.src} alt="" draggable="false" /></span>
                      <span className="tl-card__face tl-card__face--back" />
                      <span className="tl-card__face tl-card__face--side" />
                      <span className="tl-card__face tl-card__face--top" />
                    </span>
                  </span>
                </button>
              )
            }
            const isSel = selectedSet.has(f.index)
            const available = isAvailable(f)
            return (
              <button
                key={f.index}
                type="button"
                className={`tl-sheet ${isSel ? 'is-selected' : ''} ${seeking === i ? 'is-seeking' : ''} ${f.status === 'missing' ? 'is-missing' : ''} ${f.status === 'pending' ? 'is-pending' : ''}`}
                style={{ left: `${(i / count) * 100}%`, width: `${100 / count}%` }} data-i={i}
                onPointerEnter={() => hover(i)}
                onFocus={() => hover(i)}
                onBlur={() => hover(null)}
                onClick={() => { if (available && !swallowClick.current) onToggle(f) }}
                aria-pressed={isSel}
                aria-disabled={!available}
                aria-label={`${pictures ? `第 ${f.index + 1} 张` : `${frameNo(f.index)} ${fmtTime(f.time)}`}${f.status === 'missing' ? ' 未取得画面' : f.status === 'pending' ? ' 抓取中' : ''}`}
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
        {cuts.map((t) => (
          <span key={`c${t}`} className="tl-cut" style={{ left: xOfTime(t) }} title={`镜头切换 ${fine(t)}`} aria-hidden="true" />
        ))}
        {cited.map((c) => (
          <button key={`q${c.time}`} type="button" className="tl-mark tl-cite" style={{ left: xOfTime(c.time) }}
            onClick={() => pointAt(c.time)} title={`回答提到 ${fmtClock(c.time)}${c.n > 1 ? `（${c.n} 次）` : ''}`}
            aria-label={`回答提到的时间 ${fmtClock(c.time)}`} data-many={c.n > 1 || undefined} />
        ))}
        {shade ? (
          <div className="tl-range" style={{ left: shade.left, width: Math.max(2, shade.right - shade.left) }} aria-hidden="true">
            <span className="tl-range__label mono-sm">{shade.label}</span>
          </div>
        ) : null}
        {range ? (
          <div ref={menuRef} className="tl-range__menu" role="menu" aria-label={`框选 ${fine(range.start)} – ${fine(range.end)}`} style={{ left: menuLeft }}>
            <button type="button" role="menuitem" onClick={() => choose('play')} disabled={busy}
              title={busy ? '正在回答，结束后再慢放' : '直接逐帧慢放这一段，不经过模型'}>
              <span className="tl-range__icon" aria-hidden="true">▶</span>直接慢放{busy ? '（回答中）' : ''}
            </button>
            <button type="button" role="menuitem" onClick={() => choose('ask')}>
              <span className="tl-range__icon" aria-hidden="true">✎</span>带着这段提问
            </button>
            <button type="button" role="menuitem" className="tl-range__cancel" onClick={() => setRange(null)}>取消</button>
          </div>
        ) : null}
        {bands.map(({ g, first, last }) => (
          <span key={g.id} className="tl-band" data-kind={g.kind} aria-hidden="true"
            style={{ left: `${(first / count) * 100}%`, width: `${((last - first + 1) / count) * 100}%` }}
            title={`${EXTRA[g.kind]} ${fmtTime(g.start)} – ${fmtTime(g.end)}`} />
        ))}
        {previewFrame ? (
          <div className="sheet-preview" style={{ left: previewLeft, width: PREVIEW_WIDTH, '--arrow-x': `${previewX - previewLeft}px` }}>
            {previewFrame.src ? <img src={previewFrame.src} alt="" /> : (
              <div className="sheet-preview__empty">{previewFrame.status === 'missing' ? previewFrame.reason || '未取得画面' : '正在抓取…'}</div>
            )}
            <div className="sheet-preview__meta">
              <span className="mono-sm">{pictures ? `第 ${previewFrame.index + 1} 张` : fmtTime(previewFrame.time)}</span>
              {!pictures && preview.seek != null && Math.abs(preview.seek - previewFrame.time) >= 1 ? (
                <span className="mono-sm muted">≈ {fmtClock(preview.seek)}</span>
              ) : null}
              {previewFrame.kind ? (
                <span className="tag timeline__tag" data-kind={previewFrame.kind}>{EXTRA[previewFrame.kind]}</span>
              ) : <span className="mono-sm muted">{frameNo(previewFrame.index)}</span>}
              {selectedSet.has(previewFrame.index) ? <span className="tag tag--active">已选</span> : null}
            </div>
          </div>
        ) : null}
      </div>
      </div></div>
      {zoom ? (
        <FrameLightbox
          items={zoom.items}
          at={zoom.at} onAt={(at) => setZoom((z) => ({ ...z, at }))} onClose={() => setZoom(null)}
        />
      ) : null}
    </section>
  )
}
