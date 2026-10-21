import React, { useEffect, useRef, useState } from 'react'
import { IconArrowRight, IconClose, IconFilm, IconImage, IconLink, IconUpload, IconChevron } from '../components/Icons'
import { looksLikeLink } from '../api/client'
import { fmtBytes } from '../lib/format'
import { linkPlatform } from '../lib/platforms'
import { BRAND, WORKSPACE_CONTENT } from '../config/workspace'
import Wordmark from '../components/Wordmark'
import HomepageMascot from '../components/HomepageMascot'
import SamplingOptions, { DEFAULT_SAMPLING, customized, presetLabel, samplingSpec } from '../components/SamplingOptions'

const SOURCES = '支持 B 站、视频号、抖音、小红书、YouTube 等平台的分享链接'
const MAX_PICTURES = 60
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
export default function ImportPanel({ showMascot = false, active = true, onStart, slideRef, externalError = '', onClearError, onShowAccounts }) {
  const [entry, setEntry] = useState('link')
  const [file, setFile] = useState(null)
  const [link, setLink] = useState('')
  const [task, setTask] = useState('')
  const [sampling, setSamplingState] = useState(loadSampling) // preset + overrides, remembered for next time
  const [panel, setPanel] = useState(null) // the one open option under the slide: 'task' | 'sampling'
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
  const linkRef = useRef(null)
  const questionRef = useRef(null)
  const taskButtonRef = useRef(null)
  const samplingButtonRef = useRef(null)

  useEffect(() => {
    if (panel === 'task') questionRef.current?.focus({ preventScroll: true })
  }, [panel])

  const [pics, setPics] = useState([]) // pictures picked or dropped: analysed as a picture set, not a video
  const isImage = (f) => f.type.startsWith('image/') || /\.(jpe?g|png|webp|bmp|gif)$/i.test(f.name)
  const accept = (picked) => {
    const files = [...(picked || [])]
    if (!files.length) return
    if (files.some(isImage) && !files.every(isImage)) {
      setError('视频和图片请分开导入，一次选择一个视频或一组图片')
      return
    }
    if (files.every(isImage)) {
      if (files.length > MAX_PICTURES) {
        setError(`一次最多 ${MAX_PICTURES} 张图片`)
        return
      }
      setError('')
      onClearError?.()
      setLink('')
      setFile(null)
      setPics(files)
      setEntry('upload')
      return
    }
    if (files.length > 1) {
      setError('一次只能导入一个视频，请重新选择')
      return
    }
    const nextFile = files[0]
    if (!nextFile.type.startsWith('video/') && !/\.(mp4|mov|webm|mkv|m4v)$/i.test(nextFile.name)) {
      setError('请选择 MP4、MOV、WEBM 等视频文件，或者几张图片')
      return
    }
    setPics([])
    setError('')
    onClearError?.()
    setLink('')
    setFile(nextFile)
    setEntry('upload')
  }

  const isLink = entry === 'link' && looksLikeLink(link)
  const mode = entry === 'upload' ? (pics.length ? 'images' : file ? 'file' : 'empty') : isLink ? 'link' : 'empty'
  const source = mode === 'link' ? linkPlatform(link) : null
  const hint = mode === 'link'
    ? `${source?.name || '链接'} · 已识别，导入后即可提问`
    : link.trim() ? '没有识别到链接，请粘贴完整的分享链接或分享文案' : SOURCES
  const submit = () => {
    if (mode === 'images') onStart({ images: pics, task })
    else if (mode === 'file') onStart({ file, task, sampling: samplingSpec(sampling) })
    else if (mode === 'link') onStart({ link: link.trim(), task, sampling: samplingSpec(sampling) })
    else if (entry === 'upload') inputRef.current?.click()
    else {
      setError('请先粘贴视频或图文的分享链接')
      linkRef.current?.focus()
    }
  }
  const shownError = error || externalError
  const open = (panel) => setPanel((p) => (p === panel ? null : panel))
  const closeQuestion = () => {
    setPanel(null)
    taskButtonRef.current?.focus({ preventScroll: true })
  }

  return (
    <section className="magazine-hero" onKeyDown={(event) => {
      if (event.key === 'Escape' && panel) {
        const control = event.currentTarget.querySelector(`[aria-controls="import-${panel === 'task' ? 'task' : 'sampling'}"]`)
        setPanel(null)
        control?.focus({ preventScroll: true })
      }
    }}>
      <div className="home-intro" data-exit>
        <p className="magazine-hero__gloss"><span>{BRAND.gloss}</span><span className="magazine-hero__tag">{BRAND.tag}</span></p>
        <div className="magazine-hero__brand" aria-hidden="true"><Wordmark stacked /></div>
        <h1 className="magazine-hero__title">{WORKSPACE_CONTENT.title.map((line) => <span key={line}>{line}</span>)}</h1>
        <p className="magazine-hero__description">{WORKSPACE_CONTENT.description}</p>
      </div>
      {showMascot ? <HomepageMascot placement="hero" active={active} state={shownError ? 'think' : mode !== 'empty' || dragging ? 'focus' : 'idle'} /> : null}
      <div className="import-entry">
        <div
          ref={slideRef}
          className={`import-slide ${dragging ? 'is-dragging' : ''} ${mode !== 'empty' ? 'has-file' : ''}`}
          onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
          onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false) }}
          onDrop={(event) => { event.preventDefault(); setDragging(false); accept(event.dataTransfer.files) }}
        >
          <div className="import-tabs" role="tablist" aria-label="导入方式" data-exit>
            <button type="button" id="import-tab-link" role="tab" aria-selected={entry === 'link'} aria-controls="import-source" tabIndex={entry === 'link' ? 0 : -1}
              onClick={() => { setEntry('link'); setError(''); onClearError?.() }}
              onKeyDown={(e) => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); setEntry('upload'); document.getElementById('import-tab-upload')?.focus() } }}>
              <IconLink size={16} /> 粘贴链接
            </button>
            <button type="button" id="import-tab-upload" role="tab" aria-selected={entry === 'upload'} aria-controls="import-source" tabIndex={entry === 'upload' ? 0 : -1}
              onClick={() => { setEntry('upload'); setError(''); onClearError?.() }}
              onKeyDown={(e) => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); setEntry('link'); document.getElementById('import-tab-link')?.focus() } }}>
              <IconUpload size={16} /> 上传文件
            </button>
            <span className="import-tabs__note">视频 / 图片 / 图文笔记</span>
          </div>
          <input ref={inputRef} type="file" accept="video/*,.mkv,.m4v,image/*" multiple hidden onChange={(event) => { accept(event.target.files); event.target.value = '' }} />
          <div id="import-source" role="tabpanel" aria-labelledby={`import-tab-${entry}`} className={`import-slide__body${entry === 'upload' && mode === 'empty' ? ' import-slide__body--upload' : ''}`}>
            {mode === 'images' ? (
              <>
                <button type="button" className="import-control__file" onClick={() => inputRef.current?.click()} aria-label={`更换图片：${pics.length} 张`}>
                  <IconImage size={22} />
                  <span><strong>{pics.length === 1 ? pics[0].name : `${pics.length} 张图片`}</strong><small>{`${fmtBytes(pics.reduce((n, f) => n + f.size, 0))} · 点击更换`}</small></span>
                </button>
                <button type="button" className="import-control__clear" onClick={() => setPics([])} aria-label="移除图片"><IconClose size={14} /></button>
              </>
            ) : mode === 'file' ? (
              <>
                <button type="button" className="import-control__file" onClick={() => inputRef.current?.click()} aria-label={`更换视频：${file.name}`}>
                  <IconFilm size={22} />
                  <span><strong>{file.name}</strong><small>{`${fmtBytes(file.size)} · 点击更换`}</small></span>
                </button>
                <button type="button" className="import-control__clear" onClick={() => setFile(null)} aria-label="移除文件"><IconClose size={14} /></button>
              </>
            ) : entry === 'upload' ? (
              <button type="button" className="import-dropzone" onClick={() => inputRef.current?.click()}>
                <span className="import-dropzone__icon"><IconUpload size={24} /></span>
                <strong>{dragging ? '松开即可添加文件' : '点击选择，或把文件拖到这里'}</strong>
                <span>一个视频，或最多 60 张图片</span>
                <small>MP4、MOV、WEBM · JPG、PNG、WEBP 等</small>
              </button>
            ) : (
              <div className="import-control__field">
                <span>
                  <span className="import-control__address">
                    <IconLink size={18} />
                    <input
                      type="url" inputMode="url" autoComplete="url" autoCapitalize="off" spellCheck={false}
                      ref={linkRef}
                      className="import-control__link"
                      value={link}
                      placeholder="粘贴视频或图文链接"
                      aria-label="内容链接"
                      aria-describedby="import-link-hint" aria-invalid={Boolean(link.trim() && !isLink)}
                      onChange={(event) => { setLink(event.target.value); setError(''); onClearError?.() }}
                      onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && mode === 'link') { event.preventDefault(); submit() } }}
                    />
                  </span>
                  <small id="import-link-hint" className={link.trim() && mode !== 'link' ? 'is-warn' : ''}>{hint}</small>
                </span>
              </div>
            )}
          </div>
          <div className="import-slide__bar" data-exit>
            <button ref={taskButtonRef} type="button" className="import-chip" data-on={panel === 'task' || task ? true : undefined}
              onClick={() => open('task')} aria-expanded={panel === 'task'} aria-controls="import-task">
              <span aria-hidden="true">{task ? '✓' : '+'}</span> {task ? '已添加问题' : '添加问题'}<span className="import-chip__optional">（可选）</span>
            </button>
            <span className="import-slide__gap" />
            {mode !== 'images' ? (
              <button ref={samplingButtonRef} type="button" className="import-chip import-entry__sampling" data-on={panel === 'sampling' || undefined}
                onClick={() => open('sampling')} aria-expanded={panel === 'sampling'} aria-controls="import-sampling">
                解析设置 <span className="import-chip__value">{presetLabel(sampling)}{customized(sampling) ? ' · 自定义' : ''}</span><IconChevron size={12} />
              </button>
            ) : <span className="import-slide__drop">图片无需额外设置</span>}
          </div>
          <div className="import-disclosure" data-open={panel === 'task' || undefined}
            aria-hidden={panel !== 'task'} inert={panel === 'task' ? undefined : ''}>
            <div className="import-disclosure__clip">
              <div id="import-task" className="import-options import-question" data-exit>
                <label htmlFor="import-question">你想了解什么？</label>
                <textarea ref={questionRef} rows={3} id="import-question" className="field__input import-options__task" value={task} placeholder="例如：总结内容，或核查其中的说法" aria-describedby="import-question-hint"
                  onChange={(event) => setTask(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); closeQuestion() } }} />
                <div className="import-question__footer">
                  <small id="import-question-hint">导入后会填入对话框，可修改后发送。</small>
                  <button type="button" className="import-settings__done" onClick={closeQuestion}>完成</button>
                </div>
                <div className="import-options__presets">
                  {WORKSPACE_CONTENT.capabilities.map((item) => <button type="button" key={item.mark} onClick={() => setTask(item.task)}>{item.title}</button>)}
                  {task ? <button type="button" onClick={() => setTask('')}>清空问题</button> : null}
                </div>
              </div>
            </div>
          </div>
          {mode !== 'images' ? (
            <div className="import-disclosure" data-open={panel === 'sampling' || undefined}
              aria-hidden={panel !== 'sampling'} inert={panel === 'sampling' ? undefined : ''}>
              <div className="import-disclosure__clip">
                <SamplingOptions value={sampling} onChange={setSampling} onClose={() => { setPanel(null); samplingButtonRef.current?.focus({ preventScroll: true }) }} />
              </div>
            </div>
          ) : null}
          <div className="import-actions" data-exit>
            <span>{mode === 'images' ? `已选择 ${pics.length} 张图片` : mode === 'file' ? '视频已就绪' : mode === 'link' ? '链接已就绪，支持回车导入' : '导入后，围绕内容自由提问'}</span>
            <button type="button" className="import-control__submit" data-idle={mode === 'empty' || undefined} onClick={submit}>
              {mode === 'images' ? '读取图片' : mode === 'link' ? '解析链接' : entry === 'upload' && mode === 'empty' ? '选择文件' : '开始解析'} <IconArrowRight size={16} />
            </button>
          </div>
        </div>
        {shownError ? (
          <p className="field-error" role="alert">
            {shownError}
            {/「账号」/.test(shownError) && onShowAccounts ? (
              <button type="button" className="field-error__action" onClick={() => onShowAccounts(/元宝|视频号/.test(shownError) ? 'yuanbao' : /小红书/.test(shownError) ? 'xiaohongshu' : 'bilibili')}>去扫码登录</button>
            ) : null}
          </p>
        ) : null}
        <div className="import-entry__footer" data-exit>
          <button type="button" className="import-entry__sample" onClick={() => onStart({ file: null, task })}>先用示例视频体验 <i aria-hidden="true" /><IconArrowRight size={14} /></button>
        </div>
      </div>
    </section>
  )
}
