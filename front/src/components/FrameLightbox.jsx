import React, { useEffect, useLayoutEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import gsap from 'gsap'
import { IconChevron, IconClose } from './Icons'
import { prefersReducedMotion } from '../lib/motion'

const fine = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(2).padStart(5, '0')}`

// A frame enlarged in the middle of the screen. items: [{ src, time, tag?, label? }] (label replaces the
// time, e.g. "第 3 张" for a picture set); `at` is the one shown and
// onAt moves it (← / → keys, the side buttons), so the caller's own view can follow along.
// Esc, the close button or a click outside the picture closes it; focus returns where it was.
export default function FrameLightbox({ items, at, onAt, onClose, onSeek = null }) {
  const boxRef = useRef(null)
  const closeRef = useRef(null)
  const item = items[at]
  const many = items.length > 1
  const go = (k) => onAt((at + k + items.length) % items.length)

  useEffect(() => {
    const back = document.activeElement
    closeRef.current?.focus()
    return () => { if (back && back.focus) back.focus() }
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose() }
      else if (e.key === 'ArrowRight' && many) { e.preventDefault(); go(1) }
      else if (e.key === 'ArrowLeft' && many) { e.preventDefault(); go(-1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  useLayoutEffect(() => {
    if (prefersReducedMotion() || !boxRef.current) return undefined
    const t = gsap.fromTo(boxRef.current, { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.18, ease: 'power2.out' })
    return () => t.kill()
  }, [])

  if (!item) return null
  return createPortal(
    <div className="lightbox" role="dialog" aria-modal="true" aria-label={`放大查看 ${item.label || fine(item.time)}`}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <figure ref={boxRef} className="lightbox__box">
        <img src={item.src} alt={`画面 ${item.label || fine(item.time)}`} />
        <figcaption className="lightbox__bar">
          {item.tag ? <span className="lightbox__tag" data-kind={item.kind || undefined}>{item.tag}</span> : null}
          <span className="mono-sm">{item.label || fine(item.time)}</span>
          {many ? <span className="mono-sm lightbox__count">{at + 1} / {items.length}</span> : null}
          <span className="lightbox__spacer" />
          {onSeek ? (
            <button type="button" className="lightbox__btn" onClick={() => { onSeek(item.time); onClose() }}>在时间轴上定位</button>
          ) : null}
          <button ref={closeRef} type="button" className="lightbox__btn lightbox__close" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>
        </figcaption>
        {many ? (
          <>
            <button type="button" className="lightbox__nav lightbox__nav--prev" onClick={() => go(-1)} aria-label="上一帧"><IconChevron size={18} /></button>
            <button type="button" className="lightbox__nav lightbox__nav--next" onClick={() => go(1)} aria-label="下一帧"><IconChevron size={18} /></button>
          </>
        ) : null}
      </figure>
    </div>,
    document.body,
  )
}
