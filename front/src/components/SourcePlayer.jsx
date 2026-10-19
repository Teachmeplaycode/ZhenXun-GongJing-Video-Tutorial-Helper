import React, { useEffect, useRef, useState } from 'react'
import { IconClose } from './Icons'
import { mediaUrl } from '../api/client'

const LEAD = 1 // seconds of context before the cited moment
const clock = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}`

// The original video, opened at a cited moment ("回看原片"). request: { time, key } from a clicked
// time; a new key seeks again even to the same time. onFallback(time): the original couldn't be
// played, show the cached frames instead.
export default function SourcePlayer({ jobId, request, label = '原片', onClose, onFallback }) {
  const ref = useRef(null)
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(true) // fetching from the platform: the first seconds after import share the line
  const [now, setNow] = useState(request?.time ?? 0)

  useEffect(() => {
    const video = ref.current
    if (!video || !request) return
    setFailed(false)
    setLoading(true)
    const go = () => {
      video.currentTime = Math.max(0, request.time - LEAD)
      video.play().catch(() => {}) // a click started this, so sound may play; if not, the controls are there
    }
    if (video.readyState >= 1) go()
    else video.addEventListener('loadedmetadata', go, { once: true })
    return () => video.removeEventListener('loadedmetadata', go)
  }, [request])

  if (!request) return null
  return (
    <aside className="source-player" aria-label={`${label}，从 ${clock(request.time)} 播放`}>
      <header className="source-player__head">
        <span className="source-player__badge">回看原片</span>
        <span className="source-player__time mono-sm">{clock(request.time)} · 正在 {clock(now)}</span>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭原片"><IconClose size={14} /></button>
      </header>
      {failed ? (
        <div className="source-player__failed">
          <p>原视频暂时播放不了（平台链接可能已失效）。</p>
          <button type="button" className="btn btn--ghost" onClick={() => onFallback?.(request.time)}>改看 {clock(request.time)} 的缓存画面</button>
        </div>
      ) : (
        <div className="source-player__frame">
          <video
            ref={ref}
            className="source-player__video"
            src={mediaUrl(jobId)}
            controls
            playsInline
            preload="metadata"
            onTimeUpdate={(e) => setNow(e.currentTarget.currentTime)}
            onError={() => setFailed(true)}
            onWaiting={() => setLoading(true)}
            onSeeking={() => setLoading(true)}
            onCanPlay={() => setLoading(false)}
            onPlaying={() => setLoading(false)}
          />
          {loading ? <span className="source-player__loading" role="status">正在加载原片…</span> : null}
        </div>
      )}
      <p className="source-player__note caption muted">{label} · 从引用时间前 {LEAD} 秒开始播放</p>
    </aside>
  )
}
