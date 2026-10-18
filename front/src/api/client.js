import { mockAgentRun } from './mock'

// When VITE_API_BASE is set the UI talks to the real backend; otherwise it runs on mocks.
const API_BASE = import.meta.env.VITE_API_BASE

/**
 * Upload a local video to the backend, which then samples frames and transcribes it like a link.
 * Resolves to the same job snapshot as createLinkJob. XHR, for upload progress.
 */
export function uploadVideo(file, { task = '', onProgress, signal } = {}) {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted()
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE || ''}/api/videos`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let body = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }
      if (xhr.status < 300 && body) return resolve(body)
      const err = new Error(body?.message || body?.detail || (xhr.status >= 500 ? '分析服务未启动或暂时不可用' : `上传失败（HTTP ${xhr.status}）`))
      err.code = body?.code
      return reject(err)
    }
    xhr.onerror = () => reject(new Error('无法连接分析服务，请确认后端已启动'))
    xhr.onabort = () => reject(new DOMException('aborted', 'AbortError'))
    const onAbort = () => xhr.abort()
    xhr.onloadend = () => signal?.removeEventListener('abort', onAbort)
    signal?.addEventListener('abort', onAbort, { once: true })
    const form = new FormData()
    form.append('file', file)
    form.append('task', task)
    xhr.send(form)
  })
}

/**
 * Start an agent run and stream §9.2 events to onEvent.
 * Event shape: { type, run_id, call_id?, ...payload }
 */
export async function streamAgentRun(request, onEvent, signal) {
  // Link jobs keep their frames on the backend, so they always use the real model there.
  if (!API_BASE && !request.link) return mockAgentRun(request, onEvent, signal)
  let response
  try {
    response = await fetch(`${API_BASE || ''}/api/agent/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(request),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('无法连接分析服务，请确认后端已启动')
  }
  if (!response.ok || !response.body) throw new Error(`分析服务请求失败（HTTP ${response.status}）`)
  await readEventStream(response, onEvent)
}

async function readEventStream(response, onEvent) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let sep
    while ((sep = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const data = chunk.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n')
      if (data) onEvent(JSON.parse(data))
    }
  }
}

// ---- Video links ------------------------------------------------------------------------
// Links always need the backend (it resolves the platform and samples frames remotely).
// In development Vite proxies /api to it, so an empty base works.
const LINK_BASE = API_BASE || ''
/** A backend path (e.g. a replay frame) as a URL the page can load. */
export const apiUrl = (path) => `${LINK_BASE}${path}`
const LINK_RE = /https?:\/\/\S+|\bBV[0-9A-Za-z]{10}\b|(?<![0-9A-Za-z])av\d+\b/i

/** True when the pasted text contains something the backend can resolve. */
export const looksLikeLink = (text) => LINK_RE.test(text || '')

/** Best-effort platform name for a pasted link, for friendlier import hints (YouTube/抖音 now resolved by the backend). */
export function platformOf(text) {
  const t = String(text || '')
  if (/\bBV[0-9A-Za-z]{10}\b/.test(t) || /(^|\s)av\d+\b/i.test(t) || /bilibili\.com|b23\.tv/i.test(t)) return 'bilibili'
  if (/youtube\.com|youtu\.be/i.test(t)) return 'youtube'
  if (/douyin\.com|iesdouyin\.com/i.test(t)) return 'douyin'
  if (/weixin\.qq\.com|channels\.weixin\.qq\.com/i.test(t)) return 'wechat_channels'
  return ''
}

async function linkRequest(path, init = {}) {
  let response
  try {
    response = await fetch(`${LINK_BASE}${path}`, init)
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('无法连接解析服务，请确认后端已启动')
  }
  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) {
    const err = new Error(body?.message || body?.detail || (response.status >= 500 ? '解析服务未启动或暂时不可用' : `请求失败（HTTP ${response.status}）`))
    err.code = body?.code
    throw err
  }
  return body
}

/** Resolve a link and start remote frame sampling. Returns { job_id, video, slots, coverage }. */
export function createLinkJob(url, { task = '', signal } = {}) {
  return linkRequest('/api/link-jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, task }),
    signal,
  })
}

/** Ask the backend to sample the missing frames again. Returns { retrying, since }. */
export function retryLinkJob(jobId, { signal } = {}) {
  return linkRequest(`/api/link-jobs/${jobId}/retry`, { method: 'POST', signal })
}

/** The video's shot changes for the timeline: { status: running | done | failed | unavailable, cuts: [seconds] }. */
export const fetchCuts = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/cuts`, { signal })

/** Replay a stretch framed on the timeline, without the model. Returns { manual: 'replay', events } (saved in the session). */
export const manualReplay = (jobId, start, end) => linkRequest(`/api/link-jobs/${jobId}/replay`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ start, end }),
})

export const linkFrameUrl = (jobId, index) => `${LINK_BASE}/api/link-jobs/${jobId}/frames/${index}.jpg`

/** Follow a job's events (frame / missing / status / done) from `since` until its run is done. */
export async function streamLinkJob(jobId, since, onEvent, signal) {
  let response
  try {
    response = await fetch(`${LINK_BASE}/api/link-jobs/${jobId}/events?since=${since}`, { headers: { Accept: 'text/event-stream' }, signal })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error('与解析服务的连接中断')
  }
  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)
  await readEventStream(response, onEvent)
}

// ---- Saved sessions (one per link job, kept in the backend's SQLite) -------------------

/** Most recently used first: [{ id, title, author, video_id, duration, frames_ok, frames_total, cover_index, questions, last_question, updated }] */
export const listSessions = ({ signal } = {}) => linkRequest('/api/sessions', { signal }).then((body) => body.sessions)

/** Job snapshot (video, slots, coverage, running, seq) plus { task, messages }. */
export const getSession = (id, { signal } = {}) => linkRequest(`/api/sessions/${id}`, { signal })

export const deleteSession = (id) => linkRequest(`/api/sessions/${id}`, { method: 'DELETE' })

// ---- Platform logins (cookies stay in the backend; only status comes back) -------------

/** [{ id, label, purpose, app, configured, source, user, expires, valid }] */
export const listAccounts = () => linkRequest('/api/accounts').then((body) => body.accounts)

/** Start a QR login: { id, qr (data URL), state, message, expires_in }. */
export const startLogin = (platform) => linkRequest(`/api/accounts/${platform}/login`, { method: 'POST' })

/** { state: waiting | scanned | done | expired | error, message, user, account? } */
export const pollLogin = (id) => linkRequest(`/api/accounts/login/${id}`)

export const cancelLogin = (id) => linkRequest(`/api/accounts/login/${id}`, { method: 'DELETE' }).catch(() => null)

export const pasteCookie = (platform, cookie) => linkRequest(`/api/accounts/${platform}`, {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ cookie }),
})

export const logoutAccount = (platform) => linkRequest(`/api/accounts/${platform}`, { method: 'DELETE' })
