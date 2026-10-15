import React, { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { IconAlert, IconArrowRight, IconCheck, IconRefresh } from '../components/Icons'
import { fmtBytes, fmtTime } from '../lib/format'
import { EASE } from '../lib/motion'
import CountUp from '../components/react-bits/CountUp'

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
  const steps = [
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
  ]
  const transcriptFailed = analysis.transcript?.status === 'failed'
  const retryLabel = [analysis.missing ? `缺失的 ${analysis.missing} 帧` : '', transcriptFailed ? '语音转写' : ''].filter(Boolean).join('和')

  return (
    <>
      <div className="hud">
        <div className="hud__head">
          <span className="eyebrow">{ready ? '解析完成' : '正在解析'}</span>
          <span className="mono-sm hud__file">{meta.name}</span>
        </div>
        <ol className="hud__steps">
          {steps.map((s) => (
            <li key={s.key} className="hud__step" data-status={s.state}>
              <StepState state={s.state} />
              <span className="hud__label">{s.label}</span>
              <span className="hud__value mono-sm">
                {s.key === 'frames' && analysis.total ? <><CountUp to={analysis.frames} duration={0.6} /> / {analysis.total}</> : s.value}
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
        {ready && onRetry && retryLabel ? (
          <button type="button" className="link-btn hud__retry" onClick={onRetry} disabled={retrying}>
            <IconRefresh size={13} />{retrying ? '补抓中…' : `重试${retryLabel}`}
          </button>
        ) : null}
      </div>

      <div className="filmstrip" aria-label="已抓取关键帧">
        {frames.filter((f) => f.src).map((f) => (
          <figure key={f.index} className="filmstrip__item">
            <img src={f.src} alt="" />
          </figure>
        ))}
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
