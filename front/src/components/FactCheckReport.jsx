import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { IconCheck, IconClose as IconX, IconAlert as IconAlertTriangle, IconLink as IconExternal } from './Icons'
import { IconHelpCircle, IconShield, IconSearch } from './FactCheckIcons'
import { prefersReducedMotion } from '../lib/motion'
import { streamFactCheck, getFactCheck } from '../api/factcheck'

const VERDICT_CONFIG = {
  correct:    { label: '正确',   cls: 'verdict--correct',    Icon: IconCheck,        tone: 'ok' },
  partial:    { label: '部分正确', cls: 'verdict--partial',    Icon: IconAlertTriangle, tone: 'warn' },
  wrong:      { label: '错误',   cls: 'verdict--wrong',      Icon: IconX,            tone: 'bad' },
  unverifiable: { label: '无法核实', cls: 'verdict--unverifiable', Icon: IconHelpCircle, tone: 'off' },
}

const RISK_LABEL = { high: '高风险', medium: '中风险', low: '低风险' }
const RISK_TONE = { high: 'bad', medium: 'warn', low: 'ok' }

const EXAGGERATION_NOTE = {
  absolute: '绝对化用语',
  cure: '夸大疗效',
  alarmist: '恐吓式表述',
  vague_authority: '模糊权威背书',
}

function fmtTime(s) {
  const t = Math.max(0, Math.round(s))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}

function SourceItem({ src, i }) {
  const trusted = src.trusted
  return (
    <li className={`fc-source${trusted ? ' fc-source--trusted' : ''}`} data-row>
      <span className="fc-source__i mono-sm">{i + 1}</span>
      <div className="fc-source__body">
        <a className="fc-source__title" href={src.url} target="_blank" rel="noopener noreferrer"
           title="在新标签页打开出处">
          {src.title}
          <IconExternal size={12} />
        </a>
        {src.snippet ? <p className="fc-source__snippet">{src.snippet}</p> : null}
        <div className="fc-source__meta">
          {trusted ? (
            <span className="fc-trust fc-trust--yes"><IconShield size={12} />{src.name || '权威来源'} · {src.kind || ''}</span>
          ) : (
            <span className="fc-trust fc-trust--no">普通网页</span>
          )}
        </div>
      </div>
    </li>
  )
}

function ClaimCard({ claim, onSeek }) {
  const v = VERDICT_CONFIG[claim.verdict] || VERDICT_CONFIG.unverifiable
  const riskTone = RISK_TONE[claim.risk] || 'off'
  const exag = claim.exaggeration || { detected: false, terms: [], categories: [], note: '' }
  const VerdictIcon = v.Icon

  return (
    <article className={`fc-claim fc-claim--${v.tone}`} data-row>
      <header className="fc-claim__head">
        <span className={`fc-verdict fc-verdict--${v.tone}`}>
          <VerdictIcon size={14} />
          <span>{v.label}</span>
        </span>
        <span className={`fc-risk fc-risk--${riskTone}`} title="风险等级">{RISK_LABEL[claim.risk] || '中风险'}</span>
      </header>

      <p className="fc-claim__original">"{claim.original_text}"</p>
      {claim.claim && claim.claim !== claim.original_text ? (
        <p className="fc-claim__proposition">命题：{claim.claim}</p>
      ) : null}

      <div className="fc-claim__context">
        <button type="button" className="fc-time" onClick={() => onSeek?.(claim.timestamp.start)}>
          <span className="mono-sm">⏱ {claim.timestamp.label}</span>
        </button>
        <span className="fc-evidence">{claim.evidence.source === 'screentext' ? '画面文字' : '语音转写'}</span>
      </div>

      {exag.detected ? (
        <div className="fc-exag">
          <strong>夸大用语：</strong>
          <span className="fc-exag__terms">{exag.terms.join('、')}</span>
          <span className="fc-exag__note">（{exag.note}）</span>
        </div>
      ) : null}

      {claim.reason ? <p className="fc-claim__reason">{claim.reason}</p> : null}

      {claim.sources.length > 0 ? (
        <details className="fc-sources" open>
          <summary className="fc-sources__summary mono-sm">
            出处 {claim.sources.length} 条{claim.sources.some(s => s.trusted) ? '（含权威来源）' : ''}
          </summary>
          <ul className="fc-sources__list">
            {claim.sources.map((s, i) => <SourceItem key={s.url || i} src={s} i={i} />)}
          </ul>
        </details>
      ) : (
        <p className="fc-claim__no-sources">未找到可参考的来源。</p>
      )}
    </article>
  )
}

function Summary({ summary }) {
  const items = [
    { key: 'correct', label: '正确', cls: 'ok' },
    { key: 'partial', label: '部分正确', cls: 'warn' },
    { key: 'wrong', label: '错误', cls: 'bad' },
    { key: 'unverifiable', label: '无法核实', cls: 'off' },
  ]
  const total = summary.total || 0
  return (
    <div className="fc-summary" data-row>
      {items.map((it) => {
        const n = summary[it.key] || 0
        const pct = total ? Math.round(n / total * 100) : 0
        return (
          <div key={it.key} className={`fc-summary__item fc-summary__item--${it.cls}`}>
            <span className="fc-summary__label">{it.label}</span>
            <span className="fc-summary__num mono-sm">{n}</span>
            <span className="fc-summary__bar"><span style={{ width: `${pct}%` }} /></span>
          </div>
        )
      })}
      <div className="fc-summary__meta">
        <span>夸大用语 {summary.exaggerations || 0} 条</span>
        <span>· 权威来源 {summary.trusted_sources || 0} 条</span>
      </div>
    </div>
  )
}

function useEntrance(ref) {
  useEffect(() => {
    const el = ref.current
    if (!el || prefersReducedMotion()) return
    const ctx = gsap.context(() => {
      gsap.from(el.querySelectorAll('[data-row]'), { opacity: 0, y: 8, duration: 0.3, stagger: 0.04, ease: 'power2.out' })
    }, el)
    return () => ctx.revert()
  }, [])
}

export default function FactCheckReport({ jobId, video, onSeek, onClose, open = false }) {
  const [report, setReport] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState({ count: 0, total: 0, verifying: '' })
  const ctrlRef = useRef(null)
  const shellRef = useRef(null)
  useEntrance(shellRef)

  const loadSaved = useCallback(async () => {
    try {
      const r = await getFactCheck(jobId)
      if (r) setReport(r)
    } catch { /* ignore */ }
  }, [jobId])

  useEffect(() => {
    if (open) loadSaved()
  }, [open, loadSaved])

  useEffect(() => () => ctrlRef.current?.abort(), [])

  const start = useCallback(async ({ web, papers } = {}) => {
    ctrlRef.current?.abort()
    const ctrl = new AbortController()
    ctrlRef.current = ctrl
    setRunning(true)
    setError('')
    setProgress({ count: 0, total: 0, verifying: '' })
    setReport(null)
    try {
      const r = await streamFactCheck(jobId, {
        web, papers, signal: ctrl.signal,
        onEvent(ev) {
          if (ev.type === 'factcheck.claims_extracted') setProgress((p) => ({ ...p, total: ev.count }))
          if (ev.type === 'factcheck.claim.verifying') setProgress((p) => ({ ...p, verifying: ev.claim }))
          if (ev.type === 'factcheck.claim.done') setProgress((p) => ({ ...p, count: p.count + 1 }))
        },
      })
      if (!ctrl.signal.aborted) setReport(r)
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message || '核查失败')
    } finally {
      if (ctrlRef.current === ctrl) setRunning(false)
    }
  }, [jobId])

  const stop = useCallback(() => { ctrlRef.current?.abort(); setRunning(false) }, [])

  const sortedClaims = useMemo(() => {
    if (!report?.claims) return []
    return [...report.claims].sort((a, b) => {
      const ra = { high: 0, medium: 1, low: 2 }[a.risk] ?? 2
      const rb = { high: 0, medium: 1, low: 2 }[b.risk] ?? 2
      return ra - rb
    })
  }, [report])

  if (!open) return null

  return (
    <div className="fc-shell" ref={shellRef} role="dialog" aria-label="科普核查报告">
      <div className="fc-shell__backdrop" onClick={onClose} />
      <div className="fc-shell__panel">
        <header className="fc-head">
          <div className="fc-head__title">
            <IconSearch size={18} />
            <div>
              <h2 className="h2">科普核查报告</h2>
              <p className="muted mono-sm fc-head__video">{video?.title || '视频'}</p>
            </div>
          </div>
          <div className="fc-head__actions">
            {report ? (
              <button type="button" className="chip-btn" onClick={() => start({})} disabled={running}>
                {running ? '核查中…' : '重新核查'}
              </button>
            ) : running ? (
              <button type="button" className="chip-btn" onClick={stop}>停止</button>
            ) : (
              <button type="button" className="chip-btn fc-run" onClick={() => start({})}>
                开始核查
              </button>
            )}
            <button type="button" className="fc-close" onClick={onClose} aria-label="关闭">
              <IconX size={16} />
            </button>
          </div>
        </header>

        {running && (
          <div className="fc-progress" data-row>
            <div className="fc-progress__bar"><span style={{ width: `${progress.total ? Math.round(progress.count / progress.total * 100) : 0}%` }} /></div>
            <p className="mono-sm fc-progress__status">
              {progress.total === 0 ? '正在抽取说法…' : `核实中 ${progress.count} / ${progress.total}`}
              {progress.verifying ? <span className="fc-progress__claim">"{progress.verifying}"</span> : null}
            </p>
          </div>
        )}

        {error ? <div className="fc-error"><IconAlertTriangle size={14} />{error}</div> : null}

        {report ? (
          <div className="fc-body">
            {report.summary ? <Summary summary={report.summary} /> : null}
            <ol className="fc-claims">
              {sortedClaims.map((c) => (
                <li key={c.id}><ClaimCard claim={c} onSeek={onSeek} /></li>
              ))}
            </ol>
            {sortedClaims.length === 0 ? (
              <p className="fc-empty muted">未发现可核实的事实性说法。</p>
            ) : null}
            <p className="fc-disclaimer">⚕ {report.disclaimer}</p>
          </div>
        ) : !running && !error ? (
          <div className="fc-empty" data-row>
            <IconSearch size={40} />
            <p>点击"开始核查"，从视频转写和画面文字中抽出可核实的说法，用权威来源逐一核实。</p>
            <p className="muted fc-empty__sub">面向"子女帮父母查"的场景，每条结论给出正确/部分正确/错误/无法核实、出处和夸大用语标注。</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
