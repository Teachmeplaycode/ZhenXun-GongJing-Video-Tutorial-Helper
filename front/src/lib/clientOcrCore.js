// Task leases coordinate browser OCR with the server; they never change the user's selected mode.
export function ocrUrl(path, base = '') {
  const prefix = base.replace(/\/$/, '')
  if (/^https?:\/\//.test(path)) return path
  return prefix && path.startsWith(`${prefix}/`) ? path : `${prefix}/${path.replace(/^\//, '')}`
}

const aborted = () => new DOMException('aborted', 'AbortError')
const delay = (ms, signal) => new Promise((resolve, reject) => {
  if (signal?.aborted) return reject(aborted())
  const stop = () => { clearTimeout(timer); reject(aborted()) }
  const timer = setTimeout(() => { signal?.removeEventListener('abort', stop); resolve() }, ms)
  signal?.addEventListener('abort', stop, { once: true })
})

export class OcrWorkerPool {
  constructor(factory, { idleMs = 30_000 } = {}) {
    this.factory = factory
    this.idleMs = idleMs
    this.queue = []
    this.sequence = 0
  }
  run(type, payload, signal, timeout = 60_000) {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) return reject(aborted())
      const task = { id: ++this.sequence, type, payload, signal, resolve, reject, timeout }
      task.abort = () => {
        if (this.active === task) this.finish(task, aborted(), true)
        else {
          this.queue = this.queue.filter((item) => item !== task)
          signal?.removeEventListener('abort', task.abort)
          reject(aborted())
        }
      }
      signal?.addEventListener('abort', task.abort, { once: true })
      this.queue.push(task)
      this.pump()
    })
  }
  pump() {
    if (this.active || !this.queue.length) return
    clearTimeout(this.idle)
    const task = this.queue.shift()
    if (task.signal?.aborted) { task.abort(); this.pump(); return }
    this.active = task
    try {
      if (!this.worker) {
        this.worker = this.factory()
        this.worker.onmessage = ({ data }) => {
          if (!this.active || data.id !== this.active.id) return
          this.finish(this.active, data.error ? new Error(data.error) : null, false, data)
        }
        this.worker.onerror = () => this.active && this.finish(this.active, new Error('本机 OCR 模块运行失败'), true)
        this.worker.onmessageerror = () => this.active && this.finish(this.active, new Error('本机 OCR 返回数据异常'), true)
      }
      task.timer = setTimeout(() => this.finish(task, new Error('本机 OCR 处理超时'), true), task.timeout)
      this.worker.postMessage({ id: task.id, type: task.type, ...task.payload }, task.payload.buffer ? [task.payload.buffer] : [])
    } catch (error) { this.finish(task, error, true) }
  }
  finish(task, error, reset, result) {
    if (this.active !== task) return
    clearTimeout(task.timer)
    task.signal?.removeEventListener('abort', task.abort)
    this.active = null
    if (reset) { this.worker?.terminate(); this.worker = null }
    if (error) task.reject(error)
    else task.resolve(result)
    this.pump()
    if (!this.active && !this.queue.length) this.idle = setTimeout(() => { this.worker?.terminate(); this.worker = null }, this.idleMs)
  }
  close() {
    const queued = this.queue.splice(0)
    if (this.active) this.finish(this.active, aborted(), true)
    for (const task of queued) { task.signal?.removeEventListener('abort', task.abort); task.reject(aborted()) }
    clearTimeout(this.idle)
    this.worker?.terminate()
    this.worker = null
  }
}

export function createClientOcrManager({ workerFactory, apiBase = '', assetBase, fetch: fetcher = globalThis.fetch,
  supported = () => typeof Worker !== 'undefined' && typeof WebAssembly !== 'undefined' && typeof OffscreenCanvas !== 'undefined',
  hidden = () => typeof document !== 'undefined' && document.hidden,
  events = typeof window === 'undefined' ? null : window,
  visibility = typeof document === 'undefined' ? null : document,
  workerTimeout = 60_000, slowMs = 6000, pollMs = 1000, idleMs = 30_000, requestTimeout = 15_000 } = {}) {
  const sessions = new Map()
  const pool = new OcrWorkerPool(workerFactory, { idleMs })
  const id = () => globalThis.crypto?.randomUUID?.() || `ocr-${Date.now()}-${Math.random().toString(16).slice(2)}`
  const notify = (session, status) => {
    session.status = status
    for (const callback of session.listeners) { try { callback?.(status) } catch { /* a UI callback cannot break processing */ } }
  }
  async function request(job, route, body, signal, { keepalive = false } = {}) {
    const controller = new AbortController()
    const abort = () => controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) controller.abort()
    const timer = setTimeout(abort, requestTimeout)
    let response
    try {
      response = await fetcher(ocrUrl(`/api/link-jobs/${encodeURIComponent(job)}/ocr/${route}`, apiBase), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify(body), signal: controller.signal, keepalive,
      })
    } catch (error) {
      if (controller.signal.aborted && !signal?.aborted) throw new Error('本机处理连接超时')
      throw error
    } finally {
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
    }
    let value
    try { value = await response.json() } catch { value = {} }
    if (!response.ok) {
      const error = new Error(typeof value.detail === 'string' ? value.detail : `本机处理请求失败（${response.status}）`)
      error.status = response.status
      throw error
    }
    return value
  }
  async function release(session, reason) {
    const lease = session.lease
    session.lease = null
    try { await request(session.job, 'release', { client_id: session.client, ...(lease ? { lease_id: lease } : {}), reason }, undefined, { keepalive: true }) }
    catch { /* a disconnected client is recovered by the server's finite lease timeout */ }
  }
  async function run(session) {
    const signal = session.controller.signal
    const generation = session.generation || 0
    const current = () => generation === (session.generation || 0)
    const report = (phase, message, extra = {}) => { if (current()) notify(session, { phase, message, mode: session.mode, ...extra }) }
    let reason = 'aborted'
    try {
      if (!supported()) { reason = 'unsupported'; throw new Error('此浏览器不支持本机文字识别') }
      report('loading', '正在准备本机文字识别，首次使用需下载模型')
      await pool.run('init', { base: assetBase }, signal, workerTimeout)
      while (!signal.aborted) {
        if (hidden()) { report('paused', '页面进入后台，本机识别已暂停'); await delay(pollMs, signal); continue }
        const claim = await request(session.job, 'claim', { client_id: session.client }, signal)
        session.mode = claim.mode || session.mode
        if (claim.state === 'done' || claim.mode === 'server') { report('done', claim.message || '画面文字处理完成', { progress: claim.progress }); return }
        if (claim.state === 'unavailable') { reason = 'unavailable'; report('paused', claim.message || '本机处理当前不可用', { progress: claim.progress }); return }
        if (claim.state !== 'ready' || !claim.lease_id || !claim.frames?.length) {
          report('waiting', '正在等待可识别画面', { progress: claim.progress }); await delay(pollMs, signal); continue
        }
        session.lease = claim.lease_id
        const leaseController = new AbortController()
        session.processing = leaseController
        const onAbort = () => leaseController.abort()
        const onHidden = () => { if (hidden()) leaseController.abort() }
        signal.addEventListener('abort', onAbort, { once: true })
        visibility?.addEventListener('visibilitychange', onHidden)
        const leaseSignal = leaseController.signal
        let lost = false
        const heartbeat = setInterval(() => {
          request(session.job, 'heartbeat', { client_id: session.client, lease_id: claim.lease_id }, leaseSignal)
            .catch((error) => { if (error.status === 409) { lost = true; leaseController.abort() } })
        }, Math.min(8000, Math.max(1000, (claim.lease_seconds || 20) * 350)))
        let elapsed = 0
        try {
          const results = []
          for (const frame of claim.frames) {
            report('working', session.mode === 'hybrid' ? '本机与服务器正在协同识别文字' : '正在使用本机识别文字', { progress: claim.progress })
            const frameUrl = ocrUrl(frame.url, apiBase)
            const allowed = new URL(apiBase || '/', globalThis.location?.href || 'http://localhost').origin
            if (new URL(frameUrl, globalThis.location?.href || 'http://localhost').origin !== allowed) throw new Error('识别画面地址不属于当前服务')
            const response = await fetcher(frameUrl, { signal: leaseSignal, credentials: 'same-origin' })
            if (!response.ok) { const error = new Error('识别画面读取失败'); error.status = response.status; throw error }
            const buffer = await response.arrayBuffer()
            const output = await pool.run('detect', { buffer, base: assetBase }, leaseSignal, workerTimeout)
            elapsed += output.elapsed || 0
            results.push({ id: frame.id, lines: output.result })
          }
          // A network retry resends the same lease/results rather than repeating OCR.
          for (let attempt = 0; ; attempt++) {
            try {
              const result = await request(session.job, 'result', { client_id: session.client, lease_id: claim.lease_id, results }, leaseSignal)
              session.lease = null
              report('working', session.mode === 'hybrid' ? '本机与服务器正在协同识别文字' : '正在使用本机识别文字', { progress: result.progress })
              break
            } catch (error) {
              if (error.status === 409 || attempt >= 2 || leaseSignal.aborted) throw error
              await delay(500 * (attempt + 1), leaseSignal)
            }
          }
          if (session.mode === 'hybrid' && elapsed / claim.frames.length > slowMs) {
            reason = 'too_slow'
            report('paused', '本机识别较慢，服务器将继续处理')
            return
          }
        } catch (error) {
          if (signal.aborted) throw error
          await release(session, lost ? 'expired' : hidden() ? 'hidden' : 'model_error')
          if (lost || error.status === 409 || hidden()) continue
          throw error
        } finally {
          clearInterval(heartbeat)
          signal.removeEventListener('abort', onAbort)
          visibility?.removeEventListener('visibilitychange', onHidden)
          session.processing = null
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        reason = reason === 'unsupported' ? reason : 'model_error'
        report(session.mode === 'hybrid' ? 'paused' : 'error', session.mode === 'hybrid'
          ? `${error.message}，服务器将继续处理` : `${error.message}；可重试或选择服务器处理`)
      }
    } finally {
      if (current()) {
        if (reason !== 'unavailable' && session.status?.phase !== 'done') await release(session, reason)
        if (current()) session.finished = true
      }
    }
  }
  const stopAll = () => {
    for (const session of sessions.values()) { session.controller.abort(); void release(session, 'aborted') }
    pool.close()
  }
  const onPageHide = (event) => {
    if (!event.persisted) { stopAll(); return }
    // Safari restores BFCache pages without remounting React. Keep subscribers and resume on pageshow.
    for (const session of sessions.values()) {
      if (session.finished || session.status?.phase === 'done') continue
      session.suspended = true
      session.generation = (session.generation || 0) + 1
      session.controller.abort()
      void release(session, 'hidden')
      notify(session, { phase: 'paused', mode: session.mode, message: '页面已暂停，返回后继续本机识别' })
    }
    pool.close()
  }
  const onPageShow = (event) => {
    if (!event.persisted) return
    for (const session of sessions.values()) {
      if (!session.suspended || !session.refs) continue
      session.suspended = false
      session.finished = false
      session.controller = new AbortController()
      session.generation = (session.generation || 0) + 1
      queueMicrotask(() => { if (!session.controller.signal.aborted) void run(session) })
    }
  }
  events?.addEventListener('pagehide', onPageHide)
  events?.addEventListener('pageshow', onPageShow)
  return {
    start(job, { mode = 'hybrid', signal, onStatus } = {}) {
      if (!job || mode === 'server' || signal?.aborted) return () => {}
      let session = sessions.get(job)
      if (!session || session.controller.signal.aborted || session.finished) {
        session = { job, client: id(), mode, controller: new AbortController(), listeners: new Set(), refs: 0 }
        sessions.set(job, session)
        queueMicrotask(() => { if (!session.controller.signal.aborted) void run(session) })
      }
      session.refs++
      session.listeners.add(onStatus)
      if (session.status) onStatus?.(session.status)
      let stopped = false
      const stop = () => {
        if (stopped) return
        stopped = true
        signal?.removeEventListener('abort', stop)
        session.listeners.delete(onStatus)
        session.refs--
        queueMicrotask(() => {
          if (!session.refs && sessions.get(job) === session) {
            session.controller.abort()
            sessions.delete(job)
          }
        })
      }
      signal?.addEventListener('abort', stop, { once: true })
      return stop
    },
    close() { stopAll(); events?.removeEventListener('pagehide', onPageHide); events?.removeEventListener('pageshow', onPageShow); sessions.clear() },
  }
}
