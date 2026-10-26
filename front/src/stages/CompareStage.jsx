import React, { useEffect, useRef, useState } from 'react'
import { buildCompare, createLinkJob, getLinkJob } from '../api/client'
import CompareTable from '../components/bench/CompareTable'
import Working from '../components/Working'
import { startClientOcr } from '../lib/clientOcr'

const POLL = 4000 // ms between looks at the videos being read
const settled = (s) => !['pending', 'running'].includes(s?.status)
const STATUS = { resolving: '解析链接', reading: '抓画面、转写语音', ready: '已读完', failed: '失败' }

function BrowserOcrJob({ id, mode }) {
  useEffect(() => {
    if (!id || !['hybrid', 'local'].includes(mode)) return undefined
    return startClientOcr(id, { mode })
  }, [id, mode])
  return null
}

// Several tutorial links pasted on the homepage: each is imported as its own session, and once their
// speech and screen text are read, their step cards are lined up side by side (backend modules/compare.py).
// A step opens that session at its second.
export default function CompareStage({ links, sampling = null, onOpenSession }) {
  const [items, setItems] = useState(() => links.map((url) => ({ url, status: 'resolving', id: null, title: '', error: '' })))
  const [phase, setPhase] = useState('import') // import → compare → done | failed
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const started = useRef(false)
  const update = (i, patch) => setItems((list) => list.map((it, k) => (k === i ? { ...it, ...patch } : it)))

  useEffect(() => { // import one after another: resolving is quick, the reading runs on the server meanwhile
    if (started.current) return
    started.current = true
    ;(async () => {
      for (let i = 0; i < links.length; i += 1) {
        try {
          const job = await createLinkJob(links[i], { sampling })
          update(i, { id: job.job_id, title: job.video?.title || links[i], status: 'reading', ocrMode: sampling?.ocr_fps === 0 ? 'server' : job.video?.ocr_mode || 'server' })
        } catch (err) {
          update(i, { status: 'failed', error: err.message })
        }
      }
    })()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const reading = items.some((it) => it.status === 'reading')
  useEffect(() => {
    if (!reading) return undefined
    const timer = setInterval(() => {
      items.forEach((it, i) => {
        if (it.status !== 'reading') return
        getLinkJob(it.id).then((s) => {
          if (!s.running && settled(s.transcript) && settled(s.screentext)) update(i, { status: 'ready' })
        }).catch(() => {}) // looked at again next time
      })
    }, POLL)
    return () => clearInterval(timer)
  }, [reading, items])

  const ready = items.filter((it) => it.status === 'ready')
  const allSettled = items.every((it) => it.status === 'ready' || it.status === 'failed')
  const compare = async () => {
    setPhase('compare')
    setError('')
    try {
      setResult(await buildCompare(ready.map((it) => it.id)))
      setPhase('done')
    } catch (err) {
      setError(err.message)
      setPhase('failed')
    }
  }
  useEffect(() => {
    if (phase !== 'import' || !allSettled) return
    if (ready.length >= 2) compare()
    else {
      setError('能读完的视频不到 2 个，没法对照。检查失败的链接，或换几个教程再试。')
      setPhase('failed')
    }
  }, [allSettled, phase]) // eslint-disable-line react-hooks/exhaustive-deps

  const jump = (v, cell) => onOpenSession?.(v.id, cell.time)
  return (
    <section className="compare-stage" aria-label="教程对照">
      {items.filter(it => it.status === 'reading' && it.id).map(it => <BrowserOcrJob key={it.id} id={it.id} mode={it.ocrMode} />)}
      <header className="compare-stage__head">
        <span className="eyebrow">教程对照 · {links.length} 个</span>
        <h2>{phase === 'done' ? '对照好了' : phase === 'failed' ? '没能对照' : '正在读这几个教程'}</h2>
        <p className="body-sm muted">每个链接都会成为一个会话，在「历史」里能单独打开；对照表里点任意一步，直接打开那个教程的那一秒。</p>
      </header>
      <ol className="compare-stage__videos">
        {items.map((it, i) => (
          <li key={it.url} data-status={it.status}>
            <span className="compare-stage__n mono-sm">{i + 1}</span>
            <span className="compare-stage__video">
              <strong>{it.title || it.url}</strong>
              <span className="caption muted">{it.error || STATUS[it.status]}</span>
            </span>
            {it.status === 'ready' && it.id ? <button type="button" className="link-btn" onClick={() => onOpenSession?.(it.id)}>打开</button> : null}
          </li>
        ))}
      </ol>
      {phase === 'import' ? <Working label="正在读这几个教程" hint="抓关键帧、转写语音、识别画面文字，几个一起读，几分钟内好。" /> : null}
      {phase === 'compare' ? <Working label="正在整理步骤并对照" hint="每个教程先整理成步骤，再把同一个操作对成一行，一般一分钟内。" /> : null}
      {error ? (
        <p className="bench__error">{error}{phase === 'failed' && ready.length >= 2 ? <button type="button" className="link-btn" onClick={compare}>再试一次</button> : null}</p>
      ) : null}
      {result?.status === 'done' ? <div className="compare-tab compare-stage__table"><CompareTable result={result} onJump={jump} /></div> : null}
      {result && result.status !== 'done' ? <p className="body-sm muted">{result.message}</p> : null}
    </section>
  )
}
