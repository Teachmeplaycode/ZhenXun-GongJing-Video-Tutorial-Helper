import { useCallback, useEffect, useRef, useState } from 'react'
import { manualReplay, streamAgentRun } from './client'

let seq = 0
const nextId = () => `m${(seq += 1)}`

// An answer is a sequence of parts in the order they happened, like Claude or Codex:
//   { kind: 'steps', id, calls: [...], from, to }   consecutive tool calls (`from`/`to`: seconds into the run)
//   { kind: 'text', text }                           answer text
// Text arriving after tool calls opens a new text part; a tool call after text opens a new steps part.
const lastPart = (parts) => parts[parts.length - 1]
const findCall = (parts, id, fn) => parts.map((p) => (p.kind === 'steps' && p.calls.some((c) => c.id === id)
  ? { ...p, calls: p.calls.map((c) => (c.id === id ? fn(c) : c)) }
  : p))
const closeSteps = (parts, t) => parts.map((p) => (p.kind === 'steps' && p.to == null ? { ...p, to: t } : p))

// Fold a §9.2 event into the assistant message it belongs to. `ev.t` is seconds since the question.
export function applyEvent(msg, ev) {
  const parts = msg.parts
  const t = ev.t ?? null
  switch (ev.type) {
    case 'progress.update':
      return { ...msg, progress: { step: ev.step, percent: ev.percent } }
    case 'tool_call.started': {
      const call = { id: ev.call_id, tool: ev.tool_name, status: 'running', started: t }
      const last = lastPart(parts)
      if (last?.kind === 'steps' && last.to == null) {
        return { ...msg, parts: [...parts.slice(0, -1), { ...last, calls: [...last.calls, call] }] }
      }
      return { ...msg, parts: [...parts, { kind: 'steps', id: ev.call_id, calls: [call], from: t, to: null }] }
    }
    case 'tool_call.input':
      return { ...msg, parts: findCall(parts, ev.call_id, (c) => ({ ...c, input: ev.input })) }
    case 'tool_call.output':
      return {
        ...msg,
        parts: findCall(parts, ev.call_id, (c) => ({ ...c, stdout: ev.stdout, stderr: ev.stderr, exitCode: ev.exit_code, data: ev.data })),
      }
    case 'tool_call.completed':
      return {
        ...msg,
        parts: findCall(parts, ev.call_id, (c) => ({
          ...c, status: c.exitCode && c.exitCode !== 0 ? 'error' : 'done', resultCount: ev.result_count, ended: t,
        })),
        browser: msg.browser && msg.browser.callId === ev.call_id ? { ...msg.browser, status: 'done' } : msg.browser,
      }
    case 'file.edit.diff':
      return { ...msg, parts: findCall(parts, ev.call_id, (c) => ({ ...c, diff: { path: ev.path, diff: ev.diff } })) }
    case 'browser.open':
      return { ...msg, browser: { callId: ev.call_id, url: ev.url, status: 'running', actions: [], frame: null } }
    case 'browser.action':
      if (!msg.browser) return msg
      return { ...msg, browser: { ...msg.browser, url: ev.url || msg.browser.url, actions: [...msg.browser.actions, ev] } }
    case 'browser.frame':
      if (!msg.browser) return msg
      return { ...msg, browser: { ...msg.browser, frame: ev.src } }
    case 'assistant.message.delta': {
      const last = lastPart(parts)
      const next = last?.kind === 'text'
        ? [...parts.slice(0, -1), { ...last, text: last.text + ev.delta }]
        : [...closeSteps(parts, t), { kind: 'text', text: ev.delta }]
      return { ...msg, parts: next, text: msg.text + ev.delta }
    }
    case 'run.completed':
      return {
        ...msg, status: 'done', progress: null, parts: closeSteps(parts, t),
        completed: { steps: ev.steps, elapsedMs: ev.elapsed_ms, summary: ev.summary },
      }
    case 'run.error': {
      // A step still running when the run ends was cut off: by the user (stopped) or by the failure.
      const cut = ev.code === 'stopped' ? 'stopped' : 'error'
      const ended = parts.map((p) => (p.kind === 'steps'
        ? { ...p, to: p.to ?? t, calls: p.calls.map((c) => (c.status === 'running' ? { ...c, status: cut } : c)) }
        : p))
      return { ...msg, status: 'error', progress: null, error: ev.message, parts: ended }
    }
    default:
      return msg
  }
}

const emptyAnswer = () => ({ id: nextId(), role: 'assistant', status: 'running', text: '', parts: [], progress: null, browser: null, completed: null })

/** Saved messages from the backend → UI messages; answers replay their stored events in order.
 * `savedId` keeps the backend row id, so the note export can name the turns to include. */
export function restoreMessages(saved, frames) {
  const out = []
  for (const m of saved) {
    if (m.role === 'user') {
      const attachments = (m.frames || []).map((i) => frames.find((f) => f.index === i)).filter(Boolean)
      out.push({ id: nextId(), role: 'user', text: m.content, attachments, savedId: m.id })
      continue
    }
    const events = m.events || []
    let msg = events.reduce(applyEvent, emptyAnswer())
    if (m.content && !events.some((e) => e.type === 'assistant.message.delta')) {
      // Saved before answers kept their text in order: the text goes after the steps.
      msg = applyEvent(msg, { type: 'assistant.message.delta', delta: m.content })
    }
    // manual: a replay framed by hand on the timeline (no model, no question): shown as its own card.
    out.push({ ...msg, text: m.content, progress: null, status: m.status === 'done' ? 'done' : 'error', manual: m.manual || null, savedId: m.id })
  }
  return out
}

// initialMessages: a reopened session's conversation (the component is keyed per session).
export function useAgentChat({ videoId, frames, coverage = null, video = null, initialMessages = [] }) {
  const [messages, setMessages] = useState(initialMessages)
  const controllerRef = useRef(null)
  useEffect(() => () => controllerRef.current?.abort(), [])
  const running = messages.some((m) => m.role === 'assistant' && m.status === 'running')

  // options: { web, papers } — the composer's switches for this question.
  const send = useCallback(async (question, selected, options = {}) => {
    const scope = selected.length ? { type: 'frames', frames: selected.map((f) => f.index) } : { type: 'all' }
    const userMsg = { id: nextId(), role: 'user', text: question, attachments: selected, options }
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
          web: options.web ?? true,
          papers: options.papers ?? true,
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

  // Ask the question behind an answer again, with the same attachments and switches.
  const regenerate = useCallback((answerId) => {
    const i = messages.findIndex((m) => m.id === answerId)
    const question = messages.slice(0, i).reverse().find((m) => m.role === 'user')
    if (question) send(question.text, question.attachments || [], question.options || {})
  }, [messages, send])

  const stop = useCallback(() => controllerRef.current?.abort(), [])

  // A stretch framed on the timeline, replayed without the model; the card shows while it loads.
  const replay = useCallback(async (start, end) => {
    if (!video?.jobId) return
    const id = nextId()
    const base = { ...emptyAnswer(), id, manual: 'replay', range: [start, end] }
    setMessages((list) => [...list, base])
    try {
      const body = await manualReplay(video.jobId, start, end)
      const msg = body.events.reduce(applyEvent, base)
      setMessages((list) => list.map((m) => (m.id === id ? { ...msg, status: 'done' } : m)))
    } catch (err) {
      setMessages((list) => list.map((m) => (m.id === id ? { ...m, status: 'error', error: err.message } : m)))
    }
  }, [video])

  return { messages, send, regenerate, stop, running, replay }
}
