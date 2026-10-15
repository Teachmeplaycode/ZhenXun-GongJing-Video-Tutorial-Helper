import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import MessageBubble from '../components/MessageBubble'
import { IconClose, IconSend, IconStop } from '../components/Icons'
import { useAgentChat } from '../api/useAgentChat'
import { fmtTime, frameNo } from '../lib/format'
import SpotlightCard from '../components/react-bits/SpotlightCard'
import AnimatedContent from '../components/react-bits/AnimatedContent'
import { WORKSPACE_CONTENT } from '../config/workspace'
import { IconArrowRight } from '../components/Icons'
import { speechStep } from './AnalyzeHud'

const STICK_THRESHOLD = 48 // px from bottom that still counts as "following"

export default function ChatStage({ active, video, frames, duration = null, onSeek = null, coverage = null, transcript = null, initialMessages, selected, onClearSelection, onRemoveFrame }) {
  const { messages, send, stop, running } = useAgentChat({ videoId: video?.videoId, frames, coverage, video, initialMessages })
  const [draft, setDraft] = useState('')
  const scrollRef = useRef(null)
  const followRef = useRef(true)

  useEffect(() => {
    if (!active) stop()
  }, [active, stop])

  // Sticky-bottom: follow the stream unless the user scrolled up.
  const onScroll = () => {
    const el = scrollRef.current
    followRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_THRESHOLD
  }
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (el && messages.length && followRef.current) el.scrollTop = el.scrollHeight
  }, [messages, active])

  useEffect(() => {
    if (video?.task && !messages.length) setDraft(video.task)
    // only seed once with the task typed on the import screen
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = (text = draft) => {
    const q = text.trim()
    if (!q || running) return
    followRef.current = true
    send(q, selected)
    setDraft('')
    onClearSelection()
  }

  return (
    <div className="chat">
      <div ref={scrollRef} className="chat__scroll" onScroll={onScroll}>
        <div className="chat__thread">
          {!messages.length ? (
            <AnimatedContent className="chat__empty" distance={12} duration={0.5}>
              <div className="eyebrow">03 · 对话分析</div>
              <h1 className="h1">关于这段视频，你想知道什么？</h1>
              <p className="body-sm muted">
                在下方时间轴中点选薄片，可将对应关键帧作为附件带入提问；未选择时默认理解整段视频。
              </p>
              <div className="chat__suggest">
                {WORKSPACE_CONTENT.suggestions.map((s) => (
                  <SpotlightCard key={s.title} theme="light" spotlightColor="var(--accent-active)" intensity={0.7} className="workspace-card chat-task">
                    <button type="button" onClick={() => submit(s.question)}>
                      <strong>{s.title}</strong><span className="workspace-card__description">{s.description}</span>
                      <span className="workspace-card__action">{s.question} <IconArrowRight size={14} /></span>
                    </button>
                  </SpotlightCard>
                ))}
              </div>
              <div className="chat-guide"><span className="chat-guide__number">01</span><span>在时间轴选帧</span><span className="chat-guide__line" /><span className="chat-guide__number">02</span><span>提问或选择任务</span><span className="chat-guide__line" /><span className="chat-guide__number">03</span><span>查看回答与执行记录</span></div>
            </AnimatedContent>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} onStop={stop} onTime={onSeek} duration={duration} />)
          )}
          <div className="chat__anchor" />
        </div>
      </div>

      <div className="composer">
        <div className="composer__scope">
          <span>范围：{selected.length ? `已选 ${selected.length} 帧` : '整段视频'}{transcript ? ` · 语音：${speechStep(transcript).value || '等待'}` : ''}</span>
          {selected.length ? <button type="button" className="link-btn" onClick={onClearSelection}>清除</button> : null}
        </div>
        {selected.length && selected.length <= 5 ? (
          <div className="composer__attach">
            {selected.map((f) => (
              <span key={f.index} className="frame-chip">
                <img src={f.src} alt="" />
                <span className="mono-sm">{frameNo(f.index)} · {fmtTime(f.time)}</span>
                <button type="button" className="icon-btn icon-btn--sm" aria-label="移除" onClick={() => onRemoveFrame(f.index)}><IconClose size={12} /></button>
              </span>
            ))}
          </div>
        ) : null}
        <div className="composer__box">
          <textarea
            className="composer__input"
            rows={1}
            value={draft}
            placeholder="输入问题，Enter 发送，Shift + Enter 换行"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                submit()
              }
            }}
          />
          {running ? (
            <button type="button" className="btn btn--dark btn--icon" onClick={stop} aria-label="停止"><IconStop /></button>
          ) : (
            <button type="button" className="btn btn--dark btn--icon" onClick={() => submit()} disabled={!draft.trim()} aria-label="发送"><IconSend /></button>
          )}
        </div>
      </div>
    </div>
  )
}
