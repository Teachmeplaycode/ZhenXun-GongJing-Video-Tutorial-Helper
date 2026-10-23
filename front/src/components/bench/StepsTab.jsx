import React, { useEffect, useState } from 'react'
import { buildSteps, getSteps, linkFrameUrl } from '../../api/client'
import { fmtClock } from '../../lib/format'
import { IconFilm } from '../Icons'

// Step cards (backend modules/steps.py): what the tutorial has you do, in order, each at its second
// with the frame from that moment. A card's time jumps the timeline there; 「卡在这步」 starts a
// question about that step, to send with a screenshot.
export default function StepsTab({ video, onSeek = null, onStuck = null }) {
  const jobId = video?.jobId
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!jobId) return undefined
    const ctrl = new AbortController()
    getSteps(jobId, { signal: ctrl.signal }).then(setState).catch((err) => { if (err.name !== 'AbortError') setError(err.message) })
    return () => ctrl.abort()
  }, [jobId])

  const start = async () => {
    setBusy(true)
    setError('')
    try {
      setState(await buildSteps(jobId))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!jobId) return <p className="bench__note muted">导入视频后可以整理操作步骤。</p>
  const list = state?.status === 'done' ? state.steps || [] : []
  const running = busy || state?.status === 'running'
  return (
    <div className="steps-tab">
      {list.length ? (
        <>
          <header className="steps-tab__head">
            <span className="eyebrow">操作步骤</span>
            <span className="mono-sm muted">{list.length} 步 · 点时间回到那一秒</span>
          </header>
          <ol className="steps-tab__list">
            {list.map((s) => (
              <li key={`${s.n}-${s.time}`} className="step-card">
                <button type="button" className="step-card__shot" onClick={() => onSeek?.(s.time)} aria-label={`回到 ${fmtClock(s.time)}`}>
                  {s.frame != null ? <img src={linkFrameUrl(jobId, s.frame)} alt="" loading="lazy" /> : <span />}
                  <span className="step-card__no mono-sm">{String(s.n).padStart(2, '0')}</span>
                </button>
                <div className="step-card__body">
                  <strong>{s.action}</strong>
                  {s.detail ? <span className="caption muted">{s.detail}</span> : null}
                  <span className="step-card__actions">
                    <button type="button" className="step-card__time mono-sm" onClick={() => onSeek?.(s.time)}>{fmtClock(s.time)}</button>
                    {onStuck ? <button type="button" className="link-btn" onClick={() => onStuck(s)}>卡在这步</button> : null}
                  </span>
                </div>
              </li>
            ))}
          </ol>
          <button type="button" className="link-btn steps-tab__redo" onClick={start} disabled={running}>{running ? '整理中…' : '重新整理'}</button>
        </>
      ) : (
        <div className="bench__idle">
          <IconFilm size={28} />
          <h3>{running ? '正在整理步骤…' : '整理操作步骤'}</h3>
          <p className="body-sm muted">把教程里要你亲手做的操作按顺序列成卡片：每一步写清点哪里、填什么，配上那一刻的画面，点时间就回到原视频那一秒。</p>
          {state?.status === 'empty' ? <p className="caption muted">{state.message}</p> : null}
          <button type="button" className="btn btn--dark" onClick={start} disabled={running}>{running ? '整理中…' : state?.status === 'empty' ? '再试一次' : '整理步骤'}</button>
          <p className="caption muted">算一次提问，大约十几秒。</p>
        </div>
      )}
      {error ? <p className="bench__error">{error}</p> : null}
    </div>
  )
}
