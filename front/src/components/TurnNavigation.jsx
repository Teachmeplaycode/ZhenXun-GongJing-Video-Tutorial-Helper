import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconBook, IconChat, IconClose } from './Icons'
import { useEscape } from '../lib/useEscape'
import '../styles/conversation.css'

function TurnList({ conversation, activeKey, onJump }) {
  const { turns, selecting, selectedKeys, onToggle, loading } = conversation
  return <ol className="turn-directory__list">
    {turns.map((turn) => <li key={turn.key} data-active={turn.key === activeKey || undefined}>
      {selecting ? <label className="turn-directory__check" title={turn.reason || `选择第 ${turn.number} 轮加入笔记`}>
        <input type="checkbox" checked={turn.selectable && selectedKeys.has(turn.key)} disabled={loading || !turn.selectable}
          onChange={() => onToggle(turn.key)} aria-label={`选择第 ${turn.number} 轮加入笔记`} />
      </label> : null}
      <button type="button" className="turn-directory__item" aria-current={turn.key === activeKey ? 'location' : undefined}
        onClick={() => onJump(turn.key)}>
        <span className="turn-directory__number">{String(turn.number).padStart(2, '0')}</span>
        <span className="turn-directory__copy"><span className="turn-directory__question">{turn.title}</span>
          <span className="turn-directory__status">{turn.kind === 'clip' ? '视频片段' : turn.kind === 'replay' ? '手动慢放'
            : turn.status === 'running' ? '正在回答' : turn.status === 'error' ? '回答未完成' : '问答'}
            {selecting && turn.reason && turn.kind === 'qa' ? ` · ${turn.reason}` : ''}</span>
        </span>
      </button>
    </li>)}
  </ol>
}

/** The conversation directory belongs to the chat column, independent of the workbench. */
export default function TurnNavigation({ conversation, activeKey, compact, onJump }) {
  const [open, setOpen] = useState(false)
  const [peek, setPeek] = useState(null)
  const triggerRef = useRef(null)
  const panelRef = useRef(null)
  const listRef = useRef(null)
  const { turns, selecting, chosen, onSelectingChange, onReview } = conversation
  const close = () => { setOpen(false); triggerRef.current?.focus() }
  useEscape(close, open)
  useEffect(() => {
    if (open) panelRef.current?.querySelector('button')?.focus()
  }, [open])
  useEffect(() => {
    if (!open) return undefined
    const outside = (e) => { if (!panelRef.current?.contains(e.target) && !triggerRef.current?.contains(e.target)) setOpen(false) }
    window.addEventListener('pointerdown', outside)
    return () => window.removeEventListener('pointerdown', outside)
  }, [open])
  useEffect(() => {
    const rail = listRef.current
    const item = rail?.querySelector('[aria-current="location"]')
    if (item) {
      const delta = item.offsetTop - rail.scrollTop
      if (delta < 0 || delta > rail.clientHeight - item.offsetHeight) rail.scrollTop = item.offsetTop - rail.clientHeight / 2
    }
  }, [activeKey])
  if (!turns.length) return null
  const jump = (key) => { onJump(key); setOpen(false); setPeek(null) }
  const focusTrap = (e) => {
    if (!compact || e.key !== 'Tab') return
    const focusable = [...panelRef.current.querySelectorAll('button:not(:disabled),input:not(:disabled)')]
    const first = focusable[0], last = focusable.at(-1)
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
  }
  const panel = open ? <>
    {compact ? <div className="turn-directory__backdrop" onClick={close} /> : null}
    <section ref={panelRef} className={`turn-directory${compact ? ' turn-directory--compact' : ''}`}
      role={compact ? 'dialog' : 'region'} aria-modal={compact || undefined} aria-label="对话目录" onKeyDown={focusTrap}>
      <header className="turn-directory__head"><div><strong>对话目录</strong><span>{turns.length} 轮</span></div>
        <button type="button" className="icon-btn" aria-label="关闭对话目录" onClick={close}><IconClose size={16} /></button>
      </header>
      <div className="turn-directory__tools">
        <button type="button" className="link-btn" onClick={() => onSelectingChange(!selecting)}>
          {selecting ? '退出选材' : '选择加入笔记'}</button>
        {selecting ? <><button type="button" className="link-btn" onClick={conversation.onSelectAll} disabled={conversation.loading}>全选</button>
          <button type="button" className="link-btn" onClick={conversation.onClear}>清空</button></> : null}
      </div>
      {conversation.error ? <p className="turn-directory__error" role="alert">{conversation.error}
        <button type="button" className="link-btn" onClick={conversation.onRefresh}>重试读取</button></p> : null}
      <TurnList conversation={conversation} activeKey={activeKey} onJump={jump} />
      {selecting ? <footer className="turn-directory__footer"><span aria-live="polite">已选 {chosen.length} 轮问答</span>
        <button type="button" className="btn btn--dark" disabled={!chosen.length || conversation.loading} onClick={() => { setOpen(false); onReview() }}>
          <IconBook size={14} /> 整理已选问答</button>
      </footer> : null}
    </section>
  </> : null
  return <>
    {compact ? <div className="turn-nav-entry"><button ref={triggerRef} type="button" className="turn-nav-entry__button"
      onClick={() => setOpen((value) => !value)} aria-haspopup="dialog" aria-expanded={open}>
      <IconChat size={15} /> 对话目录 <span>{turns.length} 轮</span>{selecting ? <span>已选 {chosen.length}</span> : null}
    </button></div> : <nav className="turn-rail" aria-label="对话轮次">
      <button ref={triggerRef} type="button" className="turn-rail__toggle" aria-label="展开对话目录" aria-expanded={open}
        onClick={() => setOpen((value) => !value)}><IconChat size={16} /></button>
      <div ref={listRef} className="turn-rail__marks">
        {turns.map((turn) => <button key={turn.key} type="button" className="turn-rail__mark"
          aria-label={`跳转第 ${turn.number} 轮：${turn.title}`} aria-current={turn.key === activeKey ? 'location' : undefined}
          data-selected={selectedKeysHas(conversation, turn) || undefined}
          onPointerEnter={() => setPeek(turn)} onPointerLeave={() => setPeek(null)}
          onFocus={() => setPeek(turn)} onBlur={() => setPeek(null)} onClick={() => jump(turn.key)}>
          <span />
        </button>)}
      </div>
      <span className="turn-rail__count" aria-hidden="true">{turns.find((turn) => turn.key === activeKey)?.number || 1}/{turns.length}</span>
      {peek && !open ? <div className="turn-rail__preview" role="tooltip"><span>第 {peek.number} 轮</span><p>{peek.title}</p></div> : null}
    </nav>}
    {compact && panel ? createPortal(panel, document.body) : panel}
  </>
}

function selectedKeysHas(conversation, turn) {
  return conversation.selecting && turn.selectable && conversation.selectedKeys.has(turn.key)
}
