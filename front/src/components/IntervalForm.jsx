import React, { useEffect, useRef, useState } from 'react'

const MAX_RANGE = 10 // s, one replay (backend modules/frames/replay.py)

// "83", "1:23", "01:23.5", "1:02:03" → seconds; anything else → null.
export function parseTime(text) {
  const t = String(text || '').trim().replace('：', ':')
  if (!/^\d+(?:\.\d+)?$|^\d{1,2}(?::\d{1,2}){1,2}(?:\.\d+)?$/.test(t)) return null
  return t.split(':').reduce((acc, n) => acc * 60 + Number(n), 0)
}

const fine = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`

// What's wrong with a typed range, or '' when it can be replayed.
export function checkRange(start, end, duration) {
  if (start == null || end == null) return '时间格式不对：可以写 83、1:23 或 01:23.5'
  if (end <= start) return '结束要晚于开始'
  if (duration && start >= duration) return `开始超过了视频长度（${fine(duration)}）`
  if (end - start > MAX_RANGE) return `一次最多慢放 ${MAX_RANGE} 秒，现在是 ${(end - start).toFixed(1)} 秒`
  return ''
}

// A small form for a stretch typed by hand (long videos make dragging on the timeline imprecise).
// onRange(start, end, 'play' | 'ask'); busy disables 'play' while an answer is running.
export default function IntervalForm({ duration, busy, onRange, onClose }) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [touched, setTouched] = useState(false)
  const ref = useRef(null)
  const start = parseTime(a)
  const end0 = parseTime(b)
  const end = end0 != null && duration ? Math.min(end0, duration) : end0
  const problem = checkRange(start, end, duration)
  useEffect(() => {
    ref.current?.querySelector('input')?.focus()
    const onDown = (e) => { if (!ref.current?.contains(e.target) && !e.target.closest('.timeline__interval-btn')) onClose() }
    window.addEventListener('pointerdown', onDown)
    return () => window.removeEventListener('pointerdown', onDown)
  }, [onClose])
  const go = (action) => {
    setTouched(true)
    if (problem || (action === 'play' && busy)) return
    onRange(Math.round(start * 10) / 10, Math.round(end * 10) / 10, action)
    onClose()
  }
  return (
    <form ref={ref} className="interval-form" aria-label="输入慢放区间"
      onSubmit={(e) => { e.preventDefault(); go(busy ? 'ask' : 'play') }}
      onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); onClose() } }}>
      <div className="interval-form__row">
        <label>开始<input value={a} onChange={(e) => setA(e.target.value)} placeholder="1:23" inputMode="decimal" aria-invalid={touched && start == null} /></label>
        <span aria-hidden="true">–</span>
        <label>结束<input value={b} onChange={(e) => setB(e.target.value)} placeholder="1:26.5" inputMode="decimal" aria-invalid={touched && end == null} /></label>
      </div>
      <p className={`caption ${touched && problem ? 'interval-form__error' : 'muted'}`} role={touched && problem ? 'alert' : undefined}>
        {touched && problem ? problem : start != null && end != null && !problem ? `${fine(start)} – ${fine(end)} · ${(end - start).toFixed(1)} 秒` : `最长 ${MAX_RANGE} 秒；视频长 ${duration ? fine(duration) : '未知'}`}
      </p>
      <div className="interval-form__actions">
        <button type="submit" className="btn btn--dark" disabled={busy} title={busy ? '正在回答，结束后再慢放' : '直接逐帧慢放，不经过模型'}>直接慢放</button>
        <button type="button" className="btn btn--ghost" onClick={() => go('ask')}>带着这段提问</button>
      </div>
    </form>
  )
}
