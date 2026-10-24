import React, { useEffect, useState } from 'react'
import { buildCompare, createLinkJob, getCompare, getRelated, linkFrameUrl, listSessions } from '../../api/client'
import { fmtClock } from '../../lib/format'
import Working from '../Working'

const MAX_OTHERS = 2
const POLL = 4000 // ms between looks at a recommended video being imported for comparison
const views = (n) => (n >= 10000 ? `${(n / 10000).toFixed(n >= 100000 ? 0 : 1)} 万` : String(n))
const bvid = (url) => url.replace(/\/$/, '').split('/').pop()
const LAST_KEY = (jobId) => `compare.last.${jobId}` // the videos last compared with this one

// Tutorials of the same task side by side (backend modules/compare.py): one row per operation with
// each video's step for it, what differs, and which video suits whom. This video's times seek its
// timeline; another video's time opens that session at that second.
export default function CompareTab({ video, onSeek = null, onOpenSession = null, onBusy = null }) {
  const jobId = video?.jobId
  const [sessions, setSessions] = useState(null)
  const [picked, setPicked] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [related, setRelated] = useState(null)
  const [importing, setImporting] = useState(null) // { url, title, id } being parsed in the background

  const refresh = (signal) => listSessions({ signal })
    .then((list) => { const others = list.filter((s) => s.id !== jobId && s.kind !== 'images'); setSessions(others); return others })

  useEffect(() => {
    if (!jobId) return undefined
    const ctrl = new AbortController()
    refresh(ctrl.signal).catch((err) => { if (err.name !== 'AbortError') setError(err.message) })
    getRelated(jobId, { signal: ctrl.signal }).then(setRelated).catch(() => {})
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
  // A recommended video: import it here without leaving this one, then tick it once its speech is read.
  useEffect(() => {
    if (!importing?.id) return undefined
    let stop = false
    const look = async () => {
      try {
        const others = await refresh()
        const s = others.find((x) => x.id === importing.id)
        if (s && !['pending', 'running'].includes(s.transcript)) {
          setPicked((p) => (p.includes(s.id) || p.length >= MAX_OTHERS ? p : [...p, s.id]))
          setRelated((r) => r && { ...r, items: r.items.map((it) => (it.url === importing.url ? { ...it, imported: true } : it)) })
          setImporting(null)
          return
        }
      } catch {
        // try again on the next look
      }
      if (!stop) timer = setTimeout(look, POLL)
    }
    let timer = setTimeout(look, POLL)
    return () => { stop = true; clearTimeout(timer) }
  }, [importing?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const importRelated = async (it) => {
    setError('')
    setImporting({ url: it.url, title: it.title, id: null })
    try {
      const r = await createLinkJob(it.url)
      setImporting({ url: it.url, title: it.title, id: r.job_id })
    } catch (err) {
      setImporting(null)
      setError(err.message)
    }
  }
  const tickImported = (it) => {
    const s = (sessions || []).find((x) => x.video_id === bvid(it.url))
    if (s) setPicked((p) => (p.includes(s.id) || p.length >= MAX_OTHERS ? p : [...p, s.id]))
  }

  useEffect(() => { onBusy?.(busy || Boolean(importing)) }, [busy, importing]) // eslint-disable-line react-hooks/exhaustive-deps
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
          {related?.status === 'done' && related.items.length ? (
            <section className="related">
              <h4>B 站相关教程</h4>
              <p className="caption muted">B 站在这个视频旁边推荐的，按和标题的相近程度排。导入后会自动勾上。</p>
              {importing ? <Working label={`正在解析：${importing.title.slice(0, 24)}`} hint="抓关键帧、转写语音，几分钟内好；好了会自动勾上，不用一直等在这里。" /> : null}
              <ul className="related__list">
                {related.items.map((it) => (
                  <li key={it.url} className="related__item">
                    <a href={it.url} target="_blank" rel="noopener noreferrer" className="related__cover" title="在 B 站打开">
                      {it.cover ? <img src={`${it.cover}@160w_90h_1c.webp`} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="compare-cell__blank" />}
                    </a>
                    <span className="related__body">
                      <span className="related__title">{it.title}</span>
                      <span className="caption muted">{it.author} · {fmtClock(it.duration)} · {views(it.views)} 播放</span>
                    </span>
                    {it.imported
                      ? <button type="button" className="btn btn--ghost btn--sm" onClick={() => tickImported(it)}>已导入，勾上</button>
                      : <button type="button" className="btn btn--ghost btn--sm" onClick={() => importRelated(it)} disabled={Boolean(importing)}>导入</button>}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {busy ? <Working label="正在对照这几个教程" hint="没整理步骤的先整理，再把同一个操作对成一行。一般半分钟到一分钟。" /> : null}
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
