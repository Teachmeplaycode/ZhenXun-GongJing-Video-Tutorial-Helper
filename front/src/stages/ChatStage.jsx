import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import MessageBubble from '../components/MessageBubble'
import Composer, { loadSwitches } from '../components/Composer'
import ChaptersPanel from '../components/ChaptersPanel'
import { IconArrowDown, IconArrowRight } from '../components/Icons'
import { useAgentChat } from '../api/useAgentChat'
import { fetchSuggestions } from '../api/client'
import SpotlightCard from '../components/react-bits/SpotlightCard'
import AnimatedContent from '../components/react-bits/AnimatedContent'
import { WORKSPACE_CONTENT } from '../config/workspace'
import { prefersReducedMotion } from '../lib/motion'
import { screenStep, speechStep } from './AnalyzeHud'
import Avatar from '../components/Avatar'
import { collectCited, collectExtras } from '../lib/extraFrames'
import Workbench from '../components/Workbench'
import NotesTab from '../components/bench/NotesTab'

const STICK_THRESHOLD = 48 // px from bottom that still counts as "following"
// 114.25 → "01:54.3" (the agent reads tenths; whole seconds stay "01:54")
const fineClock = (t) => {
  const tenths = Math.round(t * 10)
  const m = Math.floor(tenths / 600)
  const s = (tenths - m * 600) / 10
  return `${String(m).padStart(2, '0')}:${s % 1 ? s.toFixed(1).padStart(4, '0') : String(s).padStart(2, '0')}`
}

// onPickFrames: open the timeline so frames can be picked as attachments.
// onExtras: receives the frames replayed or looked at closer in this conversation, for the timeline;
// onCited the times the answers point at; onBusy whether an answer (or a replay) is in progress.
// replayRequest { start, end, key }: a stretch framed on the timeline to replay now, without the model.
// clip { start, end }: a stretch framed on the timeline to ask about; the question asks to replay it first.
export default function ChatStage({ active, video, frames, duration = null, onSeek = null, coverage = null, transcript = null, screentext = null, chapters = null, pictures = false, activeChapter = null, onChapterSelect = null, onChapterHover = null, initialMessages, selected, onClearSelection, onRemoveFrame, onPickFrames, onExtras = null, onCited = null, onBusy = null, replayRequest = null, clip = null, onClearClip = null }) {
  const { messages, send, regenerate, stop, running, replay, cancelReplay } = useAgentChat({ videoId: video?.videoId, frames, coverage, video, initialMessages })
  // The workbench sidebar: open or not and which tab, remembered across visits.
  const [bench, setBench] = useState(() => {
    try {
      return { open: localStorage.getItem('bench.open') === '1', tab: localStorage.getItem('bench.tab') || 'chapters' }
    } catch {
      return { open: false, tab: 'chapters' }
    }
  })
  const setBenchOpen = useCallback((open) => setBench((b) => ({ ...b, open })), [])
  const setBenchTab = useCallback((tab) => setBench((b) => ({ ...b, tab, open: true })), [])
  useEffect(() => {
    try {
      localStorage.setItem('bench.open', bench.open ? '1' : '0')
      localStorage.setItem('bench.tab', bench.tab)
    } catch {
      // private mode: the sidebar still works for this visit
    }
  }, [bench])
  const extras = useMemo(() => collectExtras(messages), [messages])
  const extrasKey = extras.map((g) => `${g.id}:${g.frames.length}`).join('|')
  useEffect(() => {
    onExtras?.(extras)
    // only when a group arrives or grows, not on every streamed token
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extrasKey])
  const cited = useMemo(() => collectCited(messages, duration), [messages, duration])
  const citedKey = cited.map((c) => `${c.time}:${c.n}`).join('|')
  useEffect(() => {
    onCited?.(cited)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citedKey])
  useEffect(() => { onBusy?.(running) }, [running, onBusy])

  // Questions written for this very video (backend modules/suggest.py), once its speech and on-screen
  // text are read; until then, and if they can't be made, the general ones.
  const [tailored, setTailored] = useState([])
  const jobId = video?.jobId
  const fresh = !messages.length
  useEffect(() => {
    if (!jobId || !fresh) return undefined
    let stopped = false
    let timer = null
    const ctl = new AbortController()
    const poll = async (tries) => {
      try {
        const r = await fetchSuggestions(jobId, { signal: ctl.signal })
        if (stopped) return
        if (r.status === 'done') {
          setTailored(r.questions.map((q) => ({ title: q.label, description: q.hint || '为这个视频推荐', question: q.question, tailored: true })))
          return
        }
        if (r.status === 'failed') return
      } catch {
        if (stopped) return
      }
      if (tries > 0) timer = setTimeout(() => poll(tries - 1), 4000)
    }
    poll(60) // about four minutes: long videos read their text for a while
    return () => { stopped = true; clearTimeout(timer); ctl.abort() }
  }, [jobId, fresh])
  // A replay framed before this chat opened belongs to another video (or an earlier visit): ignore it.
  const openedAt = useRef(Date.now())
  useEffect(() => {
    if (!replayRequest || running || replayRequest.key < openedAt.current) return
    followRef.current = true
    setFollowing(true)
    replay(replayRequest.start, replayRequest.end)
    // only a new request replays, not a re-render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replayRequest?.key])
  const [draft, setDraft] = useState('')
  const [following, setFollowing] = useState(true)
  const scrollRef = useRef(null)
  const followRef = useRef(true)
  const jumpRef = useRef(null)

  useEffect(() => {
    if (!active) stop()
  }, [active, stop])

  // Sticky-bottom: follow the stream unless the user scrolled up; then offer a way back.
  const onScroll = () => {
    const el = scrollRef.current
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_THRESHOLD
    followRef.current = near
    setFollowing(near)
  }
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (el && messages.length && followRef.current) el.scrollTop = el.scrollHeight
  }, [messages, active])
  useLayoutEffect(() => {
    if (!following && jumpRef.current && !prefersReducedMotion()) {
      gsap.fromTo(jumpRef.current, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.2, ease: 'power2.out' })
    }
  }, [following])
  const jumpToEnd = () => {
    const el = scrollRef.current
    followRef.current = true
    setFollowing(true)
    el.scrollTo({ top: el.scrollHeight, behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
  }

  useEffect(() => {
    if (video?.task && !messages.length) setDraft(video.task)
    // only seed once with the task typed on the import screen
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const ask = (question, switches) => {
    if ((!question && !clip) || running) return
    followRef.current = true
    setFollowing(true)
    // A framed stretch: say so in the question, which makes the agent replay it before answering.
    const q = clip ? `慢放 ${fineClock(clip.start)} 到 ${fineClock(clip.end)}：${question || '这段发生了什么？'}` : question
    send(q, selected, switches)
    setDraft('')
    onClearSelection()
    onClearClip?.()
  }

  const scopeNote = pictures
    ? `范围：${selected.length ? `已选 ${selected.length} 张` : '全部图片'}${screentext ? ` · 图片文字 ${screenStep(screentext).value || '等待'}` : ''}`
    : `范围：${clip ? `先慢放 ${fineClock(clip.start)}–${fineClock(clip.end)}` : selected.length ? `已选 ${selected.length} 帧` : '整段视频'}${transcript ? ` · 语音 ${speechStep(transcript).value || '等待'}` : ''}${screentext ? ` · 字幕 ${screenStep(screentext).value || '等待'}` : ''}`

  const chapterList = chapters?.status === 'done' ? chapters.chapters || [] : []
  const panels = {
    chapters: <ChaptersPanel data={chapters} onSeek={onSeek} embedded active={activeChapter}
      onSelect={onChapterSelect} onHover={onChapterHover} />,
    notes: <NotesTab video={video} messages={messages} />,
  }

  return (
    <div className="chat-shell" data-bench={bench.open || undefined}>
    <div className="chat">
      <div ref={scrollRef} className="chat__scroll" onScroll={onScroll}>
        <div className="chat__thread">
          {!messages.length ? (
            <AnimatedContent className="chat__empty" distance={12} duration={0.5}>
              <div className="chat__agent">
                <Avatar role="assistant" animated />
                <span className="chat__agent-copy">
                  <strong>帧寻 Agent</strong>
                  <span>视频理解与事实核验</span>
                </span>
              </div>
              {pictures ? null : <div className="eyebrow">03 · 对话分析</div>}
              <h1 className="h1">{pictures ? '关于这组图片，你想知道什么？' : '关于这段视频，你想知道什么？'}</h1>
              <p className="body-sm muted">
                {pictures
                  ? '默认理解全部图片；在左边把某几张「选作附件」，就只针对它们提问。'
                  : '在下方时间轴中点选薄片，可将对应关键帧作为附件带入提问；未选择时默认理解整段视频。输入 / 可以选择常用任务。'}
              </p>
              {tailored.length ? <p className="chat__suggest-label mono-sm">为这个视频推荐的问题</p> : null}
              <div className="chat__suggest">
                {(tailored.length ? tailored : pictures ? WORKSPACE_CONTENT.pictureSuggestions : WORKSPACE_CONTENT.suggestions).map((s) => (
                  <SpotlightCard key={s.question} theme="light" spotlightColor="var(--accent-active)" intensity={0.7} className={`workspace-card chat-task${s.tailored ? ' chat-task--tailored' : ''}`}>
                    <button type="button" onClick={() => ask(s.question, loadSwitches())}>
                      <strong>{s.title}</strong><span className="workspace-card__description">{s.description}</span>
                      <span className="workspace-card__action">{s.question} <IconArrowRight size={14} /></span>
                    </button>
                  </SpotlightCard>
                ))}
              </div>
            </AnimatedContent>
          ) : (
            messages.map((m) => (
              <MessageBubble key={m.id} message={m} onStop={stop} onTime={onSeek} duration={duration} pictures={pictures}
                onRegenerate={m.role === 'assistant' && !running ? () => { followRef.current = true; regenerate(m.id) } : null} />
            ))
          )}
          <div className="chat__anchor" />
        </div>
      </div>
      {!following && messages.length ? (
        <button ref={jumpRef} type="button" className="chat__jump" onClick={jumpToEnd} aria-label="回到底部">
          <IconArrowDown size={14} /> {running ? '回到最新' : '回到底部'}
        </button>
      ) : null}
      <Composer
        draft={draft}
        setDraft={setDraft}
        running={running}
        onSend={ask}
        onStop={stop}
        selected={selected}
        onRemoveFrame={onRemoveFrame}
        onClearSelection={onClearSelection}
        onPickFrames={pictures ? null : onPickFrames}
        clip={clip}
        onClearClip={onClearClip}
        scopeNote={scopeNote}
      />
    </div>
    <Workbench open={bench.open} onOpenChange={setBenchOpen} tab={bench.tab} onTab={setBenchTab} panels={panels} hide={pictures ? ['chapters'] : []}
      badges={{ chapters: chapterList.length || null }} />
    </div>
  )
}
