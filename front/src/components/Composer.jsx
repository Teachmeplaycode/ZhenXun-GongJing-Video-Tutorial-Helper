import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { IconBook, IconClose, IconGlobe, IconImage, IconPlus, IconSend, IconSlash, IconStop } from './Icons'
import { fmtTime, frameNo } from '../lib/format'
import { prefersReducedMotion } from '../lib/motion'

// Input bar in the manner of React Bits' PromptBar, trimmed to what this app uses: a growing text
// field, switches for the tools a question may use, a "/" menu of common tasks, the frames attached
// from the timeline, and send / stop.

export const COMMANDS = [
  { key: '总结', hint: '分点总结视频内容', text: '总结这个视频的主要内容，分 3–5 点，每点注明时间点。' },
  { key: '时间线', hint: '按时间列出关键事件', text: '按时间顺序列出视频里的关键事件和画面变化，每条注明时间点。' },
  { key: '卡点', hint: '软件教程：逐步操作和出错点', text: '按顺序列出视频里的每一步操作：第几秒点了哪个按钮或菜单、输入了什么；哪一步最容易出错，为什么。' },
  { key: '科普核查', hint: '技能：逐条核查视频里的说法', text: '用科普核查技能，逐条核查这个视频里的健康和科学说法。' },
  { key: '反诈识别', hint: '技能：识别诈骗与引流风险', text: '用反诈识别技能，看看这个视频有没有诈骗或引流风险。' },
  { key: '核实', hint: '查资料核实某个说法', text: '核实视频里的主要说法是否正确，请查资料并给出来源链接。' },
  { key: '论文', hint: '找相关的学术论文', text: '找几篇和这个视频主题相关的学术论文，说明它们和视频内容的关系。' },
  { key: '细看', hint: '仔细看某一段画面', text: '仔细看 00:00 到 00:30 这段画面，描述具体发生了什么。' },
  { key: '慢放', hint: '慢放复看几秒钟，看清动作', text: '慢放复看 00:00 到 00:02，一帧一帧看清楚这段动作是怎么发生的。' },
  { key: 'GIF', hint: '截一段做成 GIF 或 MP4（表情包、存片段）', text: '我要这段的 GIF' },
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

const MAX_IMAGES = 4
const STUCK = '我跟着做卡在这一步了，帮我看看我现在在视频的哪一步、哪里不一样、下一步该怎么做？'
// Grey completion after the caret (Tab takes it) only where there is a keyboard and a mouse.
const canComplete = () => typeof window !== 'undefined' && Boolean(window.matchMedia?.('(hover: hover) and (pointer: fine)').matches)

// clip { start, end }: a stretch framed on the timeline, sent with the question (which may then be empty).
// suggestions [{ question }]: small pills above the box, sent with a click (onSuggest).
// onUpload(file) → { id, url }: a picture for the question (button, paste or drop); a question with
//   pictures and no text asks where the person is stuck.
// complete(text, signal) → the rest of the question; hints: questions to complete from without asking.
export default function Composer({ draft, setDraft, running, onSend, onStop, selected, onRemoveFrame, onClearSelection, onPickFrames, scopeNote, clip = null, onClearClip = null,
  suggestions = [], onSuggest = null, onUpload = null, complete = null, hints = [] }) {
  const [switches, setSwitches] = useState(loadSwitches)
  const [active, setActive] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  const menuRef = useRef(null)
  const inputRef = useRef(null)
  const fileRef = useRef(null)
  const [images, setImages] = useState([]) // { key, name, preview, id?, url?, error? }
  const [ghost, setGhost] = useState('') // the predicted rest of the question
  const uploading = images.some((im) => !im.id && !im.error)
  const ready = images.filter((im) => im.id)

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
    if (!complete || !canComplete() || running || /^\//.test(draft) || draft.trim().length < 2 || /\s$/.test(draft)) return undefined
    const known = hints.find((h) => h.length > draft.length && h.startsWith(draft))
    if (known) { setGhost(known.slice(draft.length)); return undefined }
    const ctl = new AbortController()
    const timer = setTimeout(() => {
      complete(draft, ctl.signal).then((rest) => { if (!ctl.signal.aborted && rest) setGhost(rest) }).catch(() => {})
    }, 450)
    return () => { clearTimeout(timer); ctl.abort() }
  }, [draft, running]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () => {
    const q = draft.trim() || (ready.length ? STUCK : '')
    if ((!q && !clip) || running || menuOpen || uploading) return
    onSend(q, { ...switches, images: ready.map(({ id, url }) => ({ id, url })) })
    setImages([])
    setGhost('')
  }

  const onKeyDown = (e) => {
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
      if (e.key === 'Escape') { e.preventDefault(); setDismissed(true); return }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const pills = !draft && !running && onSuggest ? suggestions.slice(0, 4) : []
  return (
    <div className="composer" onDragOver={(e) => { if (onUpload && [...e.dataTransfer.types].includes('Files')) e.preventDefault() }}
      onDrop={(e) => { if (onUpload && e.dataTransfer.files.length) { e.preventDefault(); addFiles(e.dataTransfer.files) } }}>
      {pills.length ? (
        <div className="composer__pills" aria-label="推荐的问题">
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
          {!draft.trim() && ready.length ? <span className="caption muted">不写问题就问「我卡在哪一步、下一步怎么做」</span> : null}
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
        <div className="composer__field">
          {ghost ? (
            <div className="composer__ghost" aria-hidden="true">
              <span className="composer__ghost-typed">{draft}</span><span className="composer__ghost-rest">{ghost}</span><kbd>Tab</kbd>
            </div>
          ) : null}
          <textarea
            ref={inputRef}
            className="composer__input"
            rows={1}
            value={draft}
            placeholder={onUpload ? '问点什么…  可以粘贴或拖入截图；输入 / 选择常用任务，Enter 发送' : '问点什么…  输入 / 选择常用任务，Enter 发送，Shift + Enter 换行'}
            onChange={(e) => { setDraft(e.target.value); setActive(0); setDismissed(false) }}
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
                <IconImage size={13} /> 图片
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
          <button type="button" className="chip-btn chip-btn--ghost" onClick={() => { setDraft('/'); inputRef.current?.focus() }} title="常用任务">
            <IconSlash size={13} /> 命令
          </button>
          <span className="composer__scope mono-sm">{scopeNote}</span>
          {running ? (
            <button type="button" className="btn btn--dark btn--icon" onClick={onStop} aria-label="停止" title="停止"><IconStop /></button>
          ) : (
            <button type="button" className="btn btn--dark btn--icon" onClick={submit} disabled={(!draft.trim() && !clip && !ready.length) || menuOpen || uploading}
              aria-label="发送" title={uploading ? '图片还在上传' : '发送'}><IconSend /></button>
          )}
        </div>
      </div>
    </div>
  )
}
