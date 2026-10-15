import { useCallback, useEffect, useRef, useState } from 'react'
import { streamAgentRun } from './client'

let seq = 0
const nextId = () => `m${(seq += 1)}`

// Fold a §9.2 event into the assistant message it belongs to.
export function applyEvent(msg, ev) {
  const calls = msg.calls
  const patchCall = (id, fn) => calls.map((c) => (c.id === id ? fn(c) : c))
  switch (ev.type) {
    case 'progress.update':
      return { ...msg, progress: { step: ev.step, percent: ev.percent } }
    case 'tool_call.started':
      return { ...msg, calls: [...calls, { id: ev.call_id, tool: ev.tool_name, status: 'running' }] }
    case 'tool_call.input':
      return { ...msg, calls: patchCall(ev.call_id, (c) => ({ ...c, input: ev.input })) }
    case 'tool_call.output':
      return {
        ...msg,
        calls: patchCall(ev.call_id, (c) => ({ ...c, stdout: ev.stdout, stderr: ev.stderr, exitCode: ev.exit_code })),
      }
    case 'tool_call.completed':
      return {
        ...msg,
        calls: patchCall(ev.call_id, (c) => ({ ...c, status: c.exitCode && c.exitCode !== 0 ? 'error' : 'done', resultCount: ev.result_count })),
        browser: msg.browser && msg.browser.callId === ev.call_id ? { ...msg.browser, status: 'done' } : msg.browser,
      }
    case 'file.edit.diff':
      return { ...msg, calls: patchCall(ev.call_id, (c) => ({ ...c, diff: { path: ev.path, diff: ev.diff } })) }
    case 'browser.open':
      return { ...msg, browser: { callId: ev.call_id, url: ev.url, status: 'running', actions: [], frame: null } }
    case 'browser.action':
      return { ...msg, browser: { ...msg.browser, url: ev.url || msg.browser.url, actions: [...msg.browser.actions, ev] } }
    case 'browser.frame':
      return { ...msg, browser: { ...msg.browser, frame: ev.src } }
    case 'assistant.message.delta':
      return { ...msg, text: msg.text + ev.delta }
    case 'run.completed':
      return { ...msg, status: 'done', progress: null, completed: { steps: ev.steps, elapsedMs: ev.elapsed_ms, summary: ev.summary } }
    case 'run.error':
      // A step still running when the run ends was cut off: by the user (stopped) or by the failure.
      return { ...msg, status: 'error', progress: null, error: ev.message, calls: calls.map((c) => (c.status === 'running' ? { ...c, status: ev.code === 'stopped' ? 'stopped' : 'error' } : c)) }
    default:
      return msg
  }
}

// coverage: link jobs report which time ranges have no frames, so answers can say so.
const emptyAnswer = () => ({ id: nextId(), role: 'assistant', status: 'running', text: '', calls: [], progress: null, browser: null, completed: null })

/** Saved messages from the backend → UI messages; answers replay their stored events to rebuild the trace. */
export function restoreMessages(saved, frames) {
  return saved.map((m) => {
    if (m.role === 'user') {
      const attachments = (m.frames || []).map((i) => frames.find((f) => f.index === i)).filter(Boolean)
      return { id: nextId(), role: 'user', text: m.content, attachments }
    }
    const msg = (m.events || []).reduce(applyEvent, emptyAnswer())
    return { ...msg, text: m.content, progress: null, status: m.status === 'done' ? 'done' : 'error' }
  })
}

// initialMessages: a reopened session's conversation (the component is keyed per session).
export function useAgentChat({ videoId, frames, coverage = null, video = null, initialMessages = [] }) {
  const [messages, setMessages] = useState(initialMessages)
  const controllerRef = useRef(null)
  useEffect(() => () => controllerRef.current?.abort(), [])
  const running = messages.some((m) => m.role === 'assistant' && m.status === 'running')

  const send = useCallback(async (question, selected) => {
    const scope = selected.length ? { type: 'frames', frames: selected.map((f) => f.index) } : { type: 'all' }
    const userMsg = { id: nextId(), role: 'user', text: question, attachments: selected }
    const aiId = nextId()
    const aiMsg = { ...emptyAnswer(), id: aiId }
    setMessages((list) => [...list, userMsg, aiMsg])
    const controller = new AbortController()
    controllerRef.current = controller
    const update = (fn) => setMessages((list) => list.map((m) => (m.id === aiId ? fn(m) : m)))
    try {
      await streamAgentRun(
        {
          video_id: videoId,
          link: Boolean(video?.jobId),
          question,
          scope,
          // Only frames that actually arrived; placeholders and gaps are described by `coverage`.
          frames: (selected.length ? selected : frames.filter((f) => f.src && (!f.status || f.status === 'ok'))).map(({ index, time }) => ({ index, time })),
          coverage: coverage && { ok: coverage.ok, total: coverage.total, missing_ranges: coverage.missing_ranges },
          video: video?.title ? { title: video.title, description: video.description || '' } : undefined,
        },
        (ev) => update((m) => applyEvent(m, ev)),
        controller.signal,
      )
    } catch (err) {
      const stopped = err.name === 'AbortError'
      update((m) => applyEvent(m, { type: 'run.error', code: stopped ? 'stopped' : 'client', message: stopped ? '已停止' : err.message }))
    }
  }, [videoId, frames, coverage, video])

  const stop = useCallback(() => controllerRef.current?.abort(), [])

  return { messages, send, stop, running }
}
