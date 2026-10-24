import React, { useState } from 'react'
import { fmtClock } from '../lib/format'
import { asText } from '../recipe/graph'

// 抄作业 in the answer (backend modules/recipe.py): what was found, tree by tree, and the way to the
// full node canvas (#/recipe/<jobId>, recipe/RecipeCanvas.jsx), where every node is drawn the way
// Blender draws it and can be moved; versions and moments to check stay here, next to the answer.
export default function RecipeReport({ report, onSeek = null }) {
  const [copied, setCopied] = useState(false)
  const trees = report.trees || []
  const open = () => window.open(`${window.location.pathname}#/recipe/${report.job_id}`, '_blank', 'noopener')
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asText(report))
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }
  const at = (t) => (t != null && onSeek ? <button type="button" className="link-btn mono-sm" onClick={() => onSeek(t)}>{fmtClock(t)}</button> : null)
  return (
    <div className="recipe">
      <p className="recipe__goal"><strong>{report.goal}</strong>{report.software ? <span className="muted"> · {report.software}{report.version ? ` ${report.version}` : ''}</span> : null}</p>
      <ul className="recipe__trees">
        {trees.map((t, i) => (
          <li key={t.name + i}>
            <strong>{t.name}</strong>
            <span className="mono-sm muted">{t.nodes.length} 个节点 · {t.links.length} 条连线</span>
            <span className="caption muted recipe__names">{t.nodes.slice(0, 6).map((n) => n.name).join('、')}{t.nodes.length > 6 ? '…' : ''}</span>
          </li>
        ))}
      </ul>
      <div className="recipe__actions">
        {report.job_id ? <button type="button" className="btn btn--dark btn--sm" onClick={open}>打开节点画布</button> : null}
        <button type="button" className="btn btn--ghost btn--sm" onClick={copy}>{copied ? '已复制' : '复制为文字'}</button>
      </div>
      {report.version_notes?.length ? (
        <section className="recipe__notes">
          <h4>不同版本</h4>
          <ul>{report.version_notes.map((v, i) => <li key={i}><span className="mono-sm muted">{v.source}</span> {v.text}</li>)}</ul>
        </section>
      ) : null}
      {report.unsure?.length ? (
        <section className="recipe__notes">
          <h4>看不清，建议回看</h4>
          <ul>{report.unsure.map((u, i) => <li key={i}>{u.text} {at(u.time)}</li>)}</ul>
        </section>
      ) : null}
    </div>
  )
}
