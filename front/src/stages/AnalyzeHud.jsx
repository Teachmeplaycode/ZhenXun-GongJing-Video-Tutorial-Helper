import React, { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { IconAlert, IconArrowRight, IconCheck, IconRefresh } from '../components/Icons'
import { fmtBytes, fmtTime } from '../lib/format'
import { EASE } from '../lib/motion'

const StepState = ({ state }) =>
  state === 'done' ? <IconCheck size={14} /> : state === 'running' ? <span className="spinner-dot" />
    : state === 'warn' ? <IconAlert size={14} /> : <span className="hud__idle" />

// Transcript status from the backend → step state and the short value shown beside it.
export function speechStep(t) {
  if (!t) return { state: 'pending', value: '' }
  switch (t.status) {
    case 'running': return { state: 'running', value: t.message || '转写中' }
    case 'done': return { state: 'done', value: `${t.count} 句` }
    case 'empty': return { state: 'done', value: '没有语音' }
    case 'none': return { state: 'done', value: '没有音轨' }
    case 'unavailable': return { state: 'warn', value: '未安装识别' }
    case 'failed': return { state: 'warn', value: '失败' }
    default: return { state: 'pending', value: '' }
  }
}

// On-screen text (subtitles, captions) read once per second across the whole video.
export function screenStep(t) {
  if (!t) return { state: 'pending', value: '' }
  switch (t.status) {
    case 'running': return { state: 'running', value: t.message || '识别中' }
    case 'done': return { state: 'done', value: `${t.count} 段` }
    case 'empty': return { state: 'done', value: '画面没有文字' }
    case 'unavailable': return { state: 'warn', value: '本机不支持' }
    case 'failed': return { state: 'warn', value: '失败' }
    default: return { state: 'pending', value: t.message?.startsWith('排队') ? t.message.replace('识别画面文字', '') : '' }
  }
}

// One compact progress panel keeps the animated sculpture unobstructed.
const PLATFORM_NAMES = { bilibili: 'B 站', wechat_channels: '视频号', local: '本地文件' }

// canEnterEarly: enough link frames arrived to start chatting while the rest keep coming.
// onRetry: re-sample missing link frames (null for local files).
export default function AnalyzeHud({ meta, analysis, frames, ready, notice, onNext, canEnterEarly = false, onRetry = null, retrying = false }) {
  const nextRef = useRef(null)
  useLayoutEffect(() => {
    if (ready && nextRef.current) {
      gsap.fromTo(nextRef.current, { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: 0.4, ease: EASE.bounce })
    }
  }, [ready])

  const settled = analysis.frames + (analysis.missing || 0)
  const framesDone = Boolean(analysis.total) && settled >= analysis.total
  const pictures = meta.kind === 'images' // an image post or uploaded pictures: no time axis, no speech
  const steps = pictures ? [
    meta.link
      ? { key: 'upload', label: '解析链接', value: `${PLATFORM_NAMES[meta.platform] || meta.platform} · 图集`, state: 'done' }
      : { key: 'upload', label: '上传图片', value: meta.size ? fmtBytes(meta.size) : '已上传', state: 'done' },
    {
      key: 'frames',
      label: '读取图片',
      value: analysis.total ? `${analysis.frames} / ${analysis.total} 张` : '',
      state: framesDone ? 'done' : 'running',
      progress: analysis.total ? settled / analysis.total : 0,
    },
    ...(analysis.screentext ? [{ key: 'screen', label: '图片文字', ...screenStep(analysis.screentext) }] : []),
  ] : [
    meta.link
      ? { key: 'upload', label: '解析链接', value: `${PLATFORM_NAMES[meta.platform] || meta.platform} · ${meta.videoId}${meta.partCount > 1 ? ` · P${meta.part}` : ''}`, state: 'done' }
      : { key: 'upload', label: '上传视频', value: meta.sample ? '示例素材' : meta.size ? fmtBytes(meta.size) : '已上传', state: 'done' },
    {
      key: 'meta',
      label: '读取元数据',
      value: analysis.meta ? `${fmtTime(meta.duration)}${meta.author ? ` · ${meta.author}` : ''}${meta.width ? ` · ${meta.width}×${meta.height}` : ''}` : '',
      state: analysis.meta ? 'done' : 'running',
    },
    {
      key: 'frames',
      label: '抓取关键帧',
      value: analysis.total ? `${analysis.frames} / ${analysis.total}` : '',
      state: framesDone ? 'done' : analysis.meta ? 'running' : 'pending',
      progress: analysis.total ? settled / analysis.total : 0,
    },
    {
      key: 'index',
      label: '建立时间轴索引',
      value: analysis.index ? `${analysis.total} 段` : '',
      state: analysis.index ? 'done' : framesDone ? 'running' : 'pending',
    },
    ...(meta.backend ? [{ key: 'speech', label: '语音转写', ...speechStep(analysis.transcript) }] : []),
    ...(meta.backend && analysis.screentext ? [{ key: 'screen', label: '画面文字', ...screenStep(analysis.screentext) }] : []),
  ]
  const transcriptFailed = analysis.transcript?.status === 'failed'
  const screenFailed = analysis.screentext?.status === 'failed'
  const retryLabel = [analysis.missing ? `缺失的 ${analysis.missing} 帧` : '', transcriptFailed ? '语音转写' : '', screenFailed ? '画面文字' : '']
    .filter(Boolean).join('和')
  const frameMap = new Map(frames.map((frame) => [frame.index, frame]))
  const frameSlots = Array.from({ length: analysis.total || frames.length }, (_, index) => (
    frameMap.get(index) || { index, src: null, status: 'pending' }
  ))
  const activeFrame = frames.reduce((latest, frame) => (frame.src ? Math.max(latest, frame.index) : latest), -1)
  const frameProgress = analysis.total ? Math.min(1, settled / analysis.total) : 0

  return (
    <>
      <div className="hud" data-ready={ready || undefined}>
        <div className="hud__head">
          <div className="hud__state" data-status={ready ? 'done' : 'running'}>
            <span className="hud__state-mark">{ready ? <IconCheck size={16} /> : <span className="spinner-dot" />}</span>
            <span className="hud__state-copy">
              <strong>{ready ? '视频切帧完成' : '正在切分视频帧'}</strong>
              <small>{ready ? `已生成 ${analysis.frames} 个可检索画面` : '请保持页面开启，画面将逐帧生成'}</small>
            </span>
          </div>
          <span className="mono-sm hud__file">{meta.name}</span>
        </div>
        <p className="hud__patience">
          {ready ? '时间轴索引已经建立，可以进入对话继续理解与核验。' : '正在识别画面变化并建立时间轴，请耐心等待片刻。视频越长，处理时间可能越久。'}
        </p>
        <ol className="hud__steps">
          {steps.map((s) => (
            <li key={s.key} className="hud__step" data-status={s.state}>
              <StepState state={s.state} />
              <span className="hud__label">{s.label}</span>
              <span className="hud__value mono-sm">
                {s.key === 'frames' && analysis.total ? <>{analysis.frames} / {analysis.total}</> : s.value}
                {s.key === 'frames' && analysis.missing ? <em className="hud__missing">缺 {analysis.missing}</em> : null}
              </span>
              {s.key === 'frames' && s.state !== 'pending' ? (
                <span className="hud__bar"><span style={{ transform: `scaleX(${s.progress})` }} /></span>
              ) : null}
            </li>
          ))}
        </ol>
        {analysis.status && !ready ? <div className="hud__status mono-sm">{analysis.status}</div> : null}
        {notice ? <div className="hud__notice"><IconAlert size={14} />{notice}</div> : null}
        {transcriptFailed && analysis.transcript.message ? <div className="hud__status mono-sm">{analysis.transcript.message}</div> : null}
        {screenFailed && analysis.screentext.message ? <div className="hud__status mono-sm">{analysis.screentext.message}</div> : null}
        {ready && onRetry && retryLabel ? (
          <button type="button" className="link-btn hud__retry" onClick={onRetry} disabled={retrying}>
            <IconRefresh size={13} />{retrying ? '补抓中…' : `重试${retryLabel}`}
          </button>
        ) : null}
      </div>

      <div className="filmstrip-shell" data-ready={ready || undefined} aria-live="polite">
        <div className="filmstrip__head">
          <span className="filmstrip__title">
            <i />
            <strong>{ready ? '切分队列已完成' : '正在逐帧切分'}</strong>
            <small>{ready ? '所有画面已按时间顺序写入索引' : '每亮起一格，代表一个画面已生成'}</small>
          </span>
          <span className="mono-sm filmstrip__count">{settled} / {analysis.total || '—'} 帧</span>
        </div>
        <span className="filmstrip__progress" aria-hidden="true"><span style={{ transform: `scaleX(${frameProgress})` }} /></span>
        <div className="filmstrip" aria-label={ready ? '已完成的切分帧队列' : '正在生成的切分帧队列'}>
          {frameSlots.map((frame) => {
            const status = frame.src ? 'done' : frame.status === 'missing' ? 'missing' : 'pending'
            return (
              <figure key={frame.index} className="filmstrip__item" data-status={status} data-current={frame.index === activeFrame && !ready ? '' : undefined}>
                {frame.src ? <img src={frame.src} alt="" /> : <span aria-hidden="true" />}
              </figure>
            )
          })}
        </div>
      </div>

      {ready ? (
        <button ref={nextRef} type="button" className="btn btn--dark btn--next" onClick={onNext}>
          进入对话分析 <IconArrowRight />
        </button>
      ) : canEnterEarly ? (
        <button type="button" className="btn btn--dark btn--next btn--early" onClick={onNext}>
          先进入对话 · 其余画面后台继续 <IconArrowRight />
        </button>
      ) : null}
    </>
  )
}
