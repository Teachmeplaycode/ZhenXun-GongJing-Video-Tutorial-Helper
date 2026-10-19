import React, { useState, useEffect } from 'react'
import { fetchAntifraudReport } from '../api/client'
import { IconAlert as IconAlertTriangle, IconCheck as IconCheckCircle, IconClose as IconX, IconRefresh as IconLoader, IconLink, IconUser as IconMessage } from './Icons'
import { IconShield, IconQrCode, IconPhone } from './antifraud-icons'
import './AntifraudPanel.css'

const VERDICT_STYLE = {
  fraud: { bg: 'var(--bg-danger)', border: 'var(--border-danger)', text: 'var(--text-danger)', label: '高风险线索', Icon: IconX },
  suspicious: { bg: 'var(--bg-warning)', border: 'var(--border-warning)', text: 'var(--text-warning)', label: '可疑', Icon: IconAlertTriangle },
  safe: { bg: 'var(--bg-success)', border: 'var(--border-success)', text: 'var(--text-success)', label: '未见明显信号', Icon: IconCheckCircle },
}

const RISK_LABEL = { high: '高', medium: '中', low: '低' }

function fmtTime(seconds) {
  if (!seconds && seconds !== 0) return '--:--'
  const s = Math.max(0, Math.round(seconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

function ClaimCard({ claim }) {
  const style = VERDICT_STYLE[claim.verdict] || VERDICT_STYLE.safe
  const { Icon } = style
  return (
    <article className="antifraud__claim" data-verdict={claim.verdict}>
      <header className="antifraud__claim-head">
        <span className="antifraud__verdict" style={{ background: style.bg, color: style.text, borderColor: style.border }}>
          <Icon size={12} /> {style.label}
        </span>
        <span className="antifraud__risk">{claim.status === 'unverified' ? '待人工核实 · ' : ''}风险 {RISK_LABEL[claim.risk] || claim.risk}</span>
        <span className="antifraud__time">{fmtTime(claim.timestamp?.start)}</span>
      </header>
      <p className="antifraud__claim-text">{claim.claim}</p>
      {claim.original_text && (
        <blockquote className="antifraud__original">
          <span className="antifraud__label">原文</span>
          <span>{claim.original_text}</span>
        </blockquote>
      )}
      <p className="antifraud__reason">{claim.reason}</p>
      {claim.sources?.length > 0 && (
        <ul className="antifraud__sources">
          {claim.sources.map((s, i) => (
            <li key={i} className="antifraud__source" title={s.snippet}>
              <span className="antifraud__source-kind">{s.kind || '来源'}</span>
              <span className="antifraud__source-name">{s.name || s.title}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}

function DrainageBadge({ signals = [], qrcodes = [] }) {
  if (!signals.length && !qrcodes.length) return null
  const byKind = {}
  for (const s of signals) {
    byKind[s.kind] = (byKind[s.kind] || 0) + 1
  }
  const items = []
  if (byKind.wechat_id) items.push({ n: byKind.wechat_id, label: '微信号', Icon: IconMessage })
  if (byKind.phone) items.push({ n: byKind.phone, label: '手机号', Icon: IconPhone })
  if (byKind.phone_400) items.push({ n: byKind.phone_400, label: '400电话', Icon: IconPhone })
  if (byKind.url || byKind.short_url) items.push({ n: (byKind.url || 0) + (byKind.short_url || 0), label: '网址', Icon: IconLink })
  if (qrcodes.length) items.push({ n: qrcodes.length, label: '二维码', Icon: IconQrCode })
  if (!items.length) return null
  return (
    <div className="antifraud__badges">
      {items.map(({ n, label, Icon }) => (
        <span key={label} className="antifraud__badge">
          <Icon size={12} /> {label} ×{n}
        </span>
      ))}
    </div>
  )
}

const INSTITUTION_STATUS = {
  record_found: '找到官方登记记录', official_reference: '官方提及 · 登记未确认',
  unverified: '未核实', error: '核查失败 · 未核实',
}

function Institutions({ result }) {
  if (!result) return null
  return <section className="antifraud__institutions" aria-label="机构公开证据核查">
    <h3>机构公开证据核查</h3>
    <p className="caption muted">{result.message}</p>
    {result.omitted > 0 && <p role="status">另有 {result.omitted} 个机构超出本轮核查上限，尚未核实。</p>}
    {result.configuration_error && <p role="status">{result.configuration_error}</p>}
    {result.items?.map((item) => <article key={item.name} className="antifraud__claim">
      <header className="antifraud__claim-head"><strong>{item.name}</strong>
        <span>{INSTITUTION_STATUS[item.status] || '未核实'}</span>
        <time className="antifraud__time">{fmtTime(item.timestamp?.start)}</time>
      </header>
      <p>{item.reason}</p>
      {item.record && <p>记录状态：{item.record.registration_state} · 统一社会信用代码/注册号：{item.record.registration_code}</p>}
      <ul>{item.sources?.map((source, i) => <li key={i}>
        <span>{source.official ? '官方来源' : '第三方线索（未核实）'} · </span>
        {/^https?:\/\//i.test(source.url || '') ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || source.url}</a> : <span>{source.title}</span>}
        <blockquote>{source.snippet}</blockquote>
      </li>)}</ul>
    </article>)}
  </section>
}

// report: a finished report to show as it is (the 反诈识别 skill's result in an answer); nothing is fetched.
export default function AntifraudPanel({ jobId, videoTitle, onClose, transcript, screentext, frameRevision, report: given = null }) {
  // Refresh once each background source reaches a final state; progress-only updates
  // do not repeatedly start paid model calls or external institution queries.
  const revision = [transcript, screentext].map((stage) =>
    ['done', 'empty', 'none', 'unavailable', 'failed'].includes(stage?.status)
      ? `${stage.status}:${stage.count || 0}` : 'waiting').join('|') + `|${frameRevision || 'waiting'}`
  const [report, setReport] = useState(given)
  const [loading, setLoading] = useState(!given)
  const [error, setError] = useState('')

  useEffect(() => {
    if (given) return undefined
    let stopped = false
    const controller = new AbortController()
    setReport(null)
    setLoading(true)
    setError('')
    fetchAntifraudReport(jobId, { signal: controller.signal })
      .then((r) => { if (!stopped) setReport(r) })
      .catch((err) => { if (!stopped) setError(err.message) })
      .finally(() => { if (!stopped) setLoading(false) })
    return () => { stopped = true; controller.abort() }
  }, [jobId, revision, given])

  if (loading) {
    return (
      <div className="antifraud antifraud--loading">
        <IconLoader size={20} className="antifraud__spinner" />
        <p>正在分析诈骗风险…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="antifraud antifraud--error">
        <IconAlertTriangle size={20} />
        <p>反诈分析失败：{error}</p>
        <button type="button" className="btn btn--ghost" onClick={onClose}>关闭</button>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="antifraud antifraud--empty">
        <p>暂无反诈分析结果</p>
      </div>
    )
  }

  const verdictStyle = VERDICT_STYLE[{ high: 'fraud', medium: 'suspicious', low: 'safe' }[report.assessment?.risk || report.score?.level]] || VERDICT_STYLE.suspicious
  const { Icon: VerdictIcon } = verdictStyle

  return (
    <div className="antifraud" role="dialog" aria-label="反诈分析报告">
      <header className="antifraud__header">
        <div className="antifraud__title">
          <IconShield size={16} />
          <h2>反诈识别</h2>
        </div>
        <div className="antifraud__meta">
          <span className="antifraud__module">v{report.version} · {report.module}</span>
          {videoTitle && <span className="antifraud__video">{videoTitle}</span>}
        </div>
        {onClose ? (
          <button type="button" className="btn btn--ghost btn--icon" onClick={onClose} aria-label="关闭">
            <IconX size={14} />
          </button>
        ) : null}
      </header>

      {report.assessment?.reason && <p role="status">{report.assessment.reason}</p>}
      {report.message && <p role="status" className="antifraud__disclaimer">{report.message}</p>}
      {report.summary && <p className="antifraud__summary">{report.summary}</p>}

      <section className="antifraud__score">
        <div className="antifraud__score-total">
          <span className="antifraud__score-label">规则评分</span>
          <span className="antifraud__score-value">{report.score?.total ?? 0}</span>
        </div>
        <div className="antifraud__score-breakdown">
          <span>话术 {report.score?.base ?? 0}</span>
          <span>·</span>
          <span>引流 {report.score?.drainage_bonus ?? 0}</span>
        </div>
        <div className="antifraud__score-level" style={{ background: verdictStyle.bg, color: verdictStyle.text, borderColor: verdictStyle.border }}>
          <VerdictIcon size={14} /> 风险 {RISK_LABEL[report.assessment?.risk || report.score?.level] || '待定'}
        </div>
      </section>

      <DrainageBadge signals={report.drainage_signals} qrcodes={report.qrcodes} />
      <Institutions result={report.institutions} />

      {report.disclaimer && (
        <p className="antifraud__disclaimer">{report.disclaimer}</p>
      )}

      {report.claims?.length > 0 ? (
        <section className="antifraud__claims">
          {report.claims.map((c) => (
            <ClaimCard key={c.id} claim={c} />
          ))}
        </section>
      ) : (
        <p className="antifraud__empty">未生成任何 claim</p>
      )}
    </div>
  )
}
