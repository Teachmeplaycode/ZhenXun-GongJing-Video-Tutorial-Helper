import React from 'react'

const ORDER = [['frame', '画面'], ['speech', '原声'], ['screentext', '画面文字'], ['moment', '时间点'], ['source', '资料'], ['inference', '推断']]

// Under an answer: what its conclusions rest on, and how many citations failed the check
// (backend modules/agent/evidence.py). A failed one is shown in the text as 缺少可回看的证据.
export default function EvidenceSummary({ evidence }) {
  const summary = evidence?.summary
  if (!summary?.total) return null
  const counts = summary.counts || {}
  const failed = (evidence.items || []).filter((i) => !i.ok)
  return (
    <div className="ev-summary" data-failed={summary.failed ? '' : undefined}>
      <span className="ev-summary__label">依据</span>
      {ORDER.filter(([k]) => counts[k]).map(([k, name]) => (
        <span key={k} className={`ev-summary__item ev-chip--${k}`}>{name} {counts[k]}</span>
      ))}
      {summary.failed ? (
        <span className="ev-summary__failed" title={failed.map((i) => `${i.marker}：${i.reason}`).join('\n')}>
          {summary.failed} 条引用缺少可回看的证据
        </span>
      ) : <span className="ev-summary__ok">引用已全部核对</span>}
    </div>
  )
}
