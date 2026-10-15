import React, { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { prefersReducedMotion } from '../lib/motion'
import { clock, host } from '../lib/steps'
import DiffViewer from './DiffViewer'

// Visual detail of one step, animated on first open: probability meters fill, result rows arrive in
// order and get their verdict, a page scan sweeps window by window. Falls back to args + raw output.

const VERDICT = {
  reliable: { label: '可靠', tone: 'ok' },
  unreliable: { label: '存疑', tone: 'warn' },
  irrelevant: { label: '无关', tone: 'off' },
}

function useEntrance(ref, deps) {
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || prefersReducedMotion()) return undefined
    const ctx = gsap.context(() => {
      const tl = gsap.timeline()
      tl.from(el.querySelectorAll('[data-row]'), { opacity: 0, y: 6, duration: 0.24, ease: 'power2.out', stagger: 0.05 })
      el.querySelectorAll('[data-fill]').forEach((bar) => {
        tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: 'power2.out' }, 0.12)
      })
      tl.from(el.querySelectorAll('[data-stamp]'), { opacity: 0, scale: 1.4, duration: 0.2, ease: 'back.out(1.4)', stagger: 0.05 }, 0.3)
      tl.to(el.querySelectorAll('[data-drop]'), { opacity: 0.45, duration: 0.3, ease: 'power2.inOut', stagger: 0.05 }, 0.5)
      tl.fromTo(el.querySelectorAll('[data-strike]'), { scaleX: 0 }, { scaleX: 1, duration: 0.3, ease: 'power2.inOut', stagger: 0.05 }, 0.5)
      const segs = el.querySelectorAll('[data-seg]')
      if (segs.length) tl.fromTo(segs, { opacity: 0.15 }, { opacity: 1, duration: 0.2, ease: 'power2.out', stagger: 0.18 }, 0.1)
    }, el)
    return () => ctx.revert()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

function Meter({ p, threshold = 0.5, label }) {
  return (
    <div className="viz-meter" data-row>
      <div className="viz-meter__track">
        <span className="viz-meter__fill" data-fill style={{ width: `${Math.round(p * 100)}%` }} />
        <span className="viz-meter__threshold" style={{ left: `${threshold * 100}%` }} title={`阈值 ${threshold}`} />
      </div>
      <span className="viz-meter__value mono-sm">{label} {p.toFixed(2)}</span>
    </div>
  )
}

function Results({ results }) {
  return (
    <ol className="viz-results">
      {results.map((r, i) => {
        const v = VERDICT[r.verdict]
        const dropped = r.verdict === 'irrelevant'
        return (
          <li key={`${r.url}-${i}`} className="viz-result" data-row {...(dropped ? { 'data-drop': '' } : {})}>
            <span className="viz-result__main">
              <a href={r.url} target="_blank" rel="noreferrer" className="viz-result__title">
                {r.title}
                {dropped ? <i className="viz-result__strike" data-strike /> : null}
              </a>
              <span className="viz-result__host mono-sm">{r.host || host(r.url)}</span>
            </span>
            {r.p ? (
              <span className="viz-result__split" title={Object.entries(r.p).map(([k, x]) => `${VERDICT[k]?.label || k} ${x.toFixed(2)}`).join(' · ')}>
                {['reliable', 'unreliable', 'irrelevant'].map((k) => (
                  <i key={k} className={`viz-split viz-split--${VERDICT[k].tone}`} data-fill style={{ width: `${(r.p[k] || 0) * 100}%` }} />
                ))}
              </span>
            ) : null}
            {v ? <span className={`viz-stamp viz-stamp--${v.tone}`} data-stamp>{v.label}</span> : null}
          </li>
        )
      })}
    </ol>
  )
}

function PageScan({ d }) {
  const blocked = d.blocked
  const windows = Math.max(1, d.windows || 1)
  return (
    <div className="viz-page" data-row>
      <a href={d.url} target="_blank" rel="noreferrer" className="viz-page__title">{d.title || d.url}</a>
      <span className="viz-page__host mono-sm">{d.host} · 第 {d.from + 1}–{d.to} 字 / 共 {d.total} 字</span>
      <div className="viz-scan">
        <span className="viz-scan__label mono-sm">注入扫描</span>
        <span className="viz-scan__segs">
          {Array.from({ length: windows }, (_, i) => (
            <i key={i} className={`viz-scan__seg ${blocked && i === windows - 1 ? 'is-hit' : ''}`} data-seg />
          ))}
        </span>
        <span className={`viz-stamp viz-stamp--${blocked ? 'warn' : d.risk == null ? 'off' : 'ok'}`} data-stamp>
          {blocked ? `已拦截 ${d.risk.toFixed(2)}` : d.risk == null ? '未检查' : `安全 ${d.risk.toFixed(2)}`}
        </span>
      </div>
    </div>
  )
}

function Papers({ papers }) {
  return (
    <ol className="viz-papers">
      {papers.map((p, i) => (
        <li key={`${p.url}-${i}`} className="viz-paper" data-row>
          <a href={p.url} target="_blank" rel="noreferrer" className="viz-paper__title">{p.title}</a>
          <span className="viz-paper__meta mono-sm">
            {[(p.authors || []).join('、'), p.year, p.venue].filter(Boolean).join(' · ')}
          </span>
          {p.citations != null ? <span className="viz-paper__cites mono-sm" data-stamp>被引 {p.citations}</span> : null}
        </li>
      ))}
    </ol>
  )
}

function Hits({ hits, onSeek }) {
  return (
    <ol className="viz-hits">
      {hits.map((h, i) => (
        <li key={i} data-row>
          <button type="button" className="ts-chip" onClick={() => onSeek?.(h.t)}>{clock(h.t)}</button>
          <span>{h.text}</span>
        </li>
      ))}
    </ol>
  )
}

function Raw({ call }) {
  const params = call.input?.params
  return (
    <div className="viz-raw">
      {params ? (
        <dl className="tool-card__params">
          {Object.entries(params).map(([k, v]) => <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>)}
        </dl>
      ) : null}
      {call.stdout ? <pre className="tool-card__stdout">{call.stdout}</pre> : null}
      {call.stderr ? <pre className="tool-card__stderr">{call.stderr}</pre> : null}
      {call.diff ? <DiffViewer path={call.diff.path} diff={call.diff.diff} /> : null}
    </div>
  )
}

export default function StepDetail({ call, onSeek }) {
  const ref = useRef(null)
  const d = call.data || {}
  useEntrance(ref, [call.status])
  let body
  if (call.tool === 'decision.research_intent' && d.p != null) {
    body = <Meter p={d.p} label={d.needed ? '需要查资料' : '不需要查资料'} />
  } else if (call.tool === 'web.search' && d.results) {
    body = <Results results={d.results} />
  } else if (call.tool === 'web.fetch' && d.url) {
    body = <PageScan d={d} />
  } else if (call.tool === 'papers.search' && d.papers) {
    body = <Papers papers={d.papers} />
  } else if (call.tool === 'transcript.search' && d.hits) {
    body = <Hits hits={d.hits} onSeek={onSeek} />
  } else if (call.tool === 'frames.view' && d.times) {
    body = (
      <div className="viz-times" data-row>
        {d.fallback ? <span className="mono-sm muted">原视频已不可读，用的是已有关键帧：</span> : null}
        {d.times.map((t) => <button key={t} type="button" className="ts-chip" onClick={() => onSeek?.(t.split(':').reduce((a, n) => a * 60 + Number(n), 0))}>{t}</button>)}
      </div>
    )
  } else {
    body = <Raw call={call} />
  }
  return <div ref={ref} className="step-detail">{body}</div>
}
