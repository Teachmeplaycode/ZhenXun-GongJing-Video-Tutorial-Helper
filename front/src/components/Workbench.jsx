import React, { useEffect, useRef } from 'react'
import { IconChevron } from './Icons'

// The workbench: a sidebar on the right of the chat that holds the per-video tools, one tab each.
// A handle on its left edge (a small triangle) pulls it out and pushes it back. Panels stay mounted
// while hidden, so a fact-check or a note still being generated keeps running when another tab shows.
// panels: { key: element } in tab order; labels: { key: '章节' }; badges: { key: '3' } (optional).
export const BENCH_TABS = [
  { key: 'frames', label: '画面' }, // phones only: the frame grid instead of the timeline
  { key: 'chapters', label: '章节' },
  { key: 'notes', label: '笔记' },
  // 反诈 and 科普 are no longer tabs: they are skills the agent runs in an answer (modules/agent/skills.py).
]

// hide: tab keys that don't apply (a picture set has no chapters).
export default function Workbench({ open, onOpenChange, tab, onTab, panels, badges = {}, hide = [] }) {
  const tabsRef = useRef(null)
  const tabs = BENCH_TABS.filter((t) => !hide.includes(t.key))
  const shown = tabs.some((t) => t.key === tab) ? tab : tabs[0].key
  // Arrow keys move between tabs (WAI-ARIA tabs pattern); the focused tab is the shown one.
  const onKeyDown = (e) => {
    const i = tabs.findIndex((t) => t.key === shown)
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    e.preventDefault()
    const next = tabs[(i + step + tabs.length) % tabs.length].key
    onTab(next)
    requestAnimationFrame(() => tabsRef.current?.querySelector(`[data-tab="${next}"]`)?.focus())
  }
  // Esc closes the sidebar when it floats over the chat (narrow screens).
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape' && window.matchMedia('(max-width: 900px)').matches) onOpenChange(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  return (
    <>
      {open ? <div className="bench__backdrop" onClick={() => onOpenChange(false)} aria-hidden="true" /> : null}
      <aside className="bench" data-open={open || undefined} aria-label="工作台">
        <button type="button" className="bench__handle" onClick={() => onOpenChange(!open)}
          aria-expanded={open} aria-controls="bench-body" title={open ? '收起工作台' : '展开工作台：章节、反诈、科普、笔记'}>
          <IconChevron size={12} />
          <span className="bench__handle-label">工作台</span>
        </button>
        <div className="bench__body" id="bench-body" hidden={!open}>
          <div ref={tabsRef} className="bench__tabs" role="tablist" aria-label="工作台功能" onKeyDown={onKeyDown}>
            {tabs.map((t) => (
              <button key={t.key} type="button" role="tab" data-tab={t.key} id={`bench-tab-${t.key}`}
                aria-selected={shown === t.key} aria-controls={`bench-panel-${t.key}`} tabIndex={shown === t.key ? 0 : -1}
                className="bench__tab" onClick={() => onTab(t.key)}>
                {t.label}
                {badges[t.key] ? <span className="bench__badge mono-sm">{badges[t.key]}</span> : null}
              </button>
            ))}
          </div>
          {tabs.map((t) => (
            <section key={t.key} id={`bench-panel-${t.key}`} role="tabpanel" aria-labelledby={`bench-tab-${t.key}`}
              className="bench__panel" hidden={shown !== t.key}>
              {panels[t.key]}
            </section>
          ))}
        </div>
      </aside>
    </>
  )
}
