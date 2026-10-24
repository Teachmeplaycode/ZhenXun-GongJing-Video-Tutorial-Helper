import React, { useEffect, useState } from 'react'
import { buildCompare, getCompare, linkFrameUrl, listSessions } from '../../api/client'
import { fmtClock } from '../../lib/format'

const MAX_OTHERS = 2
const LAST_KEY = (jobId) => `compare.last.${jobId}` // the videos last compared with this one

// Tutorials of the same task side by side (backend modules/compare.py): one row per operation with
// each video's step for it, what differs, and which video suits whom. This video's times seek its
// timeline; another video's time opens that session at that second.
export default function CompareTab({ video, onSeek = null, onOpenSession = null }) {
  const jobId = video?.jobId
  const [sessions, setSessions] = useState(null)
  const [picked, setPicked] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!jobId) return undefined
    const ctrl = new AbortController()
    listSessions({ signal: ctrl.signal })
      .then((list) => setSessions(list.filter((s) => s.id !== jobId && s.kind !== 'images')))
      .catch((err) => { if (err.name !== 'AbortError') setError(err.message) })
    let last = []
    try {
      last = JSON.parse(localStorage.getItem(LAST_KEY(jobId)) || '[]')
    } catch {
      last = []
    }
    if (last.length) {
      getCompare([jobId, ...last], { signal: ctrl.signal })
        .then((r) => { if (r.status === 'done') { setResult(r); setPicked(last) } })
        .catch(() => {})
    }
    return () => ctrl.abort()
  }, [jobId])

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < MAX_OTHERS ? [...p, id] : p))
  const start = async () => {
    setBusy(true)
    setError('')
    try {
      const r = await buildCompare([jobId, ...picked])
      setResult(r)
      try {
        localStorage.setItem(LAST_KEY(jobId), JSON.stringify(picked))
      } catch {
        // private mode: the table still shows for this visit
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  const jump = (v, cell) => (v.id === jobId ? onSeek?.(cell.time) : onOpenSession?.(v.id, cell.time))

  if (!jobId) return <p className="bench__note muted">导入视频后可以和别的教程对照。</p>
  return (
    <div className="compare-tab">
      {result?.status === 'done' ? (
        <>
          <header className="steps-tab__head">
            <span className="eyebrow">教程对照</span>
            <button type="button" className="link-btn" onClick={() => setResult(null)}>换一组</button>
          </header>
          <ul className="compare-tab__videos">
            {result.videos.map((v) => (
              <li key={v.id}>
                <span className="compare-tab__label">{v.label}</span>
                <span className="compare-tab__vbody">
                  <strong>{v.title}{v.id === jobId ? '（当前）' : ''}</strong>
                  {v.trait ? <span className="caption muted">{v.trait}</span> : null}
                </span>
              </li>
            ))}
          </ul>
          {result.summary ? <p className="compare-tab__summary body-sm">{result.summary}</p> : null}
          <p className="caption muted compare-tab__count">{result.message}</p>
          <ol className="compare-tab__rows">
            {result.rows.map((r, i) => (
              <li key={`${i}-${r.op}`} className="compare-row">
                <strong className="compare-row__op">{r.op}</strong>
                {r.note ? <span className="caption muted">{r.note}</span> : null}
                <span className="compare-row__cells">
                  {r.cells.map((c, k) => {
                    const v = result.videos[k]
                    return c ? (
                      <button key={v.id} type="button" className="compare-cell" onClick={() => jump(v, c)}
                        title={`${v.label} 第 ${c.n} 步：${c.action}${v.id === jobId ? '' : '（打开那个教程）'}`}>
                        {c.frame != null ? <img src={linkFrameUrl(v.id, c.frame)} alt="" loading="lazy" /> : <span className="compare-cell__blank" />}
                        <span className="compare-cell__tag mono-sm">{v.label} · {fmtClock(c.time)}</span>
                      </button>
                    ) : <span key={v.id} className="compare-cell compare-cell--none mono-sm">{v.label} 没讲</span>
                  })}
                </span>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <div className="compare-tab__pick">
          <h3>和别的教程对照</h3>
          <p className="body-sm muted">选 1 到 {MAX_OTHERS} 个讲同一件事的教程：按操作对齐每一步，写出谁讲了、谁跳过了，哪个更适合你。没整理步骤的会先整理。</p>
          {sessions === null ? <p className="caption muted">读取会话…</p> : !sessions.length ? (
            <p className="caption muted">还没有别的视频。先导入另一个讲同样操作的教程。</p>
          ) : (
            <ul className="compare-tab__list">
              {sessions.map((s) => (
                <li key={s.id}>
                  <label className="compare-pick">
                    <input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s.id)}
                      disabled={!picked.includes(s.id) && picked.length >= MAX_OTHERS} />
                    {s.cover_index != null ? <img src={linkFrameUrl(s.id, s.cover_index)} alt="" loading="lazy" /> : <span className="compare-cell__blank" />}
                    <span className="compare-pick__title">{s.title}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="btn btn--dark" onClick={start} disabled={busy || !picked.length}>
            {busy ? '对照中…（可能要半分钟）' : picked.length ? `对照这 ${picked.length + 1} 个教程` : '先选一个教程'}
          </button>
          <p className="caption muted">算一次提问。</p>
        </div>
      )}
      {error ? <p className="bench__error">{error}</p> : null}
    </div>
  )
}
