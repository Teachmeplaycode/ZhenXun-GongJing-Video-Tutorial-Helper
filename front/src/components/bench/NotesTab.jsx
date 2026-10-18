import React, { useCallback, useEffect, useRef, useState } from 'react'
import { generateNotes, getNotes, notesExportUrl } from '../../api/client'
import ExportDialog from '../ExportDialog'
import { IconBook } from '../Icons'

const POLL = 2000 // ms between status checks while a note is being written

// Notes in the workbench: the agent writes a structured note of the video (sections by chapter with
// key points, formulas and the frames that show them, plus a mind map), which opens in the editor
// page to rearrange. The plain export of the Q&A turns lives here too.
export default function NotesTab({ video, messages = [] }) {
  const jobId = video?.jobId
  const [state, setState] = useState(null) // getNotes() answer
  const [error, setError] = useState('')
  const [exportOpen, setExportOpen] = useState(false)
  const timer = useRef(0)

  const load = useCallback(async () => {
    clearTimeout(timer.current)
    try {
      const r = await getNotes(jobId)
      setState(r)
      setError('')
      if (r.status === 'running') timer.current = setTimeout(load, POLL)
    } catch (err) {
      setError(err.message)
    }
  }, [jobId])
  useEffect(() => {
    if (jobId) load()
    return () => clearTimeout(timer.current)
  }, [jobId, load])

  const start = async () => {
    setError('')
    try {
      setState(await generateNotes(jobId))
      timer.current = setTimeout(load, POLL)
    } catch (err) {
      setError(err.message)
    }
  }
  const openEditor = () => window.open(`${window.location.pathname}#/notes/${jobId}`, '_blank', 'noopener')

  if (!jobId) return <p className="bench__note muted">导入视频后可以生成笔记。</p>
  const note = state?.note
  const running = state?.status === 'running'
  const progress = state?.progress || {}
  return (
    <div className="notes-tab">
      {running ? (
        <div className="bench__idle">
          <h3>正在整理笔记…</h3>
          <div className="notes-tab__bar" role="progressbar" aria-valuemin={0} aria-valuemax={progress.total || 1} aria-valuenow={progress.done || 0}>
            <span style={{ width: `${progress.total ? Math.round((progress.done / progress.total) * 100) : 8}%` }} />
          </div>
          <p className="caption muted">{state.message || '按章节整理要点、公式和配图'}{progress.total ? ` · ${progress.done}/${progress.total}` : ''}</p>
        </div>
      ) : note ? (
        <div className="notes-tab__done">
          <h3 className="notes-tab__title">{note.title}</h3>
          {note.summary ? <p className="body-sm notes-tab__summary">{note.summary}</p> : null}
          <p className="caption muted">{note.sections.length} 节 · {note.sections.reduce((n, s) => n + (s.figures?.length || 0), 0)} 张配图 · 思维导图 {note.mindmap?.children?.length || 0} 个分支</p>
          <ol className="notes-tab__sections">
            {note.sections.slice(0, 8).map((s) => <li key={s.id}>{s.title}</li>)}
            {note.sections.length > 8 ? <li className="muted">…还有 {note.sections.length - 8} 节</li> : null}
          </ol>
          <div className="notes-tab__actions">
            <button type="button" className="btn btn--dark" onClick={openEditor}>打开笔记编辑器</button>
            <a className="btn btn--ghost" href={notesExportUrl(jobId)} download>导出 Markdown（含图）</a>
            <button type="button" className="link-btn" onClick={start}>重新生成</button>
          </div>
        </div>
      ) : (
        <div className="bench__idle">
          <IconBook size={28} />
          <h3>生成笔记</h3>
          <p className="body-sm muted">agent 按章节整理这段视频：每节的要点、公式和例题，配上讲到它们时的画面，最后画一张思维导图。生成后可以在编辑器里拖动、缩放、改写和调整图片位置。</p>
          <p className="caption muted">适合网课、讲座、教程。长视频需要一两分钟。</p>
          {state?.status === 'failed' ? <p className="bench__error">{state.message || '上次生成失败'}</p> : null}
          <button type="button" className="btn btn--dark" onClick={start}>生成笔记</button>
        </div>
      )}
      {error ? <p className="bench__error">{error}</p> : null}

      <div className="notes-tab__qa">
        <h4 className="eyebrow">问答记录</h4>
        <p className="caption muted">把这次对话的问答、时间点和截图导出为 Markdown 或 PDF。</p>
        <button type="button" className="btn btn--ghost" disabled={!messages.length} onClick={() => setExportOpen(true)}>
          {messages.length ? '导出问答记录' : '还没有问答'}
        </button>
      </div>
      {exportOpen ? <ExportDialog sessionId={jobId} messages={messages} onClose={() => setExportOpen(false)} /> : null}
    </div>
  )
}
