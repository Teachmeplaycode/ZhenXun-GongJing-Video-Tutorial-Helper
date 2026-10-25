import React, { useEffect, useMemo, useRef, useState } from 'react'
import { IconArrowLeft, IconArrowRight, IconAlert, IconCheck, IconRefresh } from '../components/Icons'
import { fmtBytes, fmtClock } from '../lib/format'
import { linkPlatform, platformName } from '../lib/platforms'
import { speechStep, screenStep } from './AnalyzeHud'
import '../styles/processing.css'

const PHASES = ['获取素材', '提取画面', '准备完成']
const activeTask = (task) => task && ['pending', 'running'].includes(task.status)

function sourceLabel(meta) {
  if (meta.platform) return meta.platform === 'local' ? '本地文件' : platformName(meta.platform)
  if (meta.sample) return '示例素材'
  if (!meta.link) return '本地文件'
  return linkPlatform(meta.name)?.name || '视频链接'
}

function Preview({ frame }) {
  const [failed, setFailed] = useState(false)
  return failed ? (
    <div className="processing__empty"><strong>画面暂时无法显示</strong><span>可以查看其他帧或继续分析</span></div>
  ) : <img className="processing__preview-image" src={frame.src} alt={`视频画面 ${fmtClock(frame.time)}`} onError={() => setFailed(true)} />
}

export default function MobileProcessing({ stage, meta, analysis, frames, uploadProgress = 0, notice, onBack, onNext, canEnterEarly, onRetry, retrying }) {
  const acquiring = stage === 'uploading'
  // Shot-fill slots can arrive after the first pass; their announced slots are the
  // current denominator even while the original analysis.total is still unchanged.
  const total = Math.max(analysis.total || 0, frames.length)
  const settled = analysis.frames + (analysis.missing || 0)
  const extracted = total > 0 && settled >= total
  const ready = stage === 'ready' && (!total || extracted)
  const phase = acquiring ? 0 : ready || extracted ? 2 : 1
  const source = sourceLabel(meta)
  const isPictures = meta.kind === 'images'
  const speechRunning = activeTask(analysis.transcript)
  const textRunning = activeTask(analysis.screentext)
  const auxiliaryRunning = speechRunning || textRunning
  const failedTasks = [analysis.transcript?.status === 'failed' && '语音转写', analysis.screentext?.status === 'failed' && '文字识别'].filter(Boolean)
  const count = analysis.frames || 0
  const upload = Math.min(1, Math.max(0, Number(uploadProgress) || 0))
  const ratio = acquiring ? upload : total ? Math.min(1, count / total) : 0
  const indeterminate = acquiring ? Boolean(meta.link) : !total
  const title = acquiring
    ? meta.link ? '正在解析链接' : isPictures ? '正在上传图片' : '正在上传视频'
    : retrying ? '正在补充素材'
      : ready ? '画面已就绪'
        : extracted ? analysis.index ? '正在整理素材' : '正在整理索引'
          : '正在提取画面'
  const message = acquiring
    ? meta.link ? '正在获取视频信息与播放地址' : upload === 1 ? '上传完成，正在读取素材信息' : '上传完成后将自动提取画面'
    : ready ? auxiliaryRunning ? '可以开始分析，文字处理仍在继续' : '画面与索引已准备好，可以开始分析'
      : extracted ? '画面提取已结束，正在完成后续处理' : '画面会陆续出现，请保持页面开启'

  const available = useMemo(() => frames.filter(frame => frame.src), [frames])
  const seen = useRef(new Set())
  const [latestIndex, setLatestIndex] = useState(null)
  const [selectedIndex, setSelectedIndex] = useState(null)
  const rail = useRef(null)
  const followRail = useRef(true)
  useEffect(() => {
    const arrived = available.filter(frame => !seen.current.has(frame.index))
    seen.current = new Set(available.map(frame => frame.index))
    if (arrived.length) setLatestIndex(arrived[arrived.length - 1].index)
  }, [available])
  const latest = available.find(frame => frame.index === latestIndex) || available[available.length - 1]
  const selected = available.find(frame => frame.index === selectedIndex) || latest
  useEffect(() => {
    if (!followRail.current || !rail.current) return
    const current = rail.current.querySelector('[data-latest="true"]')
    if (current) rail.current.scrollLeft = Math.max(0, current.offsetLeft + current.offsetWidth - rail.current.clientWidth)
  }, [latest?.index])
  const resumeFollowing = () => {
    setSelectedIndex(null)
    followRail.current = true
    const el = rail.current
    const current = el?.querySelector('[data-latest="true"]')
    if (current) el.scrollLeft = Math.max(0, current.offsetLeft + current.offsetWidth - el.clientWidth)
  }

  const details = [
    { label: '素材信息', value: acquiring ? '读取中' : '已读取', done: !acquiring },
    ...(!acquiring ? [{ label: '时间轴索引', value: analysis.index ? '已建立' : extracted ? '建立中' : '等待画面', done: analysis.index }] : []),
    ...(analysis.transcript ? [{ label: '语音转写', ...speechStep(analysis.transcript) }] : []),
    ...(analysis.screentext ? [{ label: '画面文字', ...screenStep(analysis.screentext) }] : []),
  ]
  const warnings = [analysis.missing > 0 && `${analysis.missing} 帧未能获取`, failedTasks.length > 0 && `${failedTasks.join('、')}失败`].filter(Boolean)
  const canContinue = !acquiring && (stage === 'ready' || canEnterEarly)

  return (
    <section className="processing" role="main" aria-label="素材处理" data-phase={phase}>
      <header className="processing__header">
        <button type="button" className="processing__back" onClick={onBack} aria-label="返回导入视频"><IconArrowLeft size={20} /></button>
        <span>素材处理</span>
        <span className="processing__header-state">{warnings.length ? '有未完成项' : ready ? '可分析' : '处理中'}</span>
      </header>

      <div className="processing__scroll">
        <ol className="processing__phases" aria-label="处理阶段">
          {PHASES.map((label, index) => (
            <li key={label} data-active={index === phase || undefined} data-done={index < phase || undefined} aria-current={index === phase ? 'step' : undefined}>
              <span className="processing__phase-number">0{index + 1}</span><span>{label}</span>
            </li>
          ))}
        </ol>

        <div className="processing__status" key={title} role="status">
          <h1>{title}<span className="processing__title-dot" aria-hidden="true">.</span></h1>
          <p>{message}</p>
        </div>

        <div className="processing__metric">
          {!acquiring ? <><span className="processing__metric-label">已生成画面</span><div className="processing__count"><strong>{count}</strong><span>{total ? `/ ${total} · 帧` : '帧 · 总量待确认'}</span></div></>
            : !meta.link ? <><span className="processing__metric-label">上传进度</span><div className="processing__count"><strong>{Math.round(upload * 100)}</strong><span>%</span></div></>
              : <span className="processing__metric-label">连接素材来源</span>}
          <div className="processing__progress" data-indeterminate={indeterminate || undefined} role="progressbar"
            aria-label={acquiring ? meta.link ? '解析链接' : '上传进度' : '画面提取进度'}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={indeterminate ? undefined : Math.round(ratio * 100)}>
            <span style={indeterminate ? undefined : { transform: `scaleX(${ratio})` }} />
          </div>
          {acquiring && !meta.link && meta.size > 0 ? <span className="processing__bytes">{fmtBytes(meta.size * upload)} / {fmtBytes(meta.size)}</span> : null}
          {warnings.length > 0 ? <p className="processing__metric-warning"><IconAlert size={14} />{warnings.join(' · ')}</p> : null}
        </div>

        <div className="processing__source">
          <span className="processing__source-label">{source}{Number.isFinite(meta.duration) && meta.duration > 0 ? ` · ${fmtClock(meta.duration)}` : ''}</span>
          <p title={meta.name}>{meta.name}</p>
        </div>

        <figure className="processing__preview">
          {selected ? <Preview key={selected.src} frame={selected} /> : (
            <div className="processing__empty"><span>{source}</span><strong>等待首帧</strong><span>获取画面后将在这里显示</span></div>
          )}
          {selected ? <figcaption><span>{selectedIndex === null ? '最新画面' : '画面预览'}</span><time>{fmtClock(selected.time)}</time></figcaption> : null}
        </figure>

        {available.length > 0 ? (
          <>
            <div className="processing__rail" ref={rail} role="group" aria-label="已生成画面"
              onPointerDown={() => { followRail.current = false }} onWheel={() => { followRail.current = false }} onKeyDown={() => { followRail.current = false }}>
              {available.map(frame => (
                <button key={frame.index} type="button" className="processing__frame" data-latest={frame.index === latest?.index} aria-pressed={frame.index === selected?.index}
                  aria-label={`查看第 ${frame.index + 1} 帧，时间 ${fmtClock(frame.time)}`} onClick={() => setSelectedIndex(frame.index)}>
                  <img src={frame.src} alt="" loading="lazy" /><time>{fmtClock(frame.time)}</time>
                </button>
              ))}
            </div>
            {selectedIndex !== null ? <button className="processing__follow" type="button" onClick={resumeFollowing}>跟随最新画面 <IconArrowRight size={14} /></button> : null}
          </>
        ) : null}

        {warnings.length > 0 || notice ? (
          <aside className="processing__notice" role="status">
            <IconAlert size={16} /><div>{warnings.length > 0 ? <strong>{warnings.join(' · ')}</strong> : null}
              {notice ? <p>{notice}</p> : warnings.length > 0 ? <p>{canContinue ? '已有画面仍可用于分析。' : '其余内容仍在处理中。'}</p> : null}
              {ready && onRetry && warnings.length > 0 ? <button type="button" onClick={onRetry} disabled={retrying}><IconRefresh size={14} />{retrying ? '正在重试…' : '重试未完成内容'}</button> : null}
            </div>
          </aside>
        ) : null}

        <details className="processing__details">
          <summary>处理详情 <span aria-hidden="true">+</span></summary>
          <dl>{details.map(item => <div key={item.label}><dt>{item.label}</dt><dd data-warning={item.state === 'warn' || undefined}>{item.done || item.state === 'done' ? <IconCheck size={14} /> : null}{item.value || '等待处理'}</dd></div>)}</dl>
          {analysis.status && !ready ? <p>{analysis.status}</p> : null}
          {failedTasks.length > 0 ? <p>{[analysis.transcript?.status === 'failed' && analysis.transcript.message, analysis.screentext?.status === 'failed' && analysis.screentext.message].filter(Boolean).join('；')}</p> : null}
        </details>
      </div>

      <footer className="processing__footer">
        {canContinue ? <button key={ready ? 'ready' : 'early'} className="processing__continue" type="button" onClick={onNext}>{ready ? '开始分析' : '先开始分析'}<IconArrowRight size={20} /></button>
          : <p><span aria-hidden="true" />{acquiring ? '获取素材后自动开始提取' : '画面准备好后即可开始分析'}</p>}
        {canContinue && (!ready || auxiliaryRunning || retrying) ? <small>其余内容会继续处理，请保持页面开启</small> : null}
      </footer>
    </section>
  )
}
