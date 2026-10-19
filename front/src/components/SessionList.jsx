import React, { useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { IconClose } from './Icons'
import { linkFrameUrl } from '../api/client'
import { fmtAgo, fmtClock } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'
import { platformName } from '../lib/platforms'

// One saved session: cover frame, title, and a mono line of identifiers and counts.
// Deleting asks for a second click on the same button.
export function SessionItem({ session, current = false, compact = false, onOpen, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const s = session
  const part = s.part > 1 ? ` · P${s.part}` : ''
  return (
    <li className={`session-item ${compact ? 'session-item--compact' : ''}`} data-current={current || undefined}>
      <button type="button" className="session-item__open" onClick={() => onOpen(s.id)} title={s.title}>
        {compact ? null : (
          <span className="session-item__cover">
            {s.cover_index != null ? <img src={linkFrameUrl(s.id, s.cover_index)} alt="" loading="lazy" /> : null}
          </span>
        )}
        <span className="session-item__body">
          <span className="session-item__row">
            <span className="session-item__title">{s.title || s.video_id}</span>
            <span className="session-item__ago">{fmtAgo(s.updated)}</span>
          </span>
          <span className="session-item__meta">
            {[platformName(s.platform) || s.video_id, s.kind === 'images' ? `图文 · ${s.image_count || s.frames_total} 张` : `视频${part} · ${fmtClock(s.duration)}`,
              s.questions ? `${s.questions} 问` : '未提问'].join(' · ')}
          </span>
          {!compact && s.last_question ? <span className="session-item__last">{s.last_question}</span> : null}
        </span>
      </button>
      {onDelete ? (
        confirming ? (
          <button type="button" className="session-item__confirm" onClick={() => onDelete(s.id)} onBlur={() => setConfirming(false)} autoFocus>
            确认删除
          </button>
        ) : (
          <button type="button" className="icon-btn session-item__delete" aria-label="删除会话" onClick={() => setConfirming(true)}>
            <IconClose size={12} />
          </button>
        )
      ) : null}
    </li>
  )
}

// Staggered entrance (after the ClubProject menu): two colour layers sweep in from the right,
// the panel follows, then its rows. Closing reverses it, the layers trailing behind the panel.
export function useStaggeredDrawer(rootRef, open) {
  const timeline = useRef(null)
  const first = useRef(true)
  useLayoutEffect(() => {
    const root = rootRef.current
    const panel = root.querySelector('.history__panel')
    const layers = root.querySelectorAll('.history__layer')
    const rows = root.querySelectorAll('.history__head, .history__empty, .session-item, .account-card')
    timeline.current?.kill()
    if (first.current || prefersReducedMotion()) {
      first.current = false
      gsap.set(panel, { xPercent: open ? 0 : 105, autoAlpha: open ? 1 : 0 })
      gsap.set(layers, { xPercent: open ? 0 : 105, autoAlpha: 0 })
      gsap.set(rows, { x: 0, autoAlpha: 1 })
      return undefined
    }
    const tl = gsap.timeline({ defaults: { ease: 'power3.inOut' } })
    if (open) {
      gsap.set(layers, { xPercent: 105, autoAlpha: 1 })
      gsap.set(rows, { x: 24, autoAlpha: 0 })
      tl.to(layers, { xPercent: 0, duration: 0.46, stagger: 0.075, ease: 'power4.out' }, 0)
        .to(panel, { xPercent: 0, autoAlpha: 1, duration: 0.56, ease: 'power4.out' }, 0.14)
        .to(rows, { x: 0, autoAlpha: 1, duration: 0.34, stagger: 0.045, ease: 'power2.out' }, 0.24)
        .set(layers, { autoAlpha: 0 }, 0.72)
    } else {
      gsap.set(layers, { xPercent: 0, autoAlpha: 1 })
      tl.to(rows, { x: 24, autoAlpha: 0, duration: 0.2, stagger: { each: 0.025, from: 'end' }, ease: 'power2.in' }, 0)
        .to(panel, { xPercent: 105, autoAlpha: 0, duration: 0.4 }, 0.08)
        .to(layers, { xPercent: 105, duration: 0.4, stagger: { each: 0.07, from: 'end' } }, 0.14)
        .set(layers, { autoAlpha: 0 })
        .set(rows, { x: 0, autoAlpha: 1 })
    }
    timeline.current = tl
    return () => tl.kill()
  }, [open, rootRef])
}

// Right-side drawer listing every saved session; available from the top bar at any stage.
export function HistoryDrawer({ open, sessions, error, currentId, onOpen, onDelete, onClose }) {
  const rootRef = useRef(null)
  useStaggeredDrawer(rootRef, open)
  return (
    <div ref={rootRef} className="history" data-open={open || undefined} aria-hidden={!open} inert={open ? undefined : ''}>
      <div className="history__backdrop" onClick={onClose} />
      <span className="history__layer history__layer--accent" aria-hidden="true" />
      <span className="history__layer history__layer--ink" aria-hidden="true" />
      <aside className="history__panel" role="dialog" aria-label="历史会话">
        <header className="history__head">
          <span className="eyebrow">历史会话</span>
          <span className="mono-sm muted">{sessions.length}</span>
          <button type="button" className="icon-btn history__close" aria-label="关闭" onClick={onClose}><IconClose /></button>
        </header>
        {error ? <p className="history__empty">{error}</p> : null}
        {!error && !sessions.length ? <p className="history__empty">还没有会话。解析一个视频链接后，对话会自动保存在这里。</p> : null}
        <ul className="history__list">
          {sessions.map((s) => (
            <SessionItem key={s.id} session={s} current={s.id === currentId} onOpen={onOpen} onDelete={onDelete} />
          ))}
        </ul>
      </aside>
    </div>
  )
}
