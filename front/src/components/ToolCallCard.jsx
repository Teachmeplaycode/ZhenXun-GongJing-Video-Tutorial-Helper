import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { IconAlert, IconCheck, IconChevron, IconStop } from './Icons'
import DiffViewer from './DiffViewer'

// §9.2 / §9.3 tool call card. Collapsed by default; summary line = tool · status · count.
export default function ToolCallCard({ call }) {
  const [open, setOpen] = useState(false)
  const bodyRef = useRef(null)
  const first = useRef(true)

  // tool_call.completed: collapse back to a one-line summary.
  useEffect(() => {
    if (call.status !== 'running') setOpen(false)
  }, [call.status])

  useLayoutEffect(() => {
    const el = bodyRef.current
    if (!el) return
    if (first.current) {
      first.current = false
      gsap.set(el, { height: open ? 'auto' : 0, display: open ? 'block' : 'none' })
      return
    }
    if (open) {
      gsap.set(el, { display: 'block' })
      gsap.fromTo(el, { height: 0, opacity: 0 }, { height: 'auto', opacity: 1, duration: 0.24, ease: 'power2.out' })
    } else {
      gsap.to(el, { height: 0, opacity: 0, duration: 0.18, ease: 'power2.in', onComplete: () => gsap.set(el, { display: 'none' }) })
    }
  }, [open])

  const statusText = { running: '运行中...', error: '失败', stopped: '已停止' }[call.status] || '完成'
  const { input, stdout, stderr, exitCode, diff } = call

  return (
    <div className="tool-card" data-status={call.status}>
      <button type="button" className="tool-card__summary" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className={`tool-card__chevron ${open ? 'is-open' : ''}`}><IconChevron size={12} /></span>
        <span className="tool-card__state">
          {call.status === 'running' ? <span className="spinner-dot" /> : call.status === 'error' ? <IconAlert size={14} /> : call.status === 'stopped' ? <IconStop size={14} /> : <IconCheck size={14} />}
        </span>
        <span className="tool-card__name">{call.tool}</span>
        <span className="tool-card__meta">· {statusText}{call.status === 'done' && call.resultCount != null ? ` · ${call.resultCount} 项` : ''}</span>
      </button>
      <div ref={bodyRef} className="tool-card__body">
        {input ? (
          <div className="tool-card__section">
            <div className="tool-card__label">ARGS</div>
            {input.kind === 'bash' ? (
              <code className="tool-card__cmd">$ {input.command}</code>
            ) : (
              <dl className="tool-card__params">
                {Object.entries(input.params || {}).map(([k, v]) => (
                  <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>
                ))}
              </dl>
            )}
          </div>
        ) : null}
        {stdout != null || stderr ? (
          <div className="tool-card__section">
            <div className="tool-card__label">
              RESULT
              {exitCode != null ? <span className={`exit-code ${exitCode === 0 ? 'is-ok' : 'is-bad'}`}>exit {exitCode}</span> : null}
            </div>
            <div className="tool-card__output">
              {stdout ? <pre className="tool-card__stdout">{stdout}</pre> : null}
              {stderr ? <pre className="tool-card__stderr">{stderr}</pre> : null}
            </div>
          </div>
        ) : null}
        {diff ? <div className="tool-card__section"><DiffViewer path={diff.path} diff={diff.diff} /></div> : null}
      </div>
    </div>
  )
}
