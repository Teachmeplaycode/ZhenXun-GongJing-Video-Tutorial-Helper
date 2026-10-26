import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { getNotes, notesExportUrl, notesImageUrl, saveNoteBoard } from '../api/client'
import PreviewDialog from '../components/PreviewDialog'
import { BlockEdit, BlockView } from './blocks'
import { bounds, defaultBoard, flow, readingOrder, settleRevision } from './layout'
import './notes.css'

const MIN_ZOOM = 0.15
const MAX_ZOOM = 3
const MIN_W = 160
const SAVE_DELAY = 800 // ms after the last change
const HISTORY = 60
const clamp = (v, a, b) => Math.min(b, Math.max(a, v))
const TYPE_LABEL = { title: '标题', section: '小节', figure: '图片', mindmap: '思维导图', text: '文字' }

// The note editor (#/notes/<jobId>): the agent's note laid out on an endless canvas. Drag the
// background (or scroll) to move around, ⌘/Ctrl + scroll or the buttons to zoom; drag a block to
// move it, its corner to resize it, double-click to edit it. Changes save by themselves; the export
// and the printout read the blocks top to bottom, left to right.
export default function NoteEditor({ jobId }) {
  const [state, setState] = useState({ loading: true, error: '', note: null })
  const [board, setBoard] = useState(null)
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null)
  const [saveState, setSaveState] = useState('saved') // saved | pending | saving | error
  const canvasRef = useRef(null)
  const blockRefs = useRef({})
  const heights = useRef({})
  const past = useRef([])
  const future = useRef([])
  const saveTimer = useRef(0)
  const latest = useRef(null)
  const revision = useRef(null)
  const saving = useRef(null)
  const conflicted = useRef(false)
  const [needsFlow, setNeedsFlow] = useState(false)

  // ---- load --------------------------------------------------------------------------------
  useEffect(() => {
    let stopped = false
    getNotes(jobId).then((r) => {
      if (stopped) return
      if (r.status !== 'done' || !r.note) {
        setState({ loading: false, error: r.status === 'running' ? '笔记还在生成，请稍后刷新。' : '这个视频还没有生成笔记：回到工作台的「笔记」里先生成。', note: null })
        return
      }
      setState({ loading: false, error: '', note: r.note })
      revision.current = r.revision || null
      document.title = `${r.note.title} · 笔记`
      if (r.board?.blocks) {
        setBoard({ ...r.board, version: 1, viewport: r.board.viewport || { x: 40, y: 40, zoom: 0.8 }, blocks: r.board.blocks })
        if (r.board.needs_measure) setNeedsFlow(true)
      }
      else {
        setBoard(defaultBoard(r.note))
        setNeedsFlow(true) // place the blocks again once their real heights are known
      }
    }).catch((err) => { if (!stopped) setState({ loading: false, error: err.message, note: null }) })
    return () => { stopped = true }
  }, [jobId])

  // Real heights (unscaled: offsetHeight ignores the canvas transform), for flow, fit and export.
  const measure = useCallback(() => {
    for (const [id, el] of Object.entries(blockRefs.current)) if (el) heights.current[id] = el.offsetHeight
  }, [])
  useLayoutEffect(measure)

  // ---- save ----------------------------------------------------------------------------------
  const save = useCallback(async () => {
    clearTimeout(saveTimer.current)
    saveTimer.current = 0
    if (conflicted.current) return false
    if (saving.current) return saving.current
    if (!latest.current) return true
    saving.current = (async () => {
      let sent
      setSaveState('saving')
      try {
        do {
          sent = latest.current
          const result = await saveNoteBoard(jobId, sent, revision.current)
          revision.current = result.revision || revision.current
        } while (latest.current !== sent)
        setSaveState('saved')
        return true
      } catch (err) {
        conflicted.current = err.status === 409
        setSaveState(conflicted.current ? 'conflict' : 'error')
        return false
      }
    })()
    try { return await saving.current } finally { saving.current = null }
  }, [jobId])
  const schedule = useCallback((b) => {
    latest.current = b
    if (conflicted.current) return
    setSaveState('pending')
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(save, SAVE_DELAY)
  }, [save])
  useEffect(() => {
    const flush = () => { if (saveTimer.current) save() }
    window.addEventListener('beforeunload', flush)
    return () => window.removeEventListener('beforeunload', flush)
  }, [save])

  // Every content change goes through here: history for undo, then a save.
  const commit = useCallback((next, { history = true } = {}) => {
    setBoard((prev) => {
      const b = typeof next === 'function' ? next(prev) : next
      if (history && prev) {
        past.current = [...past.current.slice(-HISTORY + 1), prev.blocks]
        future.current = []
      }
      schedule(b)
      return b
    })
  }, [schedule])
  const setViewport = useCallback((fn) => setBoard((b) => {
    const next = { ...b, viewport: fn(b.viewport) }
    schedule(next)
    return next
  }), [schedule])

  // First open: wait for the pictures, measure, place everything without overlaps, fit to screen.
  useEffect(() => {
    if (!needsFlow || !board) return
    let stopped = false
    const imgs = [...(canvasRef.current?.querySelectorAll('img') || [])]
    const ready = Promise.race([Promise.all(imgs.map((i) => (i.complete ? null : i.decode().catch(() => null)))), new Promise((r) => setTimeout(r, 2500))])
    ready.then(() => requestAnimationFrame(() => {
      if (stopped) return
      measure()
      setNeedsFlow(false)
      const fitNewBoard = !board.needs_measure
      commit((b) => {
        const { needs_measure, changed_blocks, ...copy } = b
        return { ...copy, blocks: needs_measure ? settleRevision(b.blocks, heights.current, changed_blocks) : flow(b.blocks, heights.current) }
      }, { history: false })
      if (fitNewBoard) requestAnimationFrame(() => fit())
    }))
    return () => { stopped = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsFlow, board === null])

  // ---- view: pan and zoom ---------------------------------------------------------------------
  const zoomAt = useCallback((factor, cx, cy) => setViewport((v) => {
    const zoom = clamp(v.zoom * factor, MIN_ZOOM, MAX_ZOOM)
    const k = zoom / v.zoom
    return { zoom, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }
  }), [setViewport])
  const zoomCenter = (factor) => {
    const r = canvasRef.current.getBoundingClientRect()
    zoomAt(factor, r.width / 2, r.height / 2)
  }
  const fit = useCallback(() => {
    const el = canvasRef.current
    if (!el) return
    setBoard((b) => {
      if (!b) return b
      measure()
      // A note reads like a page: fit its width, start at the top, scroll down from there.
      const box = bounds(b.blocks, heights.current)
      const pad = 48
      const zoom = clamp((el.clientWidth - pad * 2) / box.w, MIN_ZOOM, 1)
      const next = { ...b, viewport: { zoom, x: pad - box.x * zoom + (el.clientWidth - pad * 2 - box.w * zoom) / 2, y: pad - box.y * zoom } }
      schedule(next)
      return next
    })
  }, [measure, schedule])
  // Wheel: zoom with ⌘/Ctrl (and trackpad pinch, which arrives as ctrl+wheel), pan otherwise.
  useEffect(() => {
    const el = canvasRef.current
    if (!el) return undefined
    const onWheel = (e) => {
      if (e.target.closest('.nb-edit')) return
      e.preventDefault()
      const r = el.getBoundingClientRect()
      if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * 0.0025), e.clientX - r.left, e.clientY - r.top)
      else setViewport((v) => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomAt, setViewport, board === null]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- pointer: pan the background, move or resize a block ------------------------------------------
  const gesture = useRef(null)
  const onPointerDown = (e) => {
    if (e.button !== 0 || editing) return
    const blockEl = e.target.closest('[data-block]')
    const resize = e.target.closest('[data-resize]')
    const v = board.viewport
    if (!blockEl) {
      setSelected(null)
      gesture.current = { kind: 'pan', sx: e.clientX, sy: e.clientY, x: v.x, y: v.y }
    } else {
      const id = blockEl.dataset.block
      const b = board.blocks.find((x) => x.id === id)
      setSelected(id)
      gesture.current = { kind: resize ? 'resize' : 'move', id, sx: e.clientX, sy: e.clientY, x: b.x, y: b.y, w: b.w, before: board.blocks, moved: false }
    }
    gesture.current.pointer = e.pointerId
  }
  // Take the pointer only once it moves: a still press stays a click (or a double-click to edit).
  const capture = (e, g) => {
    if (!g.captured) { canvasRef.current.setPointerCapture?.(g.pointer); g.captured = true }
  }
  const onPointerMove = (e) => {
    const g = gesture.current
    if (!g) return
    const dx = e.clientX - g.sx
    const dy = e.clientY - g.sy
    if (g.kind === 'pan') {
      capture(e, g)
      setBoard((b) => ({ ...b, viewport: { ...b.viewport, x: g.x + dx, y: g.y + dy } }))
      return
    }
    if (!g.moved && Math.hypot(dx, dy) < 3) return
    capture(e, g)
    g.moved = true
    const z = board.viewport.zoom
    setBoard((b) => ({ ...b, blocks: b.blocks.map((x) => (x.id !== g.id ? x
      : g.kind === 'move' ? { ...x, x: Math.round(g.x + dx / z), y: Math.round(g.y + dy / z) }
        : { ...x, w: Math.max(MIN_W, Math.round(g.w + dx / z)) })) }))
  }
  const onPointerUp = () => {
    const g = gesture.current
    gesture.current = null
    if (!g) return
    if (g.kind === 'pan') schedule({ ...board })
    else if (g.moved) {
      past.current = [...past.current.slice(-HISTORY + 1), g.before]
      future.current = []
      schedule(board)
    }
  }

  // ---- edit, add, delete, undo ------------------------------------------------------------------------
  const patch = (id, change) => commit((b) => ({ ...b, blocks: b.blocks.map((x) => (x.id === id ? { ...x, ...change } : x)) }))
  const remove = (id) => {
    commit((b) => ({ ...b, blocks: b.blocks.filter((x) => x.id !== id) }))
    setSelected(null)
  }
  const addText = () => {
    const el = canvasRef.current
    const v = board.viewport
    const id = `text-${Date.now().toString(36)}`
    const x = Math.round((el.clientWidth / 2 - v.x) / v.zoom - 160)
    const y = Math.round((el.clientHeight / 2 - v.y) / v.zoom - 40)
    commit((b) => ({ ...b, blocks: [...b.blocks, { id, type: 'text', x, y, w: 320, text: '' }] }))
    setSelected(id)
    setEditing(id)
  }
  const relayout = () => {
    measure()
    commit((b) => ({ ...b, blocks: flow(b.blocks, heights.current) }))
    requestAnimationFrame(() => fit())
  }
  const undo = useCallback(() => {
    if (!past.current.length) return
    setBoard((b) => {
      future.current = [b.blocks, ...future.current]
      const next = { ...b, blocks: past.current.pop() }
      schedule(next)
      return next
    })
  }, [schedule])
  const redo = useCallback(() => {
    if (!future.current.length) return
    setBoard((b) => {
      past.current = [...past.current, b.blocks]
      const next = { ...b, blocks: future.current.shift() }
      schedule(next)
      return next
    })
  }, [schedule])
  useEffect(() => {
    const onKey = (e) => {
      if (editing || e.target.closest?.('input, textarea')) return
      const mod = e.metaKey || e.ctrlKey
      if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo() }
      else if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); redo() }
      else if ((e.key === 'Delete' || e.key === 'Backspace') && selected) { e.preventDefault(); remove(selected) }
      else if (e.key === 'Enter' && selected) { e.preventDefault(); setEditing(selected) }
      else if (e.key === 'Escape') setSelected(null)
      else if (mod && (e.key === '=' || e.key === '+')) { e.preventDefault(); zoomCenter(1.2) }
      else if (mod && e.key === '-') { e.preventDefault(); zoomCenter(1 / 1.2) }
      else if (mod && e.key === '0') { e.preventDefault(); fit() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const exportMarkdown = async () => {
    if (!await save()) return
    window.location.href = notesExportUrl(jobId)
  }
  const [shown, setShown] = useState(null) // { kind: 'page' | 'image', src } — the export previewed
  const previewExport = async (kind) => {
    if (!await save()) return // the export reads the saved board
    setShown({ kind, src: kind === 'image' ? notesImageUrl(jobId) : `${notesExportUrl(jobId)}?preview=1&t=${Date.now()}` })
  }
  const print = async () => {
    if (!await save()) return
    window.print()
  }

  if (state.loading) return <div className="nb-page nb-page--message"><p className="muted">正在打开笔记…</p></div>
  if (state.error || !board) return <div className="nb-page nb-page--message"><p>{state.error}</p></div>

  const v = board.viewport
  const savedLabel = { saved: '已保存', pending: '有改动', saving: '保存中…', error: '保存失败，请重试', conflict: '版本已更新，保存已暂停' }[saveState]
  return (
    <div className="nb-page">
      <header className="nb-bar">
        <div className="nb-bar__title">
          <span className="eyebrow">笔记</span>
          <strong>{state.note.title}</strong>
          <span className="mono-sm nb-bar__save" data-state={saveState} role="status">{savedLabel}</span>
        </div>
        <div className="nb-bar__tools">
          <button type="button" className="btn btn--ghost" onClick={addText}>添加文字</button>
          <button type="button" className="btn btn--ghost" onClick={relayout} title="按页面顺序重新排列标题、小节和图片">整理布局</button>
          <span className="nb-zoom">
            <button type="button" className="icon-btn" onClick={() => zoomCenter(1 / 1.2)} aria-label="缩小">−</button>
            <button type="button" className="nb-zoom__value mono-sm" onClick={fit} title="适应宽度，回到顶部（⌘/Ctrl + 0）">{Math.round(v.zoom * 100)}%</button>
            <button type="button" className="icon-btn" onClick={() => zoomCenter(1.2)} aria-label="放大">+</button>
          </span>
          <button type="button" className="btn btn--ghost" onClick={print}>打印 / PDF</button>
          <button type="button" className="btn btn--ghost" onClick={() => previewExport('page')}>预览</button>
          <button type="button" className="btn btn--ghost" onClick={() => previewExport('image')}>存为长图</button>
          <button type="button" className="btn btn--dark" onClick={exportMarkdown}>导出 Markdown</button>
        </div>
      </header>

      {saveState === 'conflict' ? <div className="nb-conflict" role="alert">笔记已在其他页面更新。此页改动尚未保存，请保留需要的内容后重新载入。
        <button type="button" className="btn btn--ghost" onClick={() => window.location.reload()}>重新载入</button>
      </div> : null}

      {shown ? (
        <PreviewDialog title={shown.kind === 'image' ? '笔记长图' : '导出预览'} src={shown.src} image={shown.kind === 'image'} onClose={() => setShown(null)}>
          <button type="button" className="btn btn--ghost" onClick={() => setShown(null)}>关闭</button>
          {shown.kind === 'image'
            ? <a className="btn btn--dark" href={shown.src} download="笔记.png">下载长图</a>
            : <button type="button" className="btn btn--dark" onClick={exportMarkdown}>导出 Markdown</button>}
        </PreviewDialog>
      ) : null}

      <div ref={canvasRef} className="nb-canvas" style={{ '--grid': `${24 * v.zoom}px`, backgroundPosition: `${v.x}px ${v.y}px` }}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
        data-panning={gesture.current?.kind === 'pan' || undefined}>
        <div className="nb-world" style={{ transform: `translate(${v.x}px, ${v.y}px) scale(${v.zoom})` }}>
          {board.blocks.map((b) => (
            <div key={b.id} ref={(el) => { blockRefs.current[b.id] = el }} data-block={b.id} data-type={b.type}
              className="nb-block" data-selected={selected === b.id || undefined} data-editing={editing === b.id || undefined}
              style={{ left: b.x, top: b.y, width: b.w }}
              onDoubleClick={() => setEditing(b.id)}>
              {editing === b.id ? (
                <BlockEdit block={b} onCancel={() => setEditing(null)} onDone={(change) => { patch(b.id, change); setEditing(null) }} />
              ) : <BlockView block={b} />}
              {selected === b.id && editing !== b.id ? (
                <>
                  <span className="nb-block__tag mono-sm">{TYPE_LABEL[b.type]} · 双击编辑</span>
                  <button type="button" className="nb-block__delete" aria-label="删除这一块" onPointerDown={(e) => e.stopPropagation()} onClick={() => remove(b.id)}>×</button>
                  <span className="nb-block__resize" data-resize aria-hidden="true" />
                </>
              ) : null}
            </div>
          ))}
        </div>
        <p className="nb-hint caption">拖动空白处移动画布 · ⌘/Ctrl + 滚轮缩放 · 拖动方块调整位置，拖右下角改宽度 · 双击编辑 · Delete 删除 · ⌘/Ctrl + Z 撤销</p>
      </div>

      {/* What the printer (and "Save as PDF") gets: the blocks in reading order, as a document. */}
      <article className="nb-print" aria-hidden="true">
        {readingOrder(board.blocks).map((b) => <div key={b.id} className="nb-print__block" data-type={b.type}><BlockView block={b} /></div>)}
      </article>
    </div>
  )
}
