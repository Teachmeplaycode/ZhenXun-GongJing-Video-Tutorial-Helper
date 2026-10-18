// An in-browser stand-in for the backend: every /api request is answered here, so the tests run offline,
// cost nothing and give the same result every time. Responses follow backend/app.py's shapes.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const FRAME = readFileSync(fileURLToPath(new URL('./fixtures/frame.jpg', import.meta.url)))
const sse = (events) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')

export function video(overrides = {}) {
  return {
    platform: 'bilibili', video_id: 'BV1TEST00001', canonical_url: 'https://www.bilibili.com/video/BV1TEST00001',
    title: '测试视频：柚子与药物', duration: 120, part: 1, parts: [{ index: 1, title: 'P1', duration: 120 }],
    cover: '', author: '测试作者', description: '一段用于端到端测试的视频', playable_duration: null, notes: [],
    stream_count: 1, has_audio: true, ...overrides,
  }
}

const slots = (n, duration, status) => Array.from({ length: n }, (_, i) => ({
  index: i, time: Math.round(((i + 0.5) / n) * duration * 1000) / 1000, status, reason: '',
}))

/** The default answer: intent decision → frames/transcript → a web search with verdicts → text. */
export function researchAnswer() {
  const results = [
    { title: 'Grapefruit Juice and Some Drugs Don\'t Mix', url: 'https://www.fda.gov/grapefruit', host: 'www.fda.gov', verdict: 'reliable', p: { reliable: 0.97, unreliable: 0.02, irrelevant: 0.01 } },
    { title: '震惊！这种水果和 85 种药相克', url: 'https://toutiao.example.com/a', host: 'toutiao.example.com', verdict: 'unreliable', p: { reliable: 0.2, unreliable: 0.7, irrelevant: 0.1 } },
    { title: '经常饭后腹胀是否属于肠胃损伤', url: 'https://farm.example.cn/b', host: 'farm.example.cn', verdict: 'irrelevant', p: { reliable: 0.05, unreliable: 0.1, irrelevant: 0.85 } },
  ]
  return [
    { type: 'progress.update', step: '整理画面', percent: 10, t: 0 },
    { type: 'tool_call.started', call_id: 'frames', tool_name: 'frames.select', t: 0.01 },
    { type: 'tool_call.input', call_id: 'frames', input: { kind: 'params', params: { scope: '整段视频' } }, t: 0.01 },
    { type: 'tool_call.output', call_id: 'frames', stdout: 'F001 00:07', exit_code: 0, t: 0.02 },
    { type: 'tool_call.completed', call_id: 'frames', result_count: 8, t: 0.02 },
    { type: 'tool_call.started', call_id: 'speech', tool_name: 'transcript.read', t: 0.03 },
    { type: 'tool_call.input', call_id: 'speech', input: { kind: 'params', params: { scope: '整段视频' } }, t: 0.03 },
    { type: 'tool_call.output', call_id: 'speech', stdout: '12 句', exit_code: 0, t: 0.04 },
    { type: 'tool_call.completed', call_id: 'speech', result_count: 4, t: 0.04 },
    { type: 'tool_call.started', call_id: 'intent', tool_name: 'decision.research_intent', t: 0.05 },
    { type: 'tool_call.output', call_id: 'intent', stdout: '需要先查资料再回答', exit_code: 0, data: { p: 0.82, needed: true }, t: 0.25 },
    { type: 'tool_call.completed', call_id: 'intent', result_count: 1, t: 0.25 },
    { type: 'tool_call.started', call_id: 'model0', tool_name: 'vision.deepseek-flash', t: 0.3 },
    { type: 'tool_call.output', call_id: 'model0', stdout: '请求工具：web_search', exit_code: 0, t: 3.1 },
    { type: 'tool_call.completed', call_id: 'model0', result_count: 8, t: 3.1 },
    { type: 'progress.update', step: '我来查一下资料。', percent: 40, t: 3.1 },
    { type: 'tool_call.started', call_id: 'tool1', tool_name: 'web.search', t: 3.2 },
    { type: 'tool_call.input', call_id: 'tool1', input: { kind: 'params', params: { query: 'grapefruit drug interaction' } }, t: 3.2 },
    { type: 'tool_call.output', call_id: 'tool1', stdout: '2 条', exit_code: 0, data: { query: 'grapefruit drug interaction', results }, t: 5.4 },
    { type: 'tool_call.completed', call_id: 'tool1', result_count: 2, t: 5.4 },
    { type: 'tool_call.started', call_id: 'model1', tool_name: 'vision.deepseek-flash', t: 5.5 },
    { type: 'assistant.message.delta', delta: '结论：会影响部分药物。\n\n', t: 7.0 },
    { type: 'assistant.message.delta', delta: '- 视频在 [00:30] 提到柚子会抑制 **CYP3A4**\n- FDA 说明见 https://www.fda.gov/grapefruit', t: 7.4 },
    { type: 'tool_call.output', call_id: 'model1', stdout: 'finish_reason=stop', exit_code: 0, t: 7.5 },
    { type: 'tool_call.completed', call_id: 'model1', result_count: 8, t: 7.5 },
    { type: 'run.completed', steps: 6, elapsed_ms: 7600, summary: '分析 8 帧 · 4 行语音 · deepseek-flash · 输入 1000 · 输出 100 tokens', t: 7.6 },
  ]
}

/** An answer that replays 01:00–01:01 slowly (4 frames) and takes a closer look at 00:10–00:20 (2 frames). */
export function replayAnswer() {
  const replay = { start: 60, end: 61, fps: 3, clipped: false, times: [60, 60.33, 60.67, 61],
    frames: ['00', '01', '02', '03'].map((n) => `/api/link-jobs/job1/replay/0006000-0006100-030/${n}.jpg`) }
  const view = { start: 10, end: 20, times: ['00:12', '00:17'], fallback: false, secs: [12.5, 17.5],
    frames: ['00001250', '00001750'].map((n) => `/api/link-jobs/job1/extra/${n}.jpg`) }
  return [
    { type: 'tool_call.started', call_id: 'replay1', tool_name: 'frames.replay', t: 0.1 },
    { type: 'tool_call.input', call_id: 'replay1', input: { kind: 'params', params: { start: '60', end: '61' } }, t: 0.1 },
    { type: 'tool_call.output', call_id: 'replay1', stdout: '复看 01:00–01:01', exit_code: 0, data: replay, t: 0.5 },
    { type: 'tool_call.completed', call_id: 'replay1', result_count: 4, t: 0.5 },
    { type: 'tool_call.started', call_id: 'view1', tool_name: 'frames.view', t: 0.6 },
    { type: 'tool_call.input', call_id: 'view1', input: { kind: 'params', params: { start: '00:10', end: '00:20', count: 2 } }, t: 0.6 },
    { type: 'tool_call.output', call_id: 'view1', stdout: '2 张画面', exit_code: 0, data: view, t: 0.9 },
    { type: 'tool_call.completed', call_id: 'view1', result_count: 2, t: 0.9 },
    { type: 'assistant.message.delta', delta: '他在 [01:00] 起跳。', t: 1.0 },
    { type: 'run.completed', steps: 2, elapsed_ms: 1100, summary: '慢放 4 帧 · 补看 2 帧', t: 1.1 },
  ]
}

export class MockApi {
  constructor(page) {
    this.page = page
    this.requests = [] // { method, path, body }
    this.sessions = [] // saved sessions: { summary, detail }
    this.runs = [] // queued agent answers (event lists); the default answer when empty
    this.gate = null // when set, the next agent run waits for gate.release()
    this.linkError = null // when set, POST /api/link-jobs answers 422 with it
    this.frames = 8
    this.cuts = [30, 75] // shot changes the mock reports
    this.chaptersStatus = 'done' // what /chapters answers; 'running' | 'done' | 'failed' in tests
    this.chaptersMessage = '' // a custom message, e.g. the reason for a failed build
    this.chapters = [ // the chapter list the mock reports (backend modules/chapters)
      { start: 0, end: 20, title: '开场', summary: '引入话题：柚子与药物' },
      { start: 20, end: 45, title: '背景介绍', summary: '柚子的营养成分和常见吃法' },
      { start: 45, end: 70, title: '作用机制', summary: 'CYP3A4 酶被抑制的过程' },
      { start: 70, end: 95, title: '相互影响', summary: '与常见药物的相互作用' },
      { start: 95, end: 120, title: '实用建议', summary: '服药期间该怎么吃柚子' },
    ]
    this.accounts = [
      { id: 'bilibili', label: 'B 站', purpose: '读更多评论', app: 'B 站 App', configured: false, source: null, user: '', expires: null, valid: null },
      { id: 'yuanbao', label: '腾讯元宝', purpose: '解析视频号链接', app: '微信', configured: true, source: 'env', user: '', expires: null, valid: null },
    ]
    this.loginPolls = ['waiting', 'scanned', 'done'] // states the QR login goes through, one per poll
  }

  /** The next agent run waits until the returned function is called. */
  holdNextRun() {
    let release
    const promise = new Promise((resolve) => { release = resolve })
    this.gate = { promise }
    return release
  }

  runsSent() {
    return this.requests.filter((r) => r.path === '/api/agent/runs').map((r) => r.body)
  }

  snapshot(jobId, { done = false, v = video() } = {}) {
    return {
      job_id: jobId, video: v, running: !done, seq: 0,
      slots: slots(this.frames, v.duration, done ? 'ok' : 'pending'),
      coverage: { ok: done ? this.frames : 0, missing: 0, total: this.frames, pending: done ? 0 : this.frames, missing_ranges: [], reasons: {} },
      transcript: done ? { status: 'done', message: '已转写 12 句', count: 12 } : { status: 'running', message: '正在读取音轨', count: 0 },
    }
  }

  jobEvents(v = video()) {
    const events = [{ seq: 0, type: 'started', indexes: [] }]
    for (const s of slots(this.frames, v.duration, 'ok')) events.push({ seq: events.length, type: 'frame', index: s.index, time: s.time })
    events.push({ seq: events.length, type: 'transcript', status: 'done', message: '已转写 12 句', count: 12 })
    events.push({ seq: events.length, type: 'done', coverage: { ok: this.frames, missing: 0, total: this.frames, pending: 0, missing_ranges: [], reasons: {} } })
    return events
  }

  async install() {
    await this.page.route((url) => url.pathname.startsWith('/api/'), (route) => this.handle(route))
  }

  async handle(route) {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    let body = null
    try {
      body = req.postDataJSON()
    } catch {
      body = req.postData()
    }
    this.requests.push({ method: req.method(), path, body })
    const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    const stream = (events) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: sse(events) })

    if (path === '/api/health') return json({ ok: true, platforms: ['bilibili', 'wechat_channels', 'local'], ffmpeg: true, model: 'deepseek-flash' })
    if (path === '/api/sessions' && req.method() === 'GET') return json({ sessions: this.sessions.map((s) => s.summary) })
    let m = path.match(/^\/api\/sessions\/(\w+)$/)
    if (m && req.method() === 'GET') return json(this.sessions.find((s) => s.summary.id === m[1]).detail)
    if (m && req.method() === 'DELETE') {
      this.sessions = this.sessions.filter((s) => s.summary.id !== m[1])
      return json({ ok: true })
    }
    if (path === '/api/link-jobs' && req.method() === 'POST') {
      if (this.linkError) return json(this.linkError, 422)
      return json(this.snapshot('job1'))
    }
    if (path === '/api/videos') return json(this.snapshot('upload1', { v: video({ platform: 'local', video_id: 'clip.mp4', title: 'clip' }) }))
    m = path.match(/^\/api\/link-jobs\/(\w+)\/events$/)
    if (m) return stream(this.jobEvents().filter((e) => e.seq >= Number(url.searchParams.get('since') || 0)))
    m = path.match(/^\/api\/link-jobs\/(\w+)\/(frames\/\d+|replay\/[\d-]+\/\d{2}|extra\/\d{8})\.jpg$/)
    if (m) return route.fulfill({ status: 200, contentType: 'image/jpeg', body: FRAME })
    m = path.match(/^\/api\/link-jobs\/(\w+)\/cuts$/)
    if (m) return json({ status: 'done', cuts: this.cuts, message: '' })
    m = path.match(/^\/api\/link-jobs\/(\w+)\/chapters$/)
    if (m) return json({
      status: this.chaptersStatus, chapters: this.chapters, summary: "整段视频介绍柚子与药物相互作用的原理。",
      message: this.chaptersMessage || (this.chaptersStatus === 'done' ? `已生成 ${this.chapters.length} 个章节` : ''),
    })
    m = path.match(/^\/api\/link-jobs\/(\w+)\/replay$/)
    if (m && req.method() === 'POST') {
      const { start, end } = body
      const frames = [0, 1, 2, 3].map((i) => `/api/link-jobs/${m[1]}/replay/0000000-0000000-030/0${i}.jpg`)
      const data = { start, end, fps: 3, clipped: false, times: [0, 1, 2, 3].map((i) => Math.round((start + (i * (end - start)) / 3) * 100) / 100), frames }
      return json({ manual: 'replay', events: [
        { type: 'tool_call.started', call_id: 'manual1', tool_name: 'frames.replay', t: 0 },
        { type: 'tool_call.output', call_id: 'manual1', stdout: '复看', exit_code: 0, data, t: 0.4 },
        { type: 'tool_call.completed', call_id: 'manual1', result_count: 4, t: 0.4 },
      ] })
    }
    if (path === '/api/accounts') return json({ accounts: this.accounts })
    m = path.match(/^\/api\/accounts\/(\w+)\/login$/)
    if (m && req.method() === 'POST') {
      return json({ id: `login-${m[1]}`, platform: m[1], state: 'waiting', message: '', user: '', expires_in: 180, qr: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><rect width="2" height="2"/></svg>' })
    }
    m = path.match(/^\/api\/accounts\/login\/login-(\w+)$/)
    if (m && req.method() === 'GET') {
      const state = this.loginPolls.length > 1 ? this.loginPolls.shift() : this.loginPolls[0]
      const out = { id: `login-${m[1]}`, platform: m[1], state, message: state === 'scanned' ? '已扫码，请在手机上确认登录' : '', user: '', expires_in: 170 }
      if (state === 'done') {
        const account = { ...this.accounts.find((a) => a.id === m[1]), configured: true, source: 'ui', user: '测试用户', valid: true, expires: 1800000000 }
        this.accounts = this.accounts.map((a) => (a.id === m[1] ? account : a))
        return json({ ...out, user: '测试用户', message: '登录成功', account })
      }
      return json(out)
    }
    if (m && req.method() === 'DELETE') return json({ ok: true })
    if (path === '/api/agent/runs') {
      const gate = this.gate
      this.gate = null
      if (gate) await gate.promise
      const events = (this.runs.shift() || researchAnswer()).map((e) => ({ run_id: 'r1', ...e }))
      try {
        return await stream(events)
      } catch {
        return undefined // the page aborted the request (stop) while it was held
      }
    }
    return json({ detail: `mock has no route for ${req.method()} ${path}` }, 404)
  }

  /** A saved session as /api/sessions and /api/sessions/{id} return it. */
  addSession(id, { title = '历史会话', messages = [] } = {}) {
    const v = video({ title, video_id: `BV1${id}` })
    this.sessions.push({
      summary: {
        id, created: Date.now() / 1000 - 3600, updated: Date.now() / 1000 - 60, title, author: '测试作者', platform: 'bilibili',
        video_id: v.video_id, part: 1, duration: v.duration, frames_ok: this.frames, frames_total: this.frames,
        cover_index: 0, transcript: 'done', questions: messages.filter((x) => x.role === 'user').length,
        last_question: [...messages].reverse().find((x) => x.role === 'user')?.content || '',
      },
      detail: { ...this.snapshot(id, { done: true, v }), task: '', messages },
    })
  }
}
