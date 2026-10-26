import React, { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { IconBook, IconClose, IconGlobe, IconImage, IconPlus, IconSend, IconSlash, IconStop } from './Icons'
import { fmtTime, frameNo } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'
import { COMMANDS, commandFor } from '../lib/commands'

// Input bar in the manner of React Bits' PromptBar, trimmed to what this app uses: a growing text
// field, switches for the tools a question may use, a "/" menu of common tasks, the frames attached
// from the timeline, and send / stop.

export { COMMANDS } from '../lib/commands'

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

const MAX_IMAGES = 4
const STUCK = '我跟着做卡在这一步了，帮我看看我现在在视频的哪一步、哪里不一样、下一步该怎么做？'
// Grey completion after the caret (Tab takes it) only where there is a keyboard and a mouse.
const canComplete = () => typeof window !== 'undefined' && Boolean(window.matchMedia?.('(hover: hover) and (pointer: fine)').matches)

function SelectedCommand({ command, onRemove }) {
  const [expanded, setExpanded] = useState(false)
  const id = useId()
  return (
    <section className="composer__command" data-command={command.key} aria-label="已选任务">
      <div className="composer__command-head">
        <span className="command-chip">
          <span className="command-chip__kind">{command.kind === 'skill' ? '技能' : '任务'}</span>
          <strong>/{command.key}</strong>
          <button type="button" className="command-chip__remove" aria-label="移除任务" title={`移除${command.key}`} onClick={onRemove}>
            <IconClose size={13} />
          </button>
        </span>
        <button type="button" className="composer__instruction-toggle" aria-expanded={expanded} aria-controls={id}
          onClick={() => setExpanded((value) => !value)}>{expanded ? '收起指令' : '查看指令'}</button>
      </div>
      {expanded ? <div id={id} className="composer__instruction"><span>内置指令</span><p>{command.text}</p>
        {['细看', '慢放'].includes(command.key) ? <small>补充的时间范围会替代默认范围。</small> : null}
      </div> : null}
    </section>
  )
}

// clip { start, end }: a stretch framed on the timeline, sent with the question (which may then be empty).
// suggestions [{ question }]: small pills above the box, sent with a click (onSuggest).
// stuckPill: lead the pills with one that picks a screenshot ("where am I stuck?"), for tutorials.
// onUpload(file) → { id, url }: a picture for the question (button, paste or drop); a question with
//   pictures and no text asks where the person is stuck.
// complete(text, signal) → the rest of the question; hints: questions to complete from without asking.
export default function Composer({ draft, setDraft, command = null, setCommand, running, onSend, onStop, selected, onRemoveFrame, onClearSelection, onPickFrames, scopeNote, clip = null, onClearClip = null,
  suggestions = [], onSuggest = null, stuckPill = false, onUpload = null, complete = null, hints = [] }) {
  const [switches, setSwitches] = useState(loadSwitches)
  const [active, setActive] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  const [manualMenu, setManualMenu] = useState(false)
  const menuRef = useRef(null)
  const inputRef = useRef(null)
  const fileRef = useRef(null)
  const [images, setImages] = useState([]) // { key, name, preview, id?, url?, error? }
  const [ghost, setGhost] = useState('') // the predicted rest of the question
  const uploading = images.some((im) => !im.id && !im.error)
  const ready = images.filter((im) => im.id)

  const selectedCommand = commandFor(command)
  const slash = /^\/(\S*)$/.exec(draft)
  const query = slash?.[1] || ''
  const matches = useMemo(() => COMMANDS.filter((c) => c.key.includes(query)), [query])
  const menuOpen = (manualMenu || Boolean(slash)) && matches.length > 0 && !dismissed

  useLayoutEffect(() => {
    if (menuOpen && menuRef.current && !prefersReducedMotion()) {
      gsap.fromTo(menuRef.current, { opacity: 0, y: 6, scale: 0.98 }, { opacity: 1, y: 0, scale: 1, duration: 0.16, ease: 'power2.out' })
    }
  }, [menuOpen])
  useLayoutEffect(() => {
    if (menuOpen) menuRef.current?.querySelector('[data-active]')?.scrollIntoView({ block: 'nearest' })
  }, [menuOpen, active, query])

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
    setCommand?.(cmd.key)
    // A pure slash trigger is navigation, while existing user notes stay untouched.
    if (slash) setDraft('')
    setManualMenu(false)
    setDismissed(true)
    setGhost('')
    requestAnimationFrame(() => inputRef.current?.focus())
  }
  const removeCommand = () => {
    setCommand?.(null)
    setManualMenu(false)
    setDismissed(true)
    setGhost('')
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  const addFiles = (files) => {
    if (!onUpload) return
    const pictures = [...files].filter((f) => f.type.startsWith('image/')).slice(0, MAX_IMAGES - images.length)
    for (const file of pictures) {
      const key = `${Date.now()}-${Math.random()}`
      setImages((list) => [...list, { key, name: file.name, preview: URL.createObjectURL(file) }])
      onUpload(file)
        .then(({ id, url }) => setImages((list) => list.map((im) => (im.key === key ? { ...im, id, url } : im))))
        .catch((err) => setImages((list) => list.map((im) => (im.key === key ? { ...im, error: err.message || '上传失败' } : im))))
    }
  }
  const removeImage = (key) => setImages((list) => list.filter((im) => im.key !== key))
  const onPaste = (e) => {
    const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith('image/'))
    if (files.length && onUpload) { e.preventDefault(); addFiles(files) }
  }

  // Tab completion: a question the app already knows that starts with what's typed, else the model.
  useEffect(() => {
    setGhost('')
    if (selectedCommand || menuOpen || !complete || !canComplete() || running || /^\//.test(draft) || draft.trim().length < 2 || /\s$/.test(draft)) return undefined
    const known = hints.find((h) => h.length > draft.length && h.startsWith(draft))
    if (known) { setGhost(known.slice(draft.length)); return undefined }
    const ctl = new AbortController()
    const timer = setTimeout(() => {
      complete(draft, ctl.signal).then((rest) => { if (!ctl.signal.aborted && rest) setGhost(rest) }).catch(() => {})
    }, 450)
    return () => { clearTimeout(timer); ctl.abort() }
  }, [draft, running, selectedCommand?.key, menuOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () => {
    const q = draft.trim() || (!selectedCommand && ready.length ? STUCK : '')
    if ((!q && !clip && !selectedCommand) || running || menuOpen || uploading) return
    const accepted = onSend(q, { ...switches, ...(selectedCommand ? { command: selectedCommand.key } : {}), images: ready.map(({ id, url }) => ({ id, url })) })
    if (accepted === false) return
    setImages([])
    setGhost('')
  }

  const onKeyDown = (e) => {
    if (e.nativeEvent.isComposing || e.isComposing || e.keyCode === 229) return
    if (e.key === 'Backspace' && !draft && selectedCommand && !menuOpen) {
      e.preventDefault()
      removeCommand()
      return
    }
    const atEnd = inputRef.current && inputRef.current.selectionStart === draft.length
    if (ghost && e.key === 'Tab' && !e.shiftKey && atEnd && !menuOpen) {
      e.preventDefault()
      setDraft(draft + ghost)
      setGhost('')
      return
    }
    if (ghost && e.key === 'Escape') { setGhost(''); return }
    if (menuOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % matches.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + matches.length) % matches.length); return }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); pick(matches[Math.min(active, matches.length - 1)]); return }
      if (e.key === 'Escape') { e.preventDefault(); setDismissed(true); setManualMenu(false); return }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const pills = !selectedCommand && !draft && !running && onSuggest ? suggestions.slice(0, 4) : []
  const stuck = !selectedCommand && stuckPill && onUpload && !draft && !running && !images.length
  return (
    <div className="composer" onDragOver={(e) => { if (onUpload && [...e.dataTransfer.types].includes('Files')) e.preventDefault() }}
      onDrop={(e) => { if (onUpload && e.dataTransfer.files.length) { e.preventDefault(); addFiles(e.dataTransfer.files) } }}>
      {pills.length || stuck ? (
        <div className="composer__pills" aria-label="推荐的问题">
          {stuck ? (
            <button type="button" className="composer__pill composer__pill--stuck" onClick={() => fileRef.current?.click()}
              title="附上你屏幕卡住时的截图，直接发送就问卡在哪一步">
              <IconImage size={13} /> 卡住了？发截图问在第几步
            </button>
          ) : null}
          {pills.map((s) => (
            <button key={s.question} type="button" className="composer__pill" onClick={() => onSuggest(s.question)} title="点一下直接问">
              {s.question}
            </button>
          ))}
        </div>
      ) : null}
      {images.length ? (
        <div className="composer__attach">
          {images.map((im, i) => (
            <span key={im.key} className="frame-chip image-chip" data-state={im.error ? 'error' : im.id ? 'ready' : 'uploading'}>
              <img src={im.preview} alt="" />
              <span className="mono-sm">{im.error ? im.error : im.id ? `你的截图 ${i + 1}` : '上传中…'}</span>
              <button type="button" className="icon-btn icon-btn--sm" aria-label="移除图片" onClick={() => removeImage(im.key)}><IconClose size={12} /></button>
            </span>
          ))}
          {!selectedCommand && !draft.trim() && ready.length ? <span className="caption muted">不写问题就问「我卡在哪一步、下一步怎么做」</span> : null}
        </div>
      ) : null}
      {clip ? (
        <div className="composer__attach">
          <span className="frame-chip clip-chip">
            <span className="clip-chip__tag">慢放</span>
            <span className="mono-sm">{fmtTime(clip.start)} – {fmtTime(clip.end)}</span>
            <button type="button" className="icon-btn icon-btn--sm" aria-label="移除慢放区间" onClick={onClearClip}><IconClose size={12} /></button>
          </span>
          <span className="caption muted">发送时先慢放这一段再回答；不写问题就问"这段发生了什么"</span>
        </div>
      ) : null}
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
          <ul ref={menuRef} id="composer-task-menu" className="slash-menu" role="listbox" aria-label="常用任务">
            {matches.map((c, i) => (
              <li key={c.key} role="option" aria-selected={i === active}>
                <button type="button" className="slash-menu__item" data-active={i === active || undefined}
                  onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(c)}>
                  <span className="slash-menu__key mono-sm">/{c.key}</span>
                  <span className="slash-menu__hint">{c.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {selectedCommand ? <SelectedCommand key={selectedCommand.key} command={selectedCommand} onRemove={removeCommand} /> : null}
        <div className="composer__field">
          {ghost && !selectedCommand ? (
            <div className="composer__ghost" aria-hidden="true">
              <span className="composer__ghost-typed">{draft}</span><span className="composer__ghost-rest">{ghost}</span><kbd>Tab</kbd>
            </div>
          ) : null}
          <textarea
            ref={inputRef}
            className="composer__input"
            rows={1}
            value={draft}
            placeholder={selectedCommand ? '补充你关注的问题（可选），直接发送也可以' : onUpload ? '问点什么…  可以粘贴或拖入截图；输入 / 选择常用任务，Enter 发送' : '问点什么…  输入 / 选择常用任务，Enter 发送，Shift + Enter 换行'}
            onChange={(e) => { setDraft(e.target.value); setActive(0); setDismissed(false); setManualMenu(false) }}
            onKeyDown={onKeyDown}
            onPaste={onPaste}
          />
        </div>
        <div className="composer__bar">
          {onPickFrames ? (
            <button type="button" className="chip-btn" onClick={onPickFrames} title="在时间轴上点选关键帧作为附件">
              <IconPlus size={13} /> 选帧
            </button>
          ) : null}
          {onUpload ? (
            <>
              <button type="button" className="chip-btn" onClick={() => fileRef.current?.click()} disabled={images.length >= MAX_IMAGES}
                title="附上图片，比如你屏幕卡住时的截图（最多 4 张；也可以直接粘贴或拖进来）">
                <IconImage size={13} /> 截图
              </button>
              <input ref={fileRef} type="file" accept="image/*" multiple hidden
                onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
            </>
          ) : null}
          {SWITCHES.map(({ key, label, Icon, title }) => (
            <button key={key} type="button" className="chip-btn" data-on={switches[key] || undefined} aria-pressed={switches[key]}
              onClick={() => toggle(key)} title={`${title}（${switches[key] ? '已开启' : '已关闭'}）`}>
              <Icon size={13} /> {label}
            </button>
          ))}
          <button type="button" className="chip-btn chip-btn--ghost" aria-label="常用任务" aria-expanded={menuOpen} aria-controls="composer-task-menu"
            onClick={() => { setManualMenu(!menuOpen); setDismissed(menuOpen); setActive(0); setGhost(''); inputRef.current?.focus() }} title="常用任务">
            <IconSlash size={13} /> 命令
          </button>
          <span className="composer__scope mono-sm">{scopeNote}</span>
          {running ? (
            <button type="button" className="btn btn--dark btn--icon" onClick={onStop} aria-label="停止" title="停止"><IconStop /></button>
          ) : (
            <button type="button" className="btn btn--dark btn--icon" onClick={submit} disabled={(!draft.trim() && !clip && !ready.length && !selectedCommand) || menuOpen || uploading}
              aria-label="发送" title={uploading ? '图片还在上传' : '发送'}><IconSend /></button>
          )}
        </div>
      </div>
    </div>
  )
}
