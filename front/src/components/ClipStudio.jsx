import React, { useEffect, useMemo, useRef, useState } from 'react'
import { fetchClip, mediaUrl, saveBlob } from '../api/client'
import { fmtBytes } from '../lib/format'
import { useEvidence } from '../lib/evidence'
import { REF_URL } from './TimelineSculpture'

// The clip studio: the card a "我要这段的 GIF" message gets instead of an answer. Pick the stretch
// on a strip of keyframes (it shows the stretch's neighbourhood, so a few seconds of a long video
// are still easy to grab), watch it loop in the original, set the GIF's look — frame rate, width,
// speed, dithering, a 1 MB cap for WeChat — or take it as an MP4 with sound, then make it, see it,
// keep it. Laid out after 求原图's converter (ynvan.com), which it points to for what it doesn't do.

const MAX = { gif: 30, mp4: 60 }
const MIN = 0.3
const DITHER = [
  ['bayer', '有序抖动，文件小'],
  ['sierra', '误差扩散，画质好'],
  ['none', '不抖动，色块明显'],
]
// The picture's frame: all of it, or a rectangle (free, or locked to a common shape)
const ASPECTS = [['full', '整个画面'], ['free', '自由'], ['1:1', '1:1'], ['16:9', '16:9'], ['9:16', '9:16'], ['4:3', '4:3']]
const ratioOf = (a) => (a.includes(':') ? Number(a.split(':')[0]) / Number(a.split(':')[1]) : null)
const MIN_CROP = 0.08
/** The biggest centred rectangle of `ratio` (w/h in pixels) in a picture of shape `pic` (w/h), in fractions. */
const fit = (ratio, pic) => {
  if (!ratio) return { x: 0.1, y: 0.1, w: 0.8, h: 0.8 }
  const w = Math.min(1, ratio / pic)
  const h = Math.min(1, pic / ratio)
  return { x: (1 - w) / 2, y: (1 - h) / 2, w, h }
}

const clock = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`

/** The strip's window: the stretch with room around it (at least 30 s, or 4× the stretch). */
const windowFor = (start, end, duration) => {
  const span = Math.min(duration, Math.max(30, (end - start) * 4))
  const mid = (start + end) / 2
  const from = Math.max(0, Math.min(duration - span, mid - span / 2))
  return [from, from + span]
}

export default function ClipStudio({ jobId, title = '', duration = 0, frames = [], range, format: initialFormat = 'gif' }) {
  const playable = useEvidence().state === 'original' // else the keyframes only; the cut itself says why it can't
  const dur = duration || 0
  const [sel, setSel] = useState(() => {
    const s = Math.max(0, Math.min(range?.[0] ?? 0, dur))
    return [s, Math.min(dur || s + 3, Math.max(s + MIN, Math.min(range?.[1] ?? s + 3, s + MAX[initialFormat])))]
  })
  const [view, setView] = useState(() => windowFor(sel[0], sel[1], dur))
  const [format, setFormat] = useState(initialFormat)
  const [fps, setFps] = useState(12)
  const [width, setWidth] = useState(480)
  const [speed, setSpeed] = useState(1)
  const [dither, setDither] = useState('bayer')
  const [cap, setCap] = useState(true)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null) // { url, blob, name, size, fps, width, note, format }
  const [error, setError] = useState('')
  const [playing, setPlaying] = useState(false)
  const [aspect, setAspect] = useState('full')
  const [crop, setCrop] = useState(null) // { x, y, w, h } fractions of the picture, or null: all of it
  const [natural, setNatural] = useState([16, 9]) // the picture's pixel size, once known
  const [box, setBox] = useState([0, 0]) // the player's size on screen
  const playerRef = useRef(null)
  const cropDrag = useRef(null)
  useEffect(() => {
    const el = playerRef.current
    if (!el) return undefined
    const ro = new ResizeObserver(() => setBox([el.clientWidth, el.clientHeight]))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const pic = natural[0] / natural[1]
  // where the picture sits in the player (object-fit: contain)
  const scale = Math.min(box[0] / natural[0], box[1] / natural[1]) || 0
  const area = { w: natural[0] * scale, h: natural[1] * scale }
  area.left = (box[0] - area.w) / 2
  area.top = (box[1] - area.h) / 2
  const chooseAspect = (a) => {
    setAspect(a)
    setCrop(a === 'full' ? null : fit(ratioOf(a), pic))
    setResult(null)
  }
  const onCropDown = (what) => (e) => {
    e.preventDefault()
    e.stopPropagation()
    cropDrag.current = { what, x: e.clientX, y: e.clientY, start: crop }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const onCropMove = (e) => {
    const d = cropDrag.current
    if (!d || !area.w) return
    const dx = (e.clientX - d.x) / area.w
    const dy = (e.clientY - d.y) / area.h
    let { x, y, w, h } = d.start
    if (d.what === 'move') {
      x = Math.min(1 - w, Math.max(0, x + dx))
      y = Math.min(1 - h, Math.max(0, y + dy))
    } else {
      // a corner: the opposite corner stays put
      const left = d.what.includes('w')
      const top = d.what.includes('n')
      const ax = left ? x + w : x
      const ay = top ? y + h : y
      w = Math.max(MIN_CROP, Math.min(left ? ax : 1 - ax, w + (left ? -dx : dx)))
      h = Math.max(MIN_CROP, Math.min(top ? ay : 1 - ay, h + (top ? -dy : dy)))
      const r = ratioOf(aspect)
      if (r) { // keep the shape: the height follows the width, both shrunk to fit
        h = (w * pic) / r
        const maxH = top ? ay : 1 - ay
        if (h > maxH) { h = maxH; w = (h * r) / pic }
      }
      x = left ? ax - w : ax
      y = top ? ay - h : ay
    }
    setCrop({ x, y, w, h })
    setResult(null)
  }
  const onCropUp = () => { cropDrag.current = null }
  const cropSize = crop ? [Math.round(crop.w * natural[0]), Math.round(crop.h * natural[1])] : natural
  const videoRef = useRef(null)
  const stripRef = useRef(null)
  const drag = useRef(null)

  // The original loops over the stretch.
  useEffect(() => {
    const v = videoRef.current
    if (!v) return undefined
    const onTime = () => { if (v.currentTime >= sel[1] || v.currentTime < sel[0] - 0.5) v.currentTime = sel[0] }
    v.addEventListener('timeupdate', onTime)
    return () => v.removeEventListener('timeupdate', onTime)
  }, [sel])
  useEffect(() => {
    const v = videoRef.current
    if (v && !playing) v.currentTime = sel[0]
  }, [sel, playing])
  useEffect(() => () => { if (result?.url) URL.revokeObjectURL(result.url) }, [result])

  const toggle = () => {
    const v = videoRef.current
    if (!v) return
    if (v.paused) { v.currentTime = sel[0]; v.play().catch(() => {}); setPlaying(true) } else { v.pause(); setPlaying(false) }
  }

  const ready = useMemo(() => frames.filter((f) => f.src && f.time !== undefined), [frames])
  const thumbs = useMemo(() => {
    const n = 12
    return Array.from({ length: n }, (_, i) => {
      const t = view[0] + ((i + 0.5) / n) * (view[1] - view[0])
      return ready.reduce((best, f) => (!best || Math.abs(f.time - t) < Math.abs(best.time - t) ? f : best), null)
    })
  }, [ready, view])
  const span = view[1] - view[0] || 1
  const pct = (t) => `${((t - view[0]) / span) * 100}%`

  // Dragging a handle (or the stretch itself) on the strip.
  const timeAt = (clientX) => {
    const r = stripRef.current.getBoundingClientRect()
    return view[0] + Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * span
  }
  const onDown = (what) => (e) => {
    e.preventDefault()
    e.stopPropagation()
    drag.current = { what, from: timeAt(e.clientX), sel }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const onMove = (e) => {
    const d = drag.current
    if (!d) return
    const t = timeAt(e.clientX)
    const max = MAX[format]
    let [s, en] = d.sel
    if (d.what === 'start') s = Math.max(0, Math.min(t, en - MIN), en - max)
    else if (d.what === 'end') en = Math.min(dur, Math.max(t, s + MIN), s + max)
    else {
      const shift = Math.max(-s, Math.min(dur - en, t - d.from))
      s += shift
      en += shift
    }
    setSel([Math.round(s * 10) / 10, Math.round(en * 10) / 10])
    setResult(null)
  }
  const onUp = () => {
    if (!drag.current) return
    drag.current = null
    setView(windowFor(sel[0], sel[1], dur))
  }

  const length = sel[1] - sel[0]
  const tooLong = length > MAX[format]
  const make = async () => {
    setBusy(true)
    setError('')
    try {
      const rect = crop ? [crop.x, crop.y, crop.w, crop.h].map((v) => v.toFixed(4)).join(',') : undefined
      const look = format === 'gif' ? { fps, width, speed, dither, maxMb: cap ? 1 : 0, crop: rect } : { speed, crop: rect }
      const r = await fetchClip(jobId, sel[0], Math.min(sel[1], sel[0] + MAX[format]), format, look)
      setResult({ ...r, url: URL.createObjectURL(r.blob), size: r.blob.size, format })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="clip-studio">
      <header className="clip-studio__head">
        <h3 className="clip-studio__title">{format === 'gif' ? 'GIF' : 'MP4'} · {title || '这段视频'}</h3>
        <div className="clip-studio__formats" role="tablist" aria-label="格式">
          {['gif', 'mp4'].map((f) => (
            <button key={f} type="button" role="tab" aria-selected={format === f} onClick={() => { setFormat(f); setResult(null) }}>
              {f === 'gif' ? 'GIF 动图' : 'MP4 片段（带声音）'}
            </button>
          ))}
        </div>
      </header>
      <p className="clip-studio__hint">先选一段：{format === 'gif' ? 'GIF 最长 30 秒' : 'MP4 最长 60 秒'}</p>
      <div className="clip-studio__body">
        <div className="clip-studio__left">
          <div ref={playerRef} className="clip-studio__player">
            {playable && jobId ? (
              <video ref={videoRef} src={mediaUrl(jobId)} muted playsInline preload="metadata" onClick={toggle}
                onLoadedMetadata={(e) => e.target.videoWidth && setNatural([e.target.videoWidth, e.target.videoHeight])}
                onPause={() => setPlaying(false)} onPlay={() => setPlaying(true)} />
            ) : (
              thumbs[5]?.src ? <img src={thumbs[5].src} alt="" onLoad={(e) => e.target.naturalWidth && setNatural([e.target.naturalWidth, e.target.naturalHeight])} /> : null
            )}
            {crop && area.w ? (
              <div className="clip-studio__crop-area" style={{ left: area.left, top: area.top, width: area.w, height: area.h }}
                onPointerMove={onCropMove} onPointerUp={onCropUp} onPointerCancel={onCropUp}>
                <div className="clip-studio__crop" style={{ left: `${crop.x * 100}%`, top: `${crop.y * 100}%`, width: `${crop.w * 100}%`, height: `${crop.h * 100}%` }}
                  onPointerDown={onCropDown('move')} aria-label="截取范围，拖动移动，拖四角调整大小">
                  {['nw', 'ne', 'sw', 'se'].map((c) => <span key={c} className={`clip-studio__crop-handle clip-studio__crop-handle--${c}`} onPointerDown={onCropDown(c)} />)}
                </div>
              </div>
            ) : null}
            {playable && jobId && !playing ? <button type="button" className="clip-studio__play" onClick={toggle} aria-label="播放这一段">▶</button> : null}
          </div>
          <div className="clip-studio__aspects" role="radiogroup" aria-label="画面范围">
            <span className="clip-studio__aspects-label">画面范围</span>
            {ASPECTS.map(([a, label]) => (
              <button key={a} type="button" role="radio" aria-checked={aspect === a} onClick={() => chooseAspect(a)}>{label}</button>
            ))}
            <span className="mono-sm muted clip-studio__aspects-size">{cropSize[0]}×{cropSize[1]}</span>
          </div>
          <div ref={stripRef} className="clip-studio__strip" onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
            {thumbs.map((f, i) => <span key={i} className="clip-studio__thumb" style={f?.src ? { backgroundImage: `url(${f.src})` } : undefined} />)}
            <div className="clip-studio__sel" style={{ left: pct(sel[0]), width: `${(length / span) * 100}%` }} onPointerDown={onDown('move')}>
              <span className="clip-studio__handle clip-studio__handle--start" onPointerDown={onDown('start')} role="slider"
                aria-label="起点" aria-valuemin={0} aria-valuemax={dur} aria-valuenow={sel[0]} />
              <span className="clip-studio__handle clip-studio__handle--end" onPointerDown={onDown('end')} role="slider"
                aria-label="终点" aria-valuemin={0} aria-valuemax={dur} aria-valuenow={sel[1]} />
            </div>
          </div>
          <div className="clip-studio__readout mono-sm">
            <span>起点 <b>{clock(sel[0])}</b></span>
            <span>选了 <b>{length.toFixed(1)} 秒</b>{tooLong ? `（只取前 ${MAX[format]} 秒）` : ''}</span>
            <span>终点 <b>{clock(sel[1])}</b></span>
          </div>
        </div>
        <div className="clip-studio__right">
          {format === 'gif' ? (
            <>
              <Slider label="帧率" value={fps} unit="fps" min={5} max={30} step={1} onChange={(v) => { setFps(v); setResult(null) }} />
              <Slider label="宽度" value={width} unit="px" min={160} max={960} step={16} onChange={(v) => { setWidth(v); setResult(null) }} />
            </>
          ) : null}
          <Slider label="速度" value={speed} unit="×" min={0.5} max={2} step={0.25} onChange={(v) => { setSpeed(v); setResult(null) }} />
          {format === 'gif' ? (
            <>
              <label className="clip-studio__field">
                <span>抖动</span>
                <select value={dither} onChange={(e) => { setDither(e.target.value); setResult(null) }}>
                  {DITHER.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                </select>
              </label>
              <label className="clip-studio__check">
                <input type="checkbox" checked={cap} onChange={(e) => { setCap(e.target.checked); setResult(null) }} />
                <span><b>压到 1 MB 以内</b><small>微信里超过 1 MB 的 GIF 不会自动播放。勾着时帧率和宽度是上限，超了会自动往下降。</small></span>
              </label>
              <p className="clip-studio__note">想要文件小：降帧率、缩宽度、缩短时长。</p>
            </>
          ) : <p className="clip-studio__note">MP4 保留声音，最长 60 秒，宽度最大 1280 px。</p>}
          <button type="button" className="btn btn--dark clip-studio__make" onClick={make} disabled={busy || !jobId}>
            {busy ? '正在生成…' : result ? '重新生成' : `生成 ${format.toUpperCase()}`}
          </button>
          {error ? <p className="clip-studio__error" role="alert">{error}</p> : null}
        </div>
      </div>
      {result ? (
        <div className="clip-studio__result">
          {result.format === 'gif' ? <img src={result.url} alt="生成的 GIF" /> : <video src={result.url} controls playsInline />}
          <div className="clip-studio__result-meta">
            <p className="mono-sm">{result.name}</p>
            <p className="mono-sm muted">{fmtBytes(result.size)}{result.format === 'gif' && result.fps ? ` · ${result.fps} fps · ${result.width} px` : ''}</p>
            {result.note ? <p className="caption muted">{result.note}</p> : null}
            <button type="button" className="btn btn--dark" onClick={() => saveBlob(result.blob, result.name)}>下载</button>
          </div>
        </div>
      ) : null}
      <a className="clip-studio__ref" href={REF_URL} target="_blank" rel="noopener noreferrer">要整段无水印视频、原图，或做成实况照片？去「求原图」↗</a>
    </div>
  )
}

function Slider({ label, value, unit, min, max, step, onChange }) {
  return (
    <label className="clip-studio__slider">
      <span className="clip-studio__slider-head"><span>{label}</span><b className="mono-sm">{value} {unit}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
        style={{ '--fill': `${((value - min) / (max - min)) * 100}%` }} />
    </label>
  )
}
