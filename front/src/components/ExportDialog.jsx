import React, { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconBook, IconClose } from './Icons'
import { exportSessionUrl, getSession } from '../api/client'
import { fmtTime } from '../lib/format'
import '../styles/export.css'

// Map the current view to durable rows in order. Keep local streaming state and never replace the
// chat with a restored snapshot; a running answer remains pending even if an older row matches.
function withSavedIds(messages, saved) {
  let cursor = 0
  return messages.map((message) => {
    if (message.status === 'running') return { ...message, savedId: null }
    const index = saved.findIndex((row, i) => i >= cursor && row.role === message.role
      && (message.savedId != null ? row.id === message.savedId
        : (row.manual || null) === (message.manual || null) && (row.content || '') === (message.text || '')))
    if (index < 0) return { ...message, savedId: null }
    cursor = index + 1
    return { ...message, savedId: saved[index].id }
  })
}

// The conversation as exportable turns: Q&A pairs (a question and the answer that followed) and
// hand-framed replays. Each turn carries the saved rows' backend ids, so a partial export can name
// exactly what to include; turns still being answered (or not yet saved) cannot be picked yet.
export function exportItems(messages) {
  const items = []
  for (const m of messages) {
    if (m.manual === 'replay') {
      const replay = m.parts?.flatMap((part) => part.calls || []).find((call) => call.tool === 'frames.replay')?.data
      const [start, end] = m.range || [replay?.start, replay?.end]
      items.push({
        key: m.id, kind: 'manual', ids: [m.savedId].filter(Boolean),
        title: start != null && end != null ? `手动慢放 ${fmtTime(start)}–${fmtTime(end)}` : '手动慢放',
        pending: m.savedId == null || m.status === 'running',
      })
      continue
    }
    if (m.role === 'user') {
      items.push({ key: m.id, kind: 'qa', ids: [m.savedId].filter(Boolean), question: m.text || '', answer: null, pending: m.savedId == null })
    } else if (m.role === 'assistant' && items.length && items.at(-1).kind === 'qa' && !items.at(-1).answer) {
      items.at(-1).answer = m
      items.at(-1).pending = items.at(-1).pending || m.status === 'running' || m.savedId == null
      if (m.savedId != null) items.at(-1).ids.push(m.savedId)
    } else if (m.role === 'assistant') {
      items.push({ key: m.id, kind: 'qa', ids: [m.savedId].filter(Boolean), question: '', answer: m, pending: m.savedId == null || m.status === 'running' })
    }
  }
  return items
}

/** Pick the turns and the format, then download the Markdown bundle or open the PDF print page. */
export default function ExportDialog({ sessionId, messages, onClose }) {
  const [saved, setSaved] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)
  const [refresh, setRefresh] = useState(0)
  // Re-read when an answer finishes, not on each streaming token.
  const statusKey = messages.map((m) => `${m.id}:${m.status || 'done'}`).join('|')
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getSession(sessionId, { signal: controller.signal }).then((session) => {
      if (!controller.signal.aborted) setSaved(session.messages || [])
    }).catch((err) => {
      if (err.name !== 'AbortError') setError(err.message)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [sessionId, statusKey, refresh])
  const items = useMemo(() => exportItems(withSavedIds(messages, saved)), [messages, saved])
  const pickable = items.filter((it) => !it.pending)
  const [selection, setSelection] = useState(null)
  const checked = selection ?? new Set(pickable.map((it) => it.key))
  const chosen = pickable.filter((it) => checked.has(it.key))
  const canExport = !loading && !exporting && !error && chosen.length > 0

  const allChecked = pickable.length > 0 && pickable.every((it) => checked.has(it.key))
  const toggleAll = () => setSelection(allChecked ? new Set() : new Set(pickable.map((it) => it.key)))
  const toggle = (item) => setSelection(() => {
    const next = new Set(checked)
    if (next.has(item.key)) next.delete(item.key)
    else next.add(item.key)
    return next
  })

  const exportUrl = (format) => {
    const ids = chosen.flatMap((it) => it.ids)
    return exportSessionUrl(sessionId, { format, ids })
  }

  const downloadMarkdown = async () => {
    if (!canExport) return
    setExporting(true)
    try {
      const response = await fetch(exportUrl('md'))
      if (!response.ok) throw new Error(`笔记导出失败（HTTP ${response.status}），请重新读取保存状态后再试`)
      const url = URL.createObjectURL(await response.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = 'note.zip'
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      onClose()
    } catch (err) {
      setError(err.message || '笔记导出失败，请稍后再试')
    } finally {
      setExporting(false)
    }
  }

  const openPrintPage = () => {
    if (!canExport) return
    window.open(exportUrl('pdf'), '_blank', 'noopener')
    onClose()
  }

  return createPortal(
    <div className="overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="export-dialog" role="dialog" aria-label="导出笔记">
        <header className="export-dialog__head">
          <strong><IconBook size={14} /> 导出笔记</strong>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>
        </header>
        <p className="export-dialog__hint">
          选择要保留的问答（含回答引用的关键帧、慢放与补看画面及来源链接）。Markdown 打包为 zip（笔记 + 图片）；
          PDF 会打开一个打印页，用浏览器的「打印 → 另存为 PDF」保存。
        </p>
        {loading ? <p role="status" className="export-dialog__hint">正在读取已保存的消息…</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        {!loading && (error || items.some((it) => it.pending)) ? (
          <button type="button" className="btn btn--ghost" onClick={() => setRefresh((n) => n + 1)}>重新读取保存状态</button>
        ) : null}
        <div className="export-dialog__list">
          <label className="export-item export-item--all">
            <input type="checkbox" disabled={loading || !pickable.length} checked={allChecked} onChange={toggleAll} />
            <span>全选（{chosen.length}/{pickable.length}）</span>
          </label>
          {items.map((it) => (
            <label key={it.key} className="export-item" data-kind={it.kind} data-pending={it.pending || undefined}>
              <input
                type="checkbox"
                disabled={loading || it.pending}
                checked={!it.pending && checked.has(it.key)}
                onChange={() => toggle(it)}
              />
              <span className="export-item__title">
                {it.kind === 'manual' ? it.title : (it.question || (it.answer?.text || '（没有文字的回答）'))}
              </span>
              <span className="export-item__meta">{it.pending ? '尚未保存' : it.kind === 'manual' ? '画面' : '问答'}</span>
            </label>
          ))}
          {!items.length ? <p className="export-dialog__empty">这个会话还没有可以导出的内容。</p> : null}
        </div>
        <footer className="export-dialog__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn--ghost" disabled={!canExport} onClick={downloadMarkdown}>导出 Markdown</button>
          <button type="button" className="btn btn--dark" disabled={!canExport} onClick={openPrintPage}>导出 PDF（打印页）</button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}
