import React, { useRef, useState } from 'react'
import { IconArrowRight, IconClose, IconFilm, IconLink, IconUpload } from '../components/Icons'
import { looksLikeLink } from '../api/client'
import { fmtBytes } from '../lib/format'
import { BRAND, WORKSPACE_CONTENT } from '../config/workspace'
import Wordmark from '../components/Wordmark'
import { SessionItem } from '../components/SessionList'
import SamplingOptions, { DEFAULT_SAMPLING, customized, presetLabel, samplingSpec } from '../components/SamplingOptions'

const RECENT_COUNT = 3
const SAMPLING_KEY = 'import.sampling'
const loadSampling = () => {
  try {
    return { ...DEFAULT_SAMPLING, ...JSON.parse(localStorage.getItem(SAMPLING_KEY) || '{}') }
  } catch {
    return DEFAULT_SAMPLING
  }
}

// slideRef: the glass slide; the sculpture refracts through it and the upload screen grows out of it.
// externalError: a failure reported by App after the import screen was left (e.g. link resolution).
// sessions: saved sessions, newest first; the last few are listed under the slide.
export default function ImportPanel({ onStart, slideRef, externalError = '', onClearError, sessions = [], onOpenSession, onShowHistory, onShowAccounts }) {
  const [file, setFile] = useState(null)
  const [link, setLink] = useState('')
  const [task, setTask] = useState('')
  const [showTask, setShowTask] = useState(false)
  const [sampling, setSamplingState] = useState(loadSampling) // preset + overrides, remembered for next time
  const [showSampling, setShowSampling] = useState(false)
  const setSampling = (next) => {
    setSamplingState(next)
    try {
      localStorage.setItem(SAMPLING_KEY, JSON.stringify(next))
    } catch {
      // private mode: the choice holds for this import
    }
  }
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const accept = (nextFile) => {
    if (!nextFile) return
    if (!nextFile.type.startsWith('video/') && !/\.(mp4|mov|webm|mkv|m4v)$/i.test(nextFile.name)) {
      setError('请选择 MP4、MOV、WEBM 等视频文件')
      return
    }
    setError('')
    onClearError?.()
    setLink('')
    setFile(nextFile)
  }

  const isLink = !file && looksLikeLink(link)
  const mode = file ? 'file' : isLink ? 'link' : 'empty'
  const hint = mode === 'link'
    ? '已识别链接 · 直接读取画面，不下载视频'
    : link.trim() ? '没有识别到链接，请粘贴完整的分享链接' : '支持 B 站、视频号分享链接，或本地视频文件'
  const submit = () => {
    if (mode === 'file') onStart({ file, task, sampling: samplingSpec(sampling) })
    else if (mode === 'link') onStart({ link: link.trim(), task, sampling: samplingSpec(sampling) })
    else inputRef.current?.click()
  }
  const shownError = error || externalError

  return (
    <section className="magazine-hero">
      <p className="magazine-hero__gloss" data-exit>
        <span>{BRAND.gloss}</span><span className="magazine-hero__tag">{BRAND.tag}</span>
      </p>
      <h1 className="magazine-hero__brand" data-exit><Wordmark /></h1>
      <p className="magazine-hero__title" data-exit>{WORKSPACE_CONTENT.title.map((line) => <span key={line}>{line}</span>)}</p>
      <p className="magazine-hero__description" data-exit>{WORKSPACE_CONTENT.description}</p>
      <div className="import-entry">
        <div className="import-slide__label" data-exit>
          <span>01 / IMPORT</span>
          <span className={mode !== 'empty' ? 'is-ready' : ''}>{mode === 'file' ? 'READY' : mode === 'link' ? 'LINK' : 'STANDBY'}</span>
        </div>
        <div
          ref={slideRef}
          className={`import-slide ${dragging ? 'is-dragging' : ''} ${mode !== 'empty' ? 'has-file' : ''}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
          onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false) }}
          onDrop={(event) => { event.preventDefault(); setDragging(false); accept(event.dataTransfer.files?.[0]) }}
        >
          <i className="import-slide__tick import-slide__tick--tl" aria-hidden="true" />
          <i className="import-slide__tick import-slide__tick--tr" aria-hidden="true" />
          <i className="import-slide__tick import-slide__tick--bl" aria-hidden="true" />
          <i className="import-slide__tick import-slide__tick--br" aria-hidden="true" />
          <div className="import-slide__body">
            <input ref={inputRef} type="file" accept="video/*,.mkv,.m4v" hidden onChange={(event) => accept(event.target.files?.[0])} />
            {file ? (
              <>
                <button type="button" className="import-control__file" onClick={() => inputRef.current?.click()} aria-label={`更换视频：${file.name}`}>
                  <IconFilm size={22} />
                  <span><strong>{file.name}</strong><small>{`${fmtBytes(file.size)} · 点击更换`}</small></span>
                </button>
                <button type="button" className="import-control__clear" onClick={() => setFile(null)} aria-label="移除文件，改用链接"><IconClose size={14} /></button>
              </>
            ) : (
              <div className="import-control__field">
                <button type="button" className="import-control__pick" onClick={() => inputRef.current?.click()} aria-label="选择本地视频文件">
                  {mode === 'link' ? <IconLink size={22} /> : <IconUpload size={22} />}
                </button>
                <span>
                  <input
                    className="import-control__link"
                    value={link}
                    placeholder="粘贴视频链接，或选择 / 拖入文件"
                    aria-label="视频链接"
                    onChange={(event) => { setLink(event.target.value); setError(''); onClearError?.() }}
                    onKeyDown={(event) => { if (event.key === 'Enter' && mode === 'link') submit() }}
                  />
                  <small className={link.trim() && mode !== 'link' ? 'is-warn' : ''}>{hint}</small>
                </span>
              </div>
            )}
            <button type="button" className="import-control__submit" onClick={submit}>
              {mode === 'file' ? '开始解析' : mode === 'link' ? '解析链接' : '选择文件'} <IconArrowRight size={16} />
            </button>
          </div>
        </div>
        {shownError ? (
          <p className="field-error" role="alert">
            {shownError}
            {/「账号」/.test(shownError) && onShowAccounts ? (
              <button type="button" className="field-error__action" onClick={() => onShowAccounts(/元宝|视频号/.test(shownError) ? 'yuanbao' : 'bilibili')}>去扫码登录</button>
            ) : null}
          </p>
        ) : null}
        <div className="import-entry__footer" data-exit>
          <span>B 站 · 视频号 · MP4 · MOV · WEBM</span>
          <button type="button" onClick={() => setShowTask((value) => !value)} aria-expanded={showTask} aria-controls="import-task">{task ? '编辑分析任务' : '添加分析任务'}</button>
          <button type="button" className="import-entry__sampling" onClick={() => setShowSampling((value) => !value)} aria-expanded={showSampling} aria-controls="import-sampling">
            采样：{presetLabel(sampling)}{customized(sampling) ? '（自定义）' : ''}
          </button>
          <button type="button" className="import-entry__sample" onClick={() => onStart({ file: null, task })}>使用示例素材 <i aria-hidden="true" /><IconArrowRight size={14} /></button>
        </div>
        {showTask ? (
          <div id="import-task" className="import-options" data-exit>
            <label className="field">
              <span className="field__label">分析任务（可选）</span>
              <textarea className="field__input" rows={2} value={task} placeholder="你想从视频中了解什么？" onChange={(event) => setTask(event.target.value)} autoFocus />
            </label>
            <div className="import-options__presets">
              {WORKSPACE_CONTENT.capabilities.map((item) => <button type="button" key={item.mark} onClick={() => setTask(item.task)}>{item.title}</button>)}
            </div>
          </div>
        ) : null}
        {showSampling ? <SamplingOptions value={sampling} onChange={setSampling} /> : null}
        {sessions.length ? (
          <div className="recent" data-exit>
            <div className="recent__head">
              <span>RECENT</span>
              {sessions.length > RECENT_COUNT ? <button type="button" onClick={onShowHistory}>全部 {sessions.length} 条</button> : null}
            </div>
            <ul className="recent__list">
              {sessions.slice(0, RECENT_COUNT).map((s) => <SessionItem key={s.id} session={s} compact onOpen={onOpenSession} />)}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  )
}
