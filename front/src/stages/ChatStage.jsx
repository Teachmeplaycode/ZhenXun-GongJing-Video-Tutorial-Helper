import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import MessageBubble from '../components/MessageBubble'
import Composer, { loadSwitches } from '../components/Composer'
import { IconArrowDown, IconArrowRight } from '../components/Icons'
import { useAgentChat } from '../api/useAgentChat'
import SpotlightCard from '../components/react-bits/SpotlightCard'
import AnimatedContent from '../components/react-bits/AnimatedContent'
import { WORKSPACE_CONTENT } from '../config/workspace'
import { prefersReducedMotion } from '../lib/motion'
import { screenStep, speechStep } from './AnalyzeHud'
import Avatar from '../components/Avatar'

const STICK_THRESHOLD = 48 // px from bottom that still counts as "following"

// onPickFrames: open the timeline so frames can be picked as attachments.
export default function ChatStage({ active, video, frames, duration = null, onSeek = null, coverage = null, transcript = null, screentext = null, initialMessages, selected, onClearSelection, onRemoveFrame, onPickFrames }) {
  const { messages, send, regenerate, stop, running } = useAgentChat({ videoId: video?.videoId, frames, coverage, video, initialMessages })
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
    if (!question || running) return
    followRef.current = true
    setFollowing(true)
    send(question, selected, switches)
    setDraft('')
    onClearSelection()
  }

  const scopeNote = `范围：${selected.length ? `已选 ${selected.length} 帧` : '整段视频'}${transcript ? ` · 语音 ${speechStep(transcript).value || '等待'}` : ''}${screentext ? ` · 字幕 ${screenStep(screentext).value || '等待'}` : ''}`

  return (
    <div className="chat">
      <div ref={scrollRef} className="chat__scroll" onScroll={onScroll}>
        <div className="chat__thread">
          {!messages.length ? (
            <AnimatedContent className="chat__empty" distance={12} duration={0.5}>
              <div className="chat__agent">
                <Avatar role="assistant" animated />
                <span className="chat__agent-copy">
                  <strong>GongJ!ng Agent</strong>
                  <span>视频理解与事实核验</span>
                </span>
              </div>
              <div className="eyebrow">03 · 对话分析</div>
              <h1 className="h1">关于这段视频，你想知道什么？</h1>
              <p className="body-sm muted">
                在下方时间轴中点选薄片，可将对应关键帧作为附件带入提问；未选择时默认理解整段视频。输入 / 可以选择常用任务。
              </p>
              <div className="chat__suggest">
                {WORKSPACE_CONTENT.suggestions.map((s) => (
                  <SpotlightCard key={s.title} theme="light" spotlightColor="var(--accent-active)" intensity={0.7} className="workspace-card chat-task">
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
              <MessageBubble key={m.id} message={m} onStop={stop} onTime={onSeek} duration={duration}
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
        onPickFrames={onPickFrames}
        scopeNote={scopeNote}
      />
    </div>
  )
}
