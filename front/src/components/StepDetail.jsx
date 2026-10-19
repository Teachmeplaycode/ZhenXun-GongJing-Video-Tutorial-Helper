import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { prefersReducedMotion } from '../lib/motion'
import { clock, host } from '../lib/steps'
import DiffViewer from './DiffViewer'
import { apiUrl } from '../api/client'
import { IconChevron, IconExpand } from './Icons'
import FrameLightbox from './FrameLightbox'

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

const INTENT_NAMES = { tutorial: '教程操作', content: '视频内容', science: '科普核查', verify: '核实说法', fraud: '反诈识别', chat: '与视频无关' }

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
          <span>{h.source === 'screen' ? <span className="viz-stamp viz-stamp--off viz-hits__source">字幕</span> : null}{h.text}</span>
        </li>
      ))}
    </ol>
  )
}

const fine = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(2).padStart(5, '0')}`
const SPEEDS = [0.25, 0.5, 1]

// Slow-motion replay: the frames of a few seconds played back slower than real time, or stepped
// through one by one; the strip below jumps to any frame, and the time button seeks the video there.
// Clicking the picture or a thumbnail enlarges it in the middle of the screen.
export function Replay({ d, onSeek }) {
  const frames = d.frames || []
  const times = d.times || []
  const [at, setAt] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(0.25)
  const [zoom, setZoom] = useState(false)
  const stripRef = useRef(null)
  useEffect(() => {
    if (!playing || frames.length < 2) return undefined
    const t = setInterval(() => setAt((i) => (i + 1) % frames.length), 1000 / (d.fps * speed))
    return () => clearInterval(t)
  }, [playing, speed, d.fps, frames.length])
  // Keep the current thumbnail in view while stepping or playing (scroll the strip only, not the page).
  useEffect(() => {
    const strip = stripRef.current
    const el = strip?.children[at]
    if (!el) return
    const left = el.offsetLeft - strip.offsetLeft
    if (left < strip.scrollLeft) strip.scrollLeft = left
    else if (left + el.offsetWidth > strip.scrollLeft + strip.clientWidth) strip.scrollLeft = left + el.offsetWidth - strip.clientWidth
  }, [at])
  const step = (k) => { setPlaying(false); setAt((i) => (i + k + frames.length) % frames.length) }
  const open = (i) => { setPlaying(false); setAt(i); setZoom(true) }
  if (!frames.length) return null
  return (
    <div className="viz-replay" data-row>
      <button type="button" className="viz-replay__stage" onClick={() => open(at)} title="放大查看" aria-label={`放大查看 ${fine(times[at] ?? 0)}`}>
        <img src={apiUrl(frames[at])} alt={`复看画面 ${fine(times[at] ?? 0)}`} />
        <span className="viz-replay__stamp mono-sm">{fine(times[at] ?? 0)} · {at + 1}/{frames.length}</span>
        <span className="viz-replay__zoom" aria-hidden="true"><IconExpand size={14} /></span>
      </button>
      <div className="viz-replay__controls">
        <button type="button" className="icon-btn viz-replay__prev" aria-label="上一帧" onClick={() => step(-1)}><IconChevron size={12} /></button>
        <button type="button" className="btn btn--ghost" onClick={() => setPlaying((v) => !v)}>{playing ? '暂停' : '慢放'}</button>
        <button type="button" className="icon-btn" aria-label="下一帧" onClick={() => step(1)}><IconChevron size={12} /></button>
        <span className="viz-replay__speeds">
          {SPEEDS.map((s) => (
            <button key={s} type="button" className="chip-btn" data-on={speed === s || undefined} onClick={() => setSpeed(s)}>{s === 1 ? '原速' : `${s}×`}</button>
          ))}
        </span>
        <button type="button" className="ts-chip" onClick={() => onSeek?.(times[at] ?? 0)} title="在原视频里跳到这一帧">{fine(times[at] ?? 0)}</button>
      </div>
      <ol ref={stripRef} className="viz-replay__strip">
        {frames.map((src, i) => (
          <li key={src}>
            <button type="button" data-on={i === at || undefined} onClick={() => open(i)} aria-label={`放大第 ${i + 1} 帧 ${fine(times[i] ?? 0)}`}>
              <img src={apiUrl(src)} alt="" loading="lazy" />
            </button>
          </li>
        ))}
      </ol>
      {zoom ? (
        <FrameLightbox
          items={frames.map((src, i) => ({ src: apiUrl(src), time: times[i] ?? 0, tag: '慢放', kind: 'replay' }))}
          at={at} onAt={setAt} onClose={() => setZoom(false)} onSeek={onSeek}
        />
      ) : null}
      <p className="mono-sm muted">每秒 {d.fps} 帧 · 共 {frames.length} 帧{d.clipped ? ' · 只复看了前 10 秒' : ''}</p>
    </div>
  )
}

const BARS = '▁▂▃▄▅▆▇█'

// measure_motion: what the instruments read off a dense decode, and the two pictures they drew.
function Motion({ d, onSeek }) {
  return (
    <div className="viz-motion">
      <p data-row><span className="mono-sm muted">镜头</span> {d.camera}</p>
      {(d.camera_detail || []).map((line) => <p key={line} className="mono-sm muted" data-row>{line}</p>)}
      <p data-row>
        <span className="mono-sm muted">运动强度</span>{' '}
        <span className="viz-motion__bars mono-sm" aria-label="运动强度随时间变化">{(d.energy || []).map((v) => BARS[Math.min(7, Math.floor(v * 7.999))]).join('')}</span>
        {d.period ? <span className="mono-sm muted"> · 周期约 {d.period} 秒</span> : null}
      </p>
      {d.peaks?.length ? (
        <div className="viz-times" data-row>
          <span className="mono-sm muted">峰值：</span>
          {d.peaks.slice(0, 12).map((t) => <button key={t} type="button" className="ts-chip" onClick={() => onSeek?.(t)}>{fine(t)}</button>)}
        </div>
      ) : null}
      <p className="mono-sm muted" data-row>{d.region}</p>
      <div className="viz-motion__images" data-row>
        {(d.images || []).map((src, i) => (
          <figure key={src}>
            <img src={apiUrl(src)} alt={i === 0 ? '运动热力图' : '运动轨迹叠影'} loading="lazy" />
            <figcaption className="mono-sm muted">{i === 0 ? '热力图：红黄 = 动得多' : '轨迹叠影：拖影 = 移动路径'}</figcaption>
          </figure>
        ))}
      </div>
    </div>
  )
}

function Comments({ d }) {
  return (
    <div className="viz-comments">
      {d.note ? <p className="mono-sm muted" data-row>{d.note}</p> : null}
      <ol className="viz-comments__list">
        {d.comments.map((c, i) => (
          <li key={i} data-row>
            <div className="viz-comment">
              <span className="viz-comment__author">{c.pinned ? <span className="viz-stamp viz-stamp--off">置顶</span> : null}{c.author}</span>
              <span className="viz-comment__meta mono-sm">赞 {c.likes}{c.replies ? ` · 回复 ${c.replies}` : ''}</span>
            </div>
            <p className="viz-comment__text">{c.text}</p>
            {c.sub?.length ? (
              <ul className="viz-comment__sub">
                {c.sub.map((r, j) => <li key={j}><span className="viz-comment__author">{r.author}</span> {r.text}</li>)}
              </ul>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}

// Danmaku density over the whole video: one ink, peaks in the active accent; hover names the bin, click seeks.
function Density({ d, onSeek }) {
  const [hover, setHover] = useState(null)
  const max = Math.max(1, ...d.bins)
  const peakBins = new Set((d.peaks || []).map((p) => Math.min(d.bins.length - 1, Math.floor((p.t + 0.001) / d.bin))))
  return (
    <div className="viz-density" data-row>
      <div className="viz-density__plot" onMouseLeave={() => setHover(null)}>
        {d.bins.map((n, i) => (
          <button
            key={i} type="button" className="viz-density__hit"
            aria-label={`${clock(i * d.bin)}–${clock((i + 1) * d.bin)}，${n} 条弹幕`}
            onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onClick={() => onSeek?.(i * d.bin)}
          >
            <span className={`viz-density__bar ${peakBins.has(i) ? 'is-peak' : ''}`} style={{ height: `${n ? Math.max(4, (n / max) * 100) : 0}%` }} />
          </button>
        ))}
      </div>
      <div className="viz-density__axis mono-sm">
        <span>00:00</span>
        <span className={hover != null ? 'is-hover' : undefined}>
          {hover != null ? `${clock(hover * d.bin)}–${clock((hover + 1) * d.bin)} · ${d.bins[hover]} 条 · 点击跳转` : `弹幕密度 · 共 ${d.total} 条`}
        </span>
        <span>{clock(d.bins.length * d.bin)}</span>
      </div>
    </div>
  )
}

const DANMAKU_ROWS = 12

function Danmaku({ d, onSeek }) {
  const [all, setAll] = useState(false)
  const rows = all ? d.hits : d.hits.slice(0, DANMAKU_ROWS)
  return (
    <div className="viz-danmaku">
      {d.bins?.length ? <Density d={d} onSeek={onSeek} /> : null}
      {d.pool ? <p className="mono-sm muted" data-row>{d.pool}</p> : null}
      {d.peaks?.length ? (
        <div className="viz-times" data-row>
          <span className="mono-sm muted">最密集：</span>
          {d.peaks.map((p) => (
            <button key={p.t} type="button" className="ts-chip" onClick={() => onSeek?.(p.t)}>{clock(p.t)} · {p.count}</button>
          ))}
        </div>
      ) : null}
      <ol className="viz-hits">
        {rows.map((h, i) => (
          <li key={i} data-row>
            <button type="button" className="ts-chip" onClick={() => onSeek?.(h.t)}>{clock(h.t)}</button>
            <span>{h.text}{h.n > 1 ? <span className="mono-sm muted"> ×{h.n}</span> : null}</span>
          </li>
        ))}
      </ol>
      {d.hits.length > DANMAKU_ROWS ? (
        <button type="button" className="viz-more mono-sm" onClick={() => setAll((v) => !v)}>
          {all ? '收起' : `显示全部 ${d.hits.length} 条`}
        </button>
      ) : null}
    </div>
  )
}

function Browse({ d }) {
  return (
    <div className="viz-browse">
      <p className="mono-sm muted" data-row>任务：{d.task}</p>
      <ol className="viz-browse__actions">
        {(d.actions || []).map((a, i) => <li key={i} data-row><span>{a.action}</span> {a.detail}</li>)}
      </ol>
      {d.pages?.length ? (
        <ul className="viz-browse__pages">
          {d.pages.map((p, i) => (
            <li key={i} data-row><a href={p.url} target="_blank" rel="noreferrer">{p.title || p.url}</a> <span className="mono-sm muted">{host(p.url)}</span></li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

// A closer look (补看): the frames read on demand, each one enlargeable.
function ViewFrames({ d, onSeek }) {
  const [zoom, setZoom] = useState(null)
  const secs = d.secs || []
  return (
    <div className="viz-view" data-row>
      <ol className="viz-replay__strip viz-view__strip">
        {d.frames.map((src, i) => (
          <li key={src}>
            <button type="button" onClick={() => setZoom(i)} aria-label={`放大 ${fine(secs[i] ?? 0)}`}>
              <img src={apiUrl(src)} alt="" loading="lazy" />
              <span className="mono-sm">{fine(secs[i] ?? 0)}</span>
            </button>
          </li>
        ))}
      </ol>
      {zoom != null ? (
        <FrameLightbox
          items={d.frames.map((src, i) => ({ src: apiUrl(src), time: secs[i] ?? 0, tag: '补看', kind: 'view' }))}
          at={zoom} onAt={setZoom} onClose={() => setZoom(null)} onSeek={onSeek}
        />
      ) : null}
    </div>
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
  if (call.tool === 'decision.intent' && d.probabilities && Object.keys(d.probabilities).length) {
    // Each kind's probability from the decision model; only a sure pick (≥ 0.6) changes how it answers.
    body = (
      <div className="viz-intents">
        {Object.entries(d.probabilities).sort((a, b) => b[1] - a[1]).map(([kind, p]) => (
          <Meter key={kind} p={p} threshold={0.6} label={INTENT_NAMES[kind] || kind} />
        ))}
        <p className="mono-sm muted">{d.sure ? '有把握：按这一类回答' : '把握不足：照常回答'}</p>
      </div>
    )
  } else if (call.tool === 'decision.research_intent' && d.p != null) {
    body = <Meter p={d.p} label={d.needed ? '需要查资料' : '不需要查资料'} />
  } else if (call.tool === 'web.search' && d.results) {
    body = <Results results={d.results} />
  } else if (call.tool === 'web.fetch' && d.url) {
    body = <PageScan d={d} />
  } else if (call.tool === 'frames.motion' && d.camera) {
    body = <Motion d={d} onSeek={onSeek} />
  } else if (call.tool === 'frames.replay' && d.frames) {
    body = <Replay d={d} onSeek={onSeek} />
  } else if (call.tool === 'audience.comments' && d.comments) {
    body = <Comments d={d} />
  } else if (call.tool === 'audience.danmaku' && d.hits) {
    body = <Danmaku d={d} onSeek={onSeek} />
  } else if (call.tool === 'browser.use' && d.task) {
    body = <Browse d={d} />
  } else if (call.tool === 'papers.search' && d.papers) {
    body = <Papers papers={d.papers} />
  } else if (call.tool === 'transcript.search' && d.hits) {
    body = <Hits hits={d.hits} onSeek={onSeek} />
  } else if (call.tool === 'frames.view' && d.frames?.length) {
    body = <ViewFrames d={d} onSeek={onSeek} />
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
