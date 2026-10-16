import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import gsap from 'gsap'
import { IconChevron, IconClose, IconExpand, IconLock, IconRefresh, IconStop } from './Icons'
import { EASE } from '../lib/motion'

// §11 Computer-use viewport embedded in the assistant bubble.
// Frames arrive via browser.frame events (WebSocket on the real backend); without frames
// a neutral page skeleton is shown so cursor actions stay legible.
export default function BrowserViewport({ session, onStop }) {
  const [expanded, setExpanded] = useState(false)
  const [logOpen, setLogOpen] = useState(false)
  const [size, setSize] = useState(null)
  const screenRef = useRef(null)
  const cursorRef = useRef(null)
  const rippleRef = useRef(null)
  const last = session.actions[session.actions.length - 1]

  // Report local viewport size; the backend syncs it to the remote Playwright viewport.
  useEffect(() => {
    const el = screenRef.current
    if (!el) return undefined
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ w: Math.round(width), h: Math.round(height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [expanded])

  useLayoutEffect(() => {
    if (!last || !cursorRef.current) return
    gsap.to(cursorRef.current, { left: `${last.x * 100}%`, top: `${last.y * 100}%`, duration: 0.4, ease: EASE.move })
    if (last.action === 'click' && rippleRef.current) {
      gsap.fromTo(rippleRef.current, { scale: 0.4, opacity: 0.9 }, { scale: 2.6, opacity: 0, duration: 0.6, delay: 0.4, ease: EASE.enter })
    }
  }, [last, expanded])

  const view = (
    <div className={`browser ${expanded ? 'browser--expanded' : ''}`} data-status={session.status}>
      <div className="browser__bar">
        <IconLock size={12} />
        <span className="browser__url">{session.url}</span>
        {size ? <span className="browser__size">{size.w}×{size.h}</span> : null}
        <button type="button" className="icon-btn" title="刷新" aria-label="刷新"><IconRefresh size={14} /></button>
        <button type="button" className="icon-btn" title={expanded ? '收起' : '展开'} aria-label="展开" onClick={() => setExpanded((v) => !v)}>
          {expanded ? <IconClose size={14} /> : <IconExpand size={14} />}
        </button>
        <button type="button" className="icon-btn" title="停止" aria-label="停止" onClick={onStop} disabled={session.status !== 'running'}><IconStop size={14} /></button>
      </div>
      <div ref={screenRef} className="browser__screen">
        {/* Screenshots are 16:10; the stage matches them so cursor fractions land on the right spot. */}
        <div className={session.frame ? 'browser__stage' : 'browser__stage browser__stage--fill'}>
        {session.frame ? (
          <img className="browser__frame" src={session.frame} alt="远程浏览器画面" />
        ) : (
          <div className="browser__skeleton" aria-hidden="true">
            <div className="sk sk--logo" />
            <div className="sk sk--search" />
            <div className="sk-row"><div className="sk sk--card" /><div className="sk sk--card" /><div className="sk sk--card" /></div>
            <div className="sk sk--line" /><div className="sk sk--line short" />
          </div>
        )}
        <div ref={cursorRef} className="browser__cursor">
          <span ref={rippleRef} className="browser__ripple" />
        </div>
        </div>
      </div>
      <div className="browser__log">
        <button type="button" className="browser__log-toggle" onClick={() => setLogOpen((v) => !v)} aria-expanded={logOpen}>
          <span className={`tool-card__chevron ${logOpen ? 'is-open' : ''}`}><IconChevron size={12} /></span>
          操作记录 · {session.actions.length}
          {last ? <span className="browser__last">{last.action} {last.detail}</span> : null}
        </button>
        {logOpen ? (
          <ol className="browser__entries">
            {session.actions.map((a, i) => <li key={i} className={a.error ? 'is-error' : undefined}><span>{a.action}</span> {a.detail}</li>)}
          </ol>
        ) : null}
      </div>
    </div>
  )

  if (!expanded) return view
  return (
    <>
      <div className="browser browser--placeholder">已展开为全屏视图</div>
      {createPortal(<div className="overlay" onClick={(e) => e.target === e.currentTarget && setExpanded(false)}>{view}</div>, document.body)}
    </>
  )
}
