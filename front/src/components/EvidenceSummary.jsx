import React, { useEffect, useState } from 'react'

const ORDER = [['frame', '画面'], ['speech', '原声'], ['screentext', '画面文字'], ['moment', '时间点'], ['source', '资料'], ['inference', '推断']]

const CITES_KEY = 'zhenxun.cites.v1'
const readCites = () => {
  try { return localStorage.getItem(CITES_KEY) === '1' } catch { return false }
}

/** Whether answers show their evidence chips (画面 01:32 …) inline. Off by default — readers said they
 *  get in the way of reading. One switch for every answer: turning it on under one answer turns it
 *  on under all of them (and for the answers to come). */
const CITES_EVENT = 'zhenxun:cites'
export function useCiteChips() {
  const [on, setOn] = useState(readCites)
  useEffect(() => {
    const sync = (e) => setOn(Boolean(e.detail))
    window.addEventListener(CITES_EVENT, sync)
    return () => window.removeEventListener(CITES_EVENT, sync)
  }, [])
  const set = (v) => {
    try { localStorage.setItem(CITES_KEY, v ? '1' : '0') } catch { /* fine */ }
    window.dispatchEvent(new CustomEvent(CITES_EVENT, { detail: v }))
  }
  return [on, set]
}

// Under an answer: what its conclusions rest on, and how many citations failed the check
// (backend modules/agent/evidence.py). A failed one is shown in the text as 缺少可回看的证据.
// `onCites` toggles the inline chips (hidden by default; see useCiteChips).
export default function EvidenceSummary({ evidence, cites = true, onCites = null }) {
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
      {onCites ? (
        <button type="button" className="link-btn ev-summary__toggle" aria-pressed={cites} onClick={() => onCites(!cites)}
          title={cites ? '收起正文里的时间标签，读起来更顺' : '在正文里标出每句话对应的画面、原声和时间，点一下可回看'}>
          {cites ? '隐藏时间标签' : '显示时间标签'}
        </button>
      ) : null}
    </div>
  )
}
