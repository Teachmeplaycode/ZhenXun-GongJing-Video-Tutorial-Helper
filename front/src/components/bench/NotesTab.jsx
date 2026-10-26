import React, { useCallback, useEffect, useRef, useState } from 'react'
import { applyNoteRevision, discardNoteDraft, generateNotes, getNotes, getSteps, notesExportUrl, notesImageUrl, restoreNoteRevision } from '../../api/client'
import PreviewDialog from '../PreviewDialog'
import ExportDialog from '../ExportDialog'
import { IconBook } from '../Icons'
import MathText from '../MathText'
import '../../styles/conversation-notes.css'

const POLL = 2000
const generating = (s) => s?.generation?.status === 'running' || s?.status === 'running'
const versionDate = (v) => v ? new Date(v * 1000).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

// stepsToNotes: bumped by 导入笔记 on the steps tab; each bump starts a note (or a revision) with the step cards.
export default function NotesTab({ video, messages = [], conversation, stepsToNotes = 0 }) {
  const jobId = video?.jobId
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [exportOpen, setExportOpen] = useState(false)
  const [preview, setPreview] = useState(null)
  const [imageSrc, setImageSrc] = useState(null)
  const [stepCount, setStepCount] = useState(0) // built step cards, offered as material
  const [withSteps, setWithSteps] = useState(true)
  const importAsked = useRef(0)
  const timer = useRef(0)
  const mounted = useRef(false)
  const activeJob = useRef(jobId)
  const requestEpoch = useRef(0)
  const readController = useRef(null)
  const mutating = useRef(false)
  activeJob.current = jobId
  const load = useCallback(async () => {
    if (activeJob.current !== jobId) return
    clearTimeout(timer.current)
    readController.current?.abort()
    const controller = new AbortController()
    readController.current = controller
    const epoch = ++requestEpoch.current
    try {
      const result = await getNotes(jobId, { signal: controller.signal })
      if (!mounted.current || activeJob.current !== jobId || epoch !== requestEpoch.current) return
      setState(result)
      if (generating(result)) timer.current = setTimeout(load, POLL)
    } catch (err) {
      if (err.name !== 'AbortError' && mounted.current && activeJob.current === jobId && epoch === requestEpoch.current) setError(err.message)
    }
  }, [jobId])
  useEffect(() => {
    mounted.current = true
    mutating.current = false
    setState(null)
    setPreview(null)
    setImageSrc(null)
    setExportOpen(false)
    setError('')
    setInstruction('')
    setBusy(false)
    if (jobId) load()
    return () => { mounted.current = false; requestEpoch.current += 1; readController.current?.abort(); clearTimeout(timer.current) }
  }, [jobId, load])
  const mutate = async (request) => {
    if (mutating.current || activeJob.current !== jobId) return
    mutating.current = true
    clearTimeout(timer.current)
    readController.current?.abort()
    const epoch = ++requestEpoch.current
    setBusy(true)
    setError('')
    try {
      const result = await request()
      if (!mounted.current || activeJob.current !== jobId || epoch !== requestEpoch.current) return
      setState(result)
      if (generating(result)) timer.current = setTimeout(load, POLL)
      return result
    } catch (err) {
      if (mounted.current && activeJob.current === jobId && epoch === requestEpoch.current) { setError(err.message); await load() }
    } finally {
      if (mounted.current && activeJob.current === jobId) { mutating.current = false; setBusy(false) }
    }
  }
  const start = (source, useSteps = withSteps && stepCount > 0) => mutate(() => generateNotes(jobId, {
    source,
    ...(useSteps ? { use_steps: true } : {}),
    ...(source === 'conversation' ? { message_ids: conversation.messageIds, instruction: instruction.trim() } : {}),
    ...(state?.revision ? { base_revision: state.revision } : {}),
  }))
  const apply = async () => {
    const result = await mutate(() => applyNoteRevision(jobId, state.draft.id, state.draft.base_revision))
    if (result) setPreview(null)
  }
  const discard = async () => {
    const result = await mutate(() => discardNoteDraft(jobId))
    if (result) setPreview(null)
  }
  useEffect(() => {
    setStepCount(0)
    if (!jobId) return undefined
    const ctrl = new AbortController()
    getSteps(jobId, { signal: ctrl.signal })
      .then((r) => setStepCount(r?.status === 'done' ? (r.steps || []).length : 0)).catch(() => {})
    return () => ctrl.abort()
  }, [jobId, stepsToNotes])
  useEffect(() => { if (stepsToNotes) importAsked.current = stepsToNotes }, [stepsToNotes])
  useEffect(() => {
    if (!importAsked.current || !state || !stepCount || busy) return
    importAsked.current = 0
    if (generating(state) || state.draft) { setError('先等当前生成完成，或处理待确认的修订，再导入步骤。'); return }
    setWithSteps(true)
    start('video', true)
  }, [state, stepCount, busy]) // eslint-disable-line react-hooks/exhaustive-deps
  const openEditor = () => window.open(`${window.location.pathname}#/notes/${jobId}`, '_blank', 'noopener')
  if (!jobId) return <p className="bench__note muted">导入视频后可以生成笔记。</p>
  const note = state?.note
  const draft = state?.draft
  const generation = state?.generation || state
  const running = generating(state)
  const progress = generation?.progress || {}
  const turns = conversation?.turns.filter((t) => t.kind === 'qa') || []
  const chosenCount = conversation?.chosen.length || 0
  const choosing = conversation?.selecting || false
  const canGenerate = Boolean(state) && !busy && !running && !draft
  const previewUrl = `${notesExportUrl(jobId)}?preview=1${preview === 'draft' ? '&draft=1' : ''}&revision=${encodeURIComponent(preview === 'draft' ? draft?.id || '' : state?.revision || '')}`
  const failure = generation?.status === 'failed' ? generation.message || '笔记生成失败，可重试。' : ''
  return <div className="notes-tab">
    {note ? <div className="notes-tab__done">
      <span className="notes-tab__label">当前笔记</span>
      <h3 className="notes-tab__title">{note.title}</h3>
      {note.summary ? <p className="body-sm notes-tab__summary"><MathText text={note.summary} /></p> : null}
      <p className="caption muted">{note.sections.length} 节 · {note.sections.reduce((n, s) => n + (s.figures?.length || 0), 0)} 张配图 · 思维导图 {note.mindmap?.children?.length || 0} 个分支</p>
      <ol className="notes-tab__sections">{note.sections.slice(0, 8).map((s) => <li key={s.id}>{s.title}</li>)}{note.sections.length > 8 ? <li className="muted">…还有 {note.sections.length - 8} 节</li> : null}</ol>
      <div className="notes-tab__actions">
        <button type="button" className="btn btn--dark" onClick={openEditor}>打开笔记编辑器</button>
        <button type="button" className="btn btn--ghost" onClick={() => setPreview('current')}>预览导出</button>
        <button type="button" className="btn btn--ghost" onClick={() => setImageSrc(notesImageUrl(jobId))}>存为长图</button>
        <a className="btn btn--ghost" href={notesExportUrl(jobId)} download>导出 Markdown（含图）</a>
      </div>
    </div> : !running ? <div className="bench__idle">
      <IconBook size={28} /><h3>生成笔记</h3>
      <p className="body-sm muted">整理整段视频，或选取聊过的问题，生成带时间点和画面的主题笔记。生成后可以编辑正文、批注和排版。</p>
    </div> : null}
    {running ? <div className="notes-tab__generation" role="status" aria-live="polite">
      <strong>{note ? '正在准备修订稿…' : '正在整理笔记…'}</strong>
      <div className="notes-tab__bar" role="progressbar" aria-label="笔记生成进度" {...(progress.total ? { 'aria-valuemin': 0, 'aria-valuemax': progress.total, 'aria-valuenow': progress.done || 0 } : {})}>
        <span style={progress.total ? { width: `${Math.min(100, ((progress.done || 0) / progress.total) * 100)}%` } : undefined} />
      </div>
      <p className="caption muted">{generation.message || '正在整理已有画面和文字…'}{progress.total ? ` · ${progress.done || 0}/${progress.total}` : ''}</p>
      {note ? <p className="caption muted">当前笔记仍可查看；修订完成后由你确认应用。</p> : null}
    </div> : null}
    {failure ? <p className="bench__error" role="alert">{failure}{note ? ' 当前笔记已保留。' : ''}</p> : null}
    {error ? <p className="bench__error" role="alert">{error}</p> : null}
    {draft ? <section className="notes-revision" aria-label="待确认修订">
      <span className="notes-tab__label">修订待确认</span><h4>{draft.note.title}</h4>
      <ul className="notes-revision__changes">{(draft.changes || []).map((c, i) => <li key={i}>{c}</li>)}</ul>
      {draft.base_revision !== state.revision ? <p className="bench__error">当前笔记已有新编辑，请放弃这份修订并重新生成。</p> : null}
      <div className="notes-tab__actions">
        <button type="button" className="btn btn--dark" disabled={busy} onClick={() => setPreview('draft')}>预览修订</button>
        <button type="button" className="btn btn--ghost" disabled={busy} onClick={discard}>放弃修订</button>
      </div><p className="caption muted">应用后保留旧版，包括正文、批注与排版。</p>
    </section> : null}
    <section className="notes-source" aria-label="笔记来源">
      <h4>整理内容</h4>
      {stepCount ? <label className="notes-source__steps"><input type="checkbox" checked={withSteps} onChange={(e) => setWithSteps(e.target.checked)} />
        把已整理的 {stepCount} 张步骤卡作为素材</label> : null}
      <button type="button" className="btn btn--ghost" disabled={!canGenerate} onClick={() => start('video')}>{note ? '重新整理整段视频' : '整理整段视频'}</button>
      <div className="notes-source__conversation">
        <div className="notes-source__heading"><strong>根据对话{note ? '更新' : '整理'}</strong><span className="caption muted">已选 {chosenCount} 轮</span></div>
        <p className="caption muted">选择讨论过的问题，让笔记围绕你的关注点展开。</p>
        {!choosing ? <button type="button" className="btn btn--ghost" disabled={!turns.length} onClick={() => conversation?.onSelectingChange(true)}>{turns.length ? '选择加入笔记的问答' : '对话后可选择问答'}</button> : <>
          <div className="notes-source__selection-actions">
            <button type="button" className="link-btn" disabled={conversation.loading} onClick={conversation.onSelectAll}>全选可用问答</button>
            <button type="button" className="link-btn" onClick={conversation.onClear}>清空</button>
            <button type="button" className="link-btn" onClick={() => conversation.onSelectingChange(false)}>收起选择</button>
          </div>
          {conversation.loading ? <p className="caption muted" role="status">正在读取已保存的问答…</p> : null}
          {conversation.error ? <p className="bench__error" role="alert">{conversation.error}</p> : null}
          <div className="notes-source__turns">{turns.map((turn) => <div className="notes-turn" key={turn.key} data-selected={conversation.selectedKeys.has(turn.key) || undefined}>
            <label className="notes-turn__check"><input type="checkbox" aria-label={`第 ${turn.number} 轮加入笔记`} disabled={!turn.selectable || conversation.loading} checked={turn.selectable && conversation.selectedKeys.has(turn.key)} onChange={() => conversation.onToggle(turn.key)} /></label>
            <button type="button" className="notes-turn__content" onClick={() => conversation.onJump(turn.key)}>
              <span className="notes-turn__number">第 {turn.number} 轮</span><strong>{turn.question || turn.title || '仅使用任务指令'}</strong>
              {turn.answerPreview || turn.answer?.text ? <span className="notes-turn__answer">{turn.answerPreview || turn.answer.text}</span> : null}
              {!turn.selectable ? <span className="notes-turn__reason">{turn.reason || '尚不可选择'}</span> : null}
            </button>
          </div>)}</div>
          <button type="button" className="link-btn" disabled={conversation.loading} onClick={conversation.onRefresh}>重新读取保存状态</button>
        </>}
        {choosing || chosenCount ? <>
          <label className="notes-source__instruction">补充要求（可选）<textarea rows={3} maxLength={2000} value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="例如：重点拆解转场和镜头运动，保留对应截图" /></label>
          <button type="button" className="btn btn--dark" disabled={!canGenerate || !chosenCount || conversation?.loading || Boolean(conversation?.error)} onClick={() => start('conversation')}>{note ? '根据所选对话更新笔记' : '根据所选对话生成笔记'}</button>
        </> : null}
      </div>
      {draft ? <p className="caption muted">先预览并应用或放弃当前修订，再生成新的内容。</p> : null}
    </section>
    {state?.history?.length ? <details className="notes-history">
      <summary>历史版本 · {state.history.length}</summary><p className="caption muted">恢复前会保存当前版本。</p>
      {state.history.map((v) => <div className="notes-history__item" key={v.id}>
        <span><strong>{v.title || '笔记'}</strong><small>{versionDate(v.created)} · {v.source === 'conversation' ? '根据对话整理' : '视频笔记'}</small></span>
        <button type="button" className="btn btn--ghost" disabled={busy || running || Boolean(draft)} onClick={() => mutate(() => restoreNoteRevision(jobId, v.id, state.revision))}>恢复</button>
      </div>)}
    </details> : null}
    <div className="notes-tab__qa"><h4 className="eyebrow">问答记录</h4><p className="caption muted">也可以保留原始问答、时间点和截图，导出为 Markdown 或 PDF。</p>
      <button type="button" className="btn btn--ghost" disabled={!messages.length} onClick={() => setExportOpen(true)}>{messages.length ? '导出问答记录' : '还没有问答'}</button>
    </div>
    {exportOpen ? <ExportDialog sessionId={jobId} messages={messages} onClose={() => setExportOpen(false)} /> : null}
    {imageSrc ? <PreviewDialog title="笔记长图" src={imageSrc} image onClose={() => setImageSrc(null)}>
      <button type="button" className="btn btn--ghost" onClick={() => setImageSrc(null)}>关闭</button><a className="btn btn--dark" href={imageSrc} download="笔记.png">下载长图</a>
    </PreviewDialog> : null}
    {preview ? <PreviewDialog className="notes-revision-preview" title={preview === 'draft' ? '笔记修订预览' : '笔记导出预览'} src={previewUrl} onClose={() => setPreview(null)}>
      {draft ? <>
        <div className="notes-revision__preview-changes" aria-live="polite"><strong>{preview === 'draft' ? '本次修订' : '当前版本'}</strong>{preview === 'draft' ? <ul>{(draft.changes || []).map((c, i) => <li key={i}>{c}</li>)}</ul> : null}{error ? <p role="alert">{error}</p> : null}</div>
        <button type="button" className="btn btn--ghost" onClick={() => setPreview(preview === 'draft' ? 'current' : 'draft')}>{preview === 'draft' ? '查看当前版本' : '查看修订稿'}</button>
        <button type="button" className="btn btn--dark" disabled={busy || draft.base_revision !== state.revision} onClick={apply}>{busy ? '正在应用…' : '应用修订'}</button>
      </> : <a className="btn btn--dark" href={notesExportUrl(jobId)} download>导出 Markdown（含图）</a>}
      <button type="button" className="btn btn--ghost" onClick={() => setPreview(null)}>关闭预览</button>
    </PreviewDialog> : null}
  </div>
}
