import React, { useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { IconBook, IconClose, IconGlobe, IconPlus, IconSend, IconSlash, IconStop } from './Icons'
import { fmtTime, frameNo } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'

// Input bar in the manner of React Bits' PromptBar, trimmed to what this app uses: a growing text
// field, switches for the tools a question may use, a "/" menu of common tasks, the frames attached
// from the timeline, and send / stop.

export const COMMANDS = [
  { key: '总结', hint: '分点总结视频内容', text: '总结这个视频的主要内容，分 3–5 点，每点注明时间点。' },
  { key: '时间线', hint: '按时间列出关键事件', text: '按时间顺序列出视频里的关键事件和画面变化，每条注明时间点。' },
  { key: '核实', hint: '查资料核实视频里的说法', text: '核实视频里的主要说法是否正确，请查资料并给出来源链接。' },
  { key: '论文', hint: '找相关的学术论文', text: '找几篇和这个视频主题相关的学术论文，说明它们和视频内容的关系。' },
  { key: '细看', hint: '仔细看某一段画面', text: '仔细看 00:00 到 00:30 这段画面，描述具体发生了什么。' },
]

const SWITCHES = [
  { key: 'web', label: '联网', Icon: IconGlobe, title: '允许搜索网页和阅读网页' },
  { key: 'papers', label: '论文', Icon: IconBook, title: '允许检索学术论文' },
]

export const loadSwitches = () => {
  try {
    return { web: true, papers: true, ...JSON.parse(localStorage.getItem('composer.switches') || '{}') }
  } catch {
    return { web: true, papers: true }
  }
}

export default function Composer({ draft, setDraft, running, onSend, onStop, selected, onRemoveFrame, onClearSelection, onPickFrames, scopeNote }) {
  const [switches, setSwitches] = useState(loadSwitches)
  const [active, setActive] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  const menuRef = useRef(null)
  const inputRef = useRef(null)

  const slash = /^\/(\S*)$/.exec(draft)
  const matches = useMemo(() => (slash ? COMMANDS.filter((c) => c.key.includes(slash[1])) : []), [slash?.[1]]) // eslint-disable-line react-hooks/exhaustive-deps
  const menuOpen = Boolean(slash) && matches.length > 0 && !dismissed

  useLayoutEffect(() => {
    if (menuOpen && menuRef.current && !prefersReducedMotion()) {
      gsap.fromTo(menuRef.current, { opacity: 0, y: 6, scale: 0.98 }, { opacity: 1, y: 0, scale: 1, duration: 0.16, ease: 'power2.out' })
    }
  }, [menuOpen])

  const toggle = (key) => setSwitches((s) => {
    const next = { ...s, [key]: !s[key] }
    try {
      localStorage.setItem('composer.switches', JSON.stringify(next))
    } catch {
      // private mode: the switch still works for this session
    }
    return next
  })

  const pick = (cmd) => {
    setDraft(cmd.text)
    setDismissed(false)
    requestAnimationFrame(() => {
      const el = inputRef.current
      el?.focus()
      // Put the caret on the first time range so "细看" is quick to adjust.
      const at = cmd.text.indexOf('00:00')
      if (el && at >= 0) el.setSelectionRange(at, at + 5)
    })
  }

  const submit = () => {
    const q = draft.trim()
    if (!q || running || menuOpen) return
    onSend(q, switches)
  }

  const onKeyDown = (e) => {
    if (menuOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % matches.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + matches.length) % matches.length); return }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pick(matches[Math.min(active, matches.length - 1)]); return }
      if (e.key === 'Escape') { e.preventDefault(); setDismissed(true); return }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="composer">
      {selected.length ? (
        <div className="composer__attach">
          {selected.length <= 5 ? selected.map((f) => (
            <span key={f.index} className="frame-chip">
              <img src={f.src} alt="" />
              <span className="mono-sm">{frameNo(f.index)} · {fmtTime(f.time)}</span>
              <button type="button" className="icon-btn icon-btn--sm" aria-label="移除" onClick={() => onRemoveFrame(f.index)}><IconClose size={12} /></button>
            </span>
          )) : <span className="frame-chip mono-sm">已选 {selected.length} 帧 · {fmtTime(selected[0].time)} – {fmtTime(selected[selected.length - 1].time)}</span>}
          <button type="button" className="link-btn" onClick={onClearSelection}>清除</button>
        </div>
      ) : null}
      <div className="composer__box">
        {menuOpen ? (
          <ul ref={menuRef} className="slash-menu" role="listbox" aria-label="常用任务">
            {matches.map((c, i) => (
              <li key={c.key} role="option" aria-selected={i === active}>
                <button type="button" className="slash-menu__item" data-active={i === active || undefined}
                  onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); pick(c) }}>
                  <span className="slash-menu__key mono-sm">/{c.key}</span>
                  <span className="slash-menu__hint">{c.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <textarea
          ref={inputRef}
          className="composer__input"
          rows={1}
          value={draft}
          placeholder="问点什么…  输入 / 选择常用任务，Enter 发送，Shift + Enter 换行"
          onChange={(e) => { setDraft(e.target.value); setActive(0); setDismissed(false) }}
          onKeyDown={onKeyDown}
        />
        <div className="composer__bar">
          <button type="button" className="chip-btn" onClick={onPickFrames} title="在时间轴上点选关键帧作为附件">
            <IconPlus size={13} /> 选帧
          </button>
          {SWITCHES.map(({ key, label, Icon, title }) => (
            <button key={key} type="button" className="chip-btn" data-on={switches[key] || undefined} aria-pressed={switches[key]}
              onClick={() => toggle(key)} title={`${title}（${switches[key] ? '已开启' : '已关闭'}）`}>
              <Icon size={13} /> {label}
            </button>
          ))}
          <button type="button" className="chip-btn chip-btn--ghost" onClick={() => { setDraft('/'); inputRef.current?.focus() }} title="常用任务">
            <IconSlash size={13} /> 命令
          </button>
          <span className="composer__scope mono-sm">{scopeNote}</span>
          {running ? (
            <button type="button" className="btn btn--dark btn--icon" onClick={onStop} aria-label="停止" title="停止"><IconStop /></button>
          ) : (
            <button type="button" className="btn btn--dark btn--icon" onClick={submit} disabled={!draft.trim() || menuOpen} aria-label="发送" title="发送"><IconSend /></button>
          )}
        </div>
      </div>
    </div>
  )
}
