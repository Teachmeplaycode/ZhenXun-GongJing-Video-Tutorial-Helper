import { mockAgentRun } from './mock'

// When VITE_API_BASE is set the UI talks to the real backend; otherwise it runs on mocks.
const API_BASE = import.meta.env.VITE_API_BASE

// FastAPI errors carry `detail` as text, or as { code, message } (e.g. login_required, quota_exceeded).
const errorText = (body) => body?.message || (typeof body?.detail === 'object' ? body.detail?.message : body?.detail)
const errorCode = (body) => body?.code || (typeof body?.detail === 'object' ? body.detail?.code : undefined)

/**
 * Upload a local video to the backend, which then samples frames and transcribes it like a link.
 * Resolves to the same job snapshot as createLinkJob. XHR, for upload progress.
 */
export function uploadVideo(file, { task = '', sampling = null, onProgress, signal } = {}) {
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
      const err = new Error(errorText(body) || (xhr.status >= 500 ? '分析服务未启动或暂时不可用' : `上传失败（HTTP ${xhr.status}）`))
      err.code = errorCode(body)
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
    if (sampling) form.append('sampling', JSON.stringify(sampling))
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

export async function readEventStream(response, onEvent) {
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
    const err = new Error(errorText(body) || (response.status >= 500 ? '解析服务未启动或暂时不可用' : `请求失败（HTTP ${response.status}）`))
    err.code = errorCode(body)
    throw err
  }
  return body
}

/**
 * Upload pictures (screenshots, a saved image post): the backend makes them an image job — no
 * sampling or speech, the text on each picture read once. Same snapshot as createLinkJob.
 */
export function uploadImages(files, { task = '', onProgress, signal } = {}) {
  return new Promise((resolve, reject) => {
    signal?.throwIfAborted()
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE || ''}/api/images`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let body = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }
      if (xhr.status < 300 && body) return resolve(body)
      return reject(Object.assign(new Error(errorText(body) || `上传失败（HTTP ${xhr.status}）`), { code: errorCode(body) }))
    }
    xhr.onerror = () => reject(new Error('无法连接分析服务，请确认后端已启动'))
    xhr.onabort = () => reject(new DOMException('aborted', 'AbortError'))
    signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    const form = new FormData()
    for (const f of files) form.append('files', f)
    form.append('task', task)
    xhr.send(form)
  })
}

/** Resolve a link and start remote frame sampling. Returns { job_id, video, slots, coverage }. */
export function createLinkJob(url, { task = '', sampling = null, signal } = {}) {
  return linkRequest('/api/link-jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, task, ...(sampling ? { sampling } : {}) }),
    signal,
  })
}

/** Ask the backend to sample the missing frames again. Returns { retrying, since }. */
export function retryLinkJob(jobId, { signal } = {}) {
  return linkRequest(`/api/link-jobs/${jobId}/retry`, { method: 'POST', signal })
}

/** The video's shot changes for the timeline: { status: running | done | failed | unavailable, cuts: [seconds] }. */
export const fetchCuts = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/cuts`, { signal })

/** The video's chapter list: { status, chapters: [{ start, end, title, summary }], message }. */
export const fetchChapters = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/chapters`, { signal })

/** Replay a stretch framed on the timeline, without the model. Returns { manual: 'replay', events } (saved in the session). */
export const manualReplay = (jobId, start, end, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/replay`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ start, end }),
  signal,
})

/** How a cited moment can be looked at again: { state: original | cache | none, label, message } */
export const fetchSource = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/source`, { signal })
/** Delete a kept upload (frames, text and answers stay); resolves to the new source state. */
export const deleteSource = (jobId) => linkRequest(`/api/link-jobs/${jobId}/source`, { method: 'DELETE' })
/** The original video for <video src>: a kept upload, or the platform's MP4 relayed by the backend. */
export const mediaUrl = (jobId) => `${LINK_BASE}/api/link-jobs/${jobId}/media`
/** Questions worth asking about this video: { status: waiting | running | done | failed, questions: [{ question, kind, label, hint }] } */
export const fetchSuggestions = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/suggestions`, { signal })
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

/** The session-note export as a URL: format=md downloads a zip (笔记.md + images/),
 * format=pdf opens a print-styled page (the browser's Print → PDF). `ids` limits the export
 * to those saved message ids; null means the whole conversation, empty is rejected. */
export function exportSessionUrl(id, { format = 'md', ids = null } = {}) {
  const params = new URLSearchParams()
  if (format !== 'md') params.set('format', format)
  if (ids !== null) params.set('ids', ids.join(','))
  const query = params.toString()
  return `${LINK_BASE}/api/sessions/${id}/export${query ? `?${query}` : ''}`
}

/** { ok, platforms, model, public }: `public` is the web demo, where each browser sees only its own
 * sessions and platform logins are closed. */
export const getHealth = () => linkRequest('/api/health')

// ---- Web demo: accounts and daily allowances (backend modules/members.py) ---------------
const postJson = (path, body) => linkRequest(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const signUp = (name, password) => postJson('/api/auth/register', { name, password })
export const signIn = (name, password) => postJson('/api/auth/login', { name, password })
export const signOut = () => postJson('/api/auth/logout', {})
/** Full-page link to sign in with GitHub or Google (the backend redirects back to the app). */
export const oauthUrl = (provider) => `${LINK_BASE}/api/auth/${provider}/start`

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

// ---- Anti-fraud analysis ----------------------------------------------------------------

/**
 * Anti-fraud report for a link job: rule matching, drainage extraction, QR decoding.
 * Returns a report aligned with the #2 fact-check schema (version=1, module=antifraud,
 * claims[].verdict in {safe|suspicious|fraud}, claims[].risk in {high|medium|low}).
 */
export const fetchAntifraudReport = (jobId, { signal } = {}) =>
  linkRequest(`/api/link-jobs/${jobId}/antifraud`, { signal })

// ---- lecture notes (backend modules/notes) -------------------------------------------------------
/** { status: none | running | done | failed, message, progress: { done, total }, note } */
export const getNotes = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/notes`, { signal })
/** Start (or redo) generating the note; resolves to the same shape as getNotes, status running. */
export const generateNotes = (jobId, { kind = 'lecture' } = {}) => linkRequest(`/api/link-jobs/${jobId}/notes`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind }),
})
/** Save the editor's board (blocks and their places); returns { saved: seconds }. */
export const saveNoteBoard = (jobId, board) => linkRequest(`/api/link-jobs/${jobId}/notes/board`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(board),
})
export const notesExportUrl = (jobId) => `${LINK_BASE}/api/link-jobs/${jobId}/notes/export`

/** A picture set's text, picture by picture: { status, items: [{ index, lines }] }. */
export const fetchPictureTexts = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/texts`, { signal })
