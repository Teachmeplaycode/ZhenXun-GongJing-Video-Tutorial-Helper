import React from 'react'
import { stepShotUrl } from '../../api/client'
import { fmtClock } from '../../lib/format'

// The comparison of 2–5 tutorials (backend modules/compare.py): each video with its label and what it
// suits, the summary, then one row per operation with each video's step. `onJump(video, cell)` opens a
// step; `currentId` marks the video being watched (the 对照 tab), none on the homepage's comparison.
export default function CompareTable({ result, currentId = null, onJump }) {
  return (
    <>
      <ul className="compare-tab__videos">
        {result.videos.map((v) => (
          <li key={v.id}>
            <span className="compare-tab__label">{v.label}</span>
            <span className="compare-tab__vbody">
              <strong>{v.title}{v.id === currentId ? '（当前）' : ''}</strong>
              {v.trait ? <span className="caption muted">{v.trait}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      {result.summary ? <p className="compare-tab__summary body-sm">{result.summary}</p> : null}
      <p className="caption muted compare-tab__count">
        {result.message}{result.skipped?.length ? `；没整理出步骤、未参与对照：${result.skipped.join('、')}` : ''}
      </p>
      <ol className="compare-tab__rows">
        {result.rows.map((r, i) => (
          <li key={`${i}-${r.op}`} className="compare-row">
            <strong className="compare-row__op">{r.op}</strong>
            {r.note ? <span className="caption muted">{r.note}</span> : null}
            <span className="compare-row__cells">
              {r.cells.map((c, k) => {
                const v = result.videos[k]
                return c ? (
                  <button key={v.id} type="button" className="compare-cell" onClick={() => onJump?.(v, c)}
                    title={`${v.label} 第 ${c.n} 步：${c.action}${v.id === currentId ? '' : '（打开那个教程）'}`}>
                    {c.frame != null || c.shot ? <img src={stepShotUrl(v.id, c)} alt="" loading="lazy" /> : <span className="compare-cell__blank" />}
                    <span className="compare-cell__tag mono-sm">{v.label} · {fmtClock(c.time)}</span>
                  </button>
                ) : <span key={v.id} className="compare-cell compare-cell--none mono-sm">{v.label} 没讲</span>
              })}
            </span>
          </li>
        ))}
      </ol>
    </>
  )
}
