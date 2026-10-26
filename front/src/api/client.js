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

/** A link job's snapshot: { job_id, video, running, slots, coverage, transcript, screentext }. */
export const getLinkJob = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}`, { signal })

/** Ask the backend to sample the missing frames again. Returns { retrying, since }. */
export function retryLinkJob(jobId, { signal } = {}) {
  return linkRequest(`/api/link-jobs/${jobId}/retry`, { method: 'POST', signal })
}

/** The video's shot changes for the timeline: { status: running | done | failed | unavailable, cuts: [seconds] }. */
export const fetchCuts = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/cuts`, { signal })

/** The tutorial's step cards: { status: none | running | done | empty, steps: [{ n, time, action, detail, frame }], message }. */
export const getSteps = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/steps`, { signal })
/** Build them (one model call, counted as a question); resolves to the same shape. */
export const buildSteps = (jobId) => linkRequest(`/api/link-jobs/${jobId}/steps`, { method: 'POST' })
/** Comments and danmaku matched to the steps: { status: none | running | done | empty | unavailable, groups: [{ step, stuck, fixes, items }], read, message }. */
export const getStepComments = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/step-comments`, { signal })
/** Read the comment section against the steps (one model call, counted as a question). */
export const buildStepComments = (jobId) => linkRequest(`/api/link-jobs/${jobId}/step-comments`, { method: 'POST' })
/** Videos the platform recommends beside this one (Bilibili): { status, items: [{ url, title, author, duration, views, cover, imported }] }. */
export const getRelated = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/related`, { signal })
/** The 抄作业 node graph (backend modules/recipe.py): { status, trees, version_notes, unsure, tips, layout, editable }. */
export const getRecipe = (jobId) => linkRequest(`/api/link-jobs/${jobId}/recipe`)
/** The 抄作业 graph as a Blender Python script that builds it (backend modules/recipe_script.py). */
export const recipeScriptUrl = (jobId) => `${LINK_BASE}/api/link-jobs/${jobId}/recipe/script`
export async function fetchRecipeScript(jobId) {
  const response = await fetch(recipeScriptUrl(jobId))
  if (!response.ok) throw new Error('脚本生成失败')
  return response.text()
}
/** The person's own Blender through the 帧寻 Bridge add-on (local app only): { available, connected, blender, message }. */
export const blenderStatus = () => linkRequest('/api/blender/status')
export const blenderAddonUrl = () => `${LINK_BASE}/api/blender/addon`
/** Build the graph (one tree, or all) in the open Blender. */
export const applyRecipe = (jobId, tree = null) => linkRequest(`/api/link-jobs/${jobId}/recipe/apply`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tree }),
})
/** 对答案: the person's tree in Blender against the graph → { done, summary, findings: [{ kind, text, node?, from?, to? }] }. */
export const checkRecipe = (jobId, tree) => linkRequest(`/api/link-jobs/${jobId}/recipe/check`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tree }),
})
/** AI 修改: the model edits one tree (and builds each try in the connected Blender) → { summary, changes, problems, checks, preview, recipe }. */
export const reviseRecipe = (jobId, tree, instruction) => linkRequest(`/api/link-jobs/${jobId}/recipe/revise`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tree, instruction }),
})
/** Back to the graph before the last AI 修改. */
export const undoRecipe = (jobId) => linkRequest(`/api/link-jobs/${jobId}/recipe/undo`, { method: 'POST' })
/** Where the nodes were dragged to on the canvas: { tree index: { node id: [x, y] } }. */
export const saveRecipeLayout = (jobId, positions) => linkRequest(`/api/link-jobs/${jobId}/recipe/layout`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ positions }),
})
/** A comparison of 2–3 tutorials built before: { status: none | done | empty, videos, rows: [{ op, cells, note }], summary, message }. */
export const getCompare = (ids, { signal } = {}) => linkRequest(`/api/compare?ids=${ids.join(',')}`, { signal })
/** Align their step cards (steps built first where missing); counted as one question. */
export const buildCompare = (ids) => linkRequest('/api/compare', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }),
})
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

/** A stretch of the original cut out as a GIF (≤30 s) or an MP4 (≤60 s): { blob, name, fps, width, note }.
 *  look: { fps, width, speed, dither: 'bayer' | 'sierra' | 'none', maxMb, crop: 'x,y,w,h' (fractions) } (an MP4 uses speed and crop). */
export async function fetchClip(jobId, start, end, format, look = {}, { signal } = {}) {
  const q = new URLSearchParams({ start: start.toFixed(2), end: end.toFixed(2), format })
  for (const [k, v] of Object.entries({ fps: look.fps, width: look.width, speed: look.speed, dither: look.dither, max_mb: look.maxMb, crop: look.crop })) {
    if (v !== undefined && v !== null) q.set(k, String(v))
  }
  const res = await fetch(`${LINK_BASE}/api/link-jobs/${jobId}/clip?${q}`, { signal })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || '截取失败，请稍后再试')
  }
  const blob = await res.blob()
  const disposition = res.headers.get('content-disposition') || ''
  const name = decodeURIComponent((disposition.match(/filename\*=utf-8''([^;]+)/i) || [])[1] || '') || `帧寻片段.${format}`
  return { blob, name, fps: Number(res.headers.get('x-clip-fps')) || null, width: Number(res.headers.get('x-clip-width')) || null,
    note: decodeURIComponent(res.headers.get('x-clip-note') || '') }
}

/** Save a blob as a file under `name`. */
export function saveBlob(blob, name) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 30000)
}

/** Keep a clip studio card with its session (backend /studio). */
export async function saveStudio(jobId, text, [start, end], format, command = null) {
  const res = await fetch(`${LINK_BASE}/api/link-jobs/${jobId}/studio`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, start, end, format, ...(command ? { command } : {}) }) })
  if (!res.ok) throw new Error('保存截取卡片失败')
}

/** Cut and save in one go (the timeline's range menu). */
export async function downloadClip(jobId, start, end, format) {
  const { blob, name } = await fetchClip(jobId, start, end, format)
  saveBlob(blob, name)
  return name
}
/** Questions worth asking about this video: { status: waiting | running | done | failed, questions: [{ question, kind, label, hint }] } */
export const fetchSuggestions = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/suggestions`, { signal })

/** A picture added to the next question (a screenshot of where one is stuck): { id, url, width, height }. */
export async function uploadAttachment(jobId, file) {
  const form = new FormData()
  form.append('file', file)
  const image = await linkRequest(`/api/link-jobs/${jobId}/attachments`, { method: 'POST', body: form })
  // Sent messages load the stored image, so use the same API base as restored messages.
  return { ...image, url: apiUrl(image.url) }
}

/** The rest of the question being typed, for the composer's grey Tab completion ('' when unsure). */
export const completeQuestion = (jobId, text, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/complete`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }), signal,
}).then((body) => body?.completion || '')
export const linkFrameUrl = (jobId, index) => `${LINK_BASE}/api/link-jobs/${jobId}/frames/${index}.jpg`
/** A step card's picture: its own sharper one when the cards were made with it, else the nearest keyframe. */
export const stepShotUrl = (jobId, step) => (step.shot ? `${LINK_BASE}/api/link-jobs/${jobId}/steps/${step.n}.jpg` : linkFrameUrl(jobId, step.frame))

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

/** Finished tutorials anyone may open on the public site (backend SAMPLE_SESSIONS). */
export const listSamples = () => linkRequest('/api/samples').then((body) => body.samples || []).catch(() => [])

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
/** A one-click guest account (a small daily allowance, kept by this browser only). */
export const startGuest = () => postJson('/api/auth/guest', {})
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
/** The note as one long PNG (a phone keeps it in its photos). */
export const notesImageUrl = (jobId) => `${notesExportUrl(jobId)}?image=1&t=${Date.now()}`

/** A picture set's text, picture by picture: { status, items: [{ index, lines }] }. */
export const fetchPictureTexts = (jobId, { signal } = {}) => linkRequest(`/api/link-jobs/${jobId}/texts`, { signal })
