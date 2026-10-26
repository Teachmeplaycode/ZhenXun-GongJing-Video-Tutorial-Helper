import { test, expect } from '@playwright/test'
import { MockApi, video } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

// App wiring only: the real worker RPC is preserved; model accuracy has its own tests.
async function setup(page, { mode = 'local', screen = 'running', resume = false } = {}) {
  await page.addInitScript(() => {
    localStorage.setItem('zhenxun.guide.v1', '1')
    window.ocrWorkerCalls = []
    window.ocrWorkerTerminations = 0
    const NativeWorker = window.Worker
    window.Worker = class {
      constructor(url, options) {
        if (options?.name !== 'zhenxun-ocr') return new NativeWorker(url, options)
        window.ocrWorkerCalls.push({ type: 'construct', url: String(url) })
      }
      postMessage(message) {
        window.ocrWorkerCalls.push({ type: message.type, id: message.id })
        if (message.type === 'init') queueMicrotask(() => this.onmessage?.({ data: { id: message.id, result: null, elapsed: 0 } }))
        // Keep detect in flight so cancellation must release a real lease.
      }
      terminate() { window.ocrWorkerTerminations++ }
    }
    const originalFetch = window.fetch.bind(window)
    window.ocrFeeds = []
    window.fetch = (input, options) => {
      const url = typeof input === 'string' ? input : input.url
      if (/\/link-jobs\/[^/]+\/events\?/.test(url)) {
        return Promise.resolve(new Response(new ReadableStream({
          start(controller) { window.ocrFeeds.push(controller) },
        }), { headers: { 'Content-Type': 'text/event-stream' } }))
      }
      return originalFetch(input, options)
    }
  })
  const mock = new MockApi(page)
  const v = video(mode ? { ocr_mode: mode } : {})
  const snapshot = (job = 'job1', done = false) => ({
    ...mock.snapshot(job, { done, v }),
    screentext: { status: screen, message: screen === 'failed' ? '本机识别中断，可以重试' : '画面文字仍在处理', count: 0 },
  })
  if (resume) {
    mock.addSession('resume1', { title: '继续识别的会话' })
    mock.sessions[0].detail = { ...snapshot('resume1', true), task: '', messages: [] }
  }
  await mock.install()
  await page.route('**/api/link-jobs', (route) => route.fulfill({ json: snapshot() }))
  const requests = []
  await page.route('**/api/link-jobs/*/ocr/**', (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const body = request.method() === 'POST' ? request.postDataJSON() : null
    requests.push({ path, body })
    if (path.endsWith('/claim')) return route.fulfill({ json: {
      state: 'ready', mode: mode || 'server', lease_id: 'lease-1', lease_seconds: 30,
      frames: [{ id: 1, time: 7.5, url: '/api/link-jobs/job1/frames/0.jpg' }],
      progress: { done: 0, total: 4, local: 0, server: 0 },
    } })
    return route.fulfill({ json: { accepted: 1, state: 'waiting' } })
  })
  await page.goto('/')
  if (resume) {
    await page.locator('.btn--history').click()
    await page.locator('.history .session-item', { hasText: '继续识别的会话' }).locator('.session-item__open').click()
    await expect(page.locator('.composer__input')).toBeVisible()
  } else {
    await page.locator('.import-control__link').fill(LINK)
    await page.locator('.import-control__submit').click()
  }
  return { mock, requests }
}

async function emit(page, events, feed = 0) {
  await expect.poll(() => page.evaluate(() => window.ocrFeeds.length)).toBeGreaterThan(feed)
  await page.evaluate(({ events, feed }) => {
    window.ocrFeeds[feed].enqueue(new TextEncoder().encode(events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')))
  }, { events, feed })
}
const done = { type: 'done', coverage: { ok: 8, missing: 0, total: 8, pending: 0, missing_ranges: [], reasons: {} } }
const readyEvents = () => [
  ...Array.from({ length: 8 }, (_, index) => ({ type: 'frame', index, time: index * 15 + 7.5 })),
  { type: 'transcript', status: 'done', count: 12 }, done,
]
const calls = (page, type) => page.evaluate((kind) => window.ocrWorkerCalls.filter((item) => item.type === kind).length, type)

for (const mode of ['local', 'hybrid']) {
  test(`OCR lifecycle: ${mode} starts the worker and claims actual work during import`, async ({ page }) => {
    const { requests } = await setup(page, { mode })
    await expect.poll(() => calls(page, 'detect')).toBe(1)
    await expect.poll(() => requests.filter((item) => item.path.endsWith('/claim')).length).toBe(1)
    expect(await calls(page, 'init')).toBe(1)
    expect(requests.find((item) => item.path.endsWith('/claim')).body.client_id).toBeTruthy()
  })
}
for (const entry of [{ mode: 'server', screen: 'running', label: 'server' }, { mode: null, screen: 'running', label: 'legacy' }, { mode: 'local', screen: 'done', label: 'completed' }]) {
  test(`OCR lifecycle: ${entry.label} does not initialise a browser model`, async ({ page }) => {
    const { requests } = await setup(page, entry)
    await emit(page, readyEvents())
    await expect(page.locator('.btn--next:not(.btn--early)')).toBeVisible()
    await page.waitForTimeout(250)
    expect(await calls(page, 'construct')).toBe(0)
    expect(requests).toEqual([])
  })
}
test('OCR lifecycle: reopening an unfinished saved local session resumes the browser worker', async ({ page }) => {
  const { requests } = await setup(page, { mode: 'local', resume: true })
  await expect.poll(() => calls(page, 'detect')).toBe(1)
  expect(requests.find((item) => item.path.endsWith('/claim')).path).toContain('/resume1/')
})
test('OCR lifecycle: retrying failed text reactivates browser processing', async ({ page }) => {
  const { requests } = await setup(page, { mode: 'local', screen: 'failed' })
  await emit(page, readyEvents())
  await expect(page.locator('.hud__retry')).toBeVisible()
  expect(await calls(page, 'construct')).toBe(0)
  await page.route('**/api/link-jobs/job1/retry', (route) => route.fulfill({ json: { retrying: 0, transcript: false, screentext: true, since: 12 } }))
  await page.locator('.hud__retry').click()
  await expect.poll(() => calls(page, 'detect')).toBe(1)
  expect(requests.some((item) => item.path.endsWith('/claim'))).toBe(true)
})
test('OCR lifecycle: returning home releases in-flight work and aborts the worker', async ({ page }) => {
  const { requests } = await setup(page, { mode: 'hybrid' })
  await expect.poll(() => calls(page, 'detect')).toBe(1)
  await page.getByRole('button', { name: /返回首页/ }).first().click()
  await expect(page.locator('.import-control__link')).toBeVisible()
  await expect.poll(() => requests.some((item) => item.path.endsWith('/release') && item.body.lease_id === 'lease-1')).toBe(true)
  await expect.poll(() => page.evaluate(() => window.ocrWorkerTerminations)).toBeGreaterThan(0)
  const claims = requests.filter((item) => item.path.endsWith('/claim')).length
  await page.waitForTimeout(1100)
  expect(requests.filter((item) => item.path.endsWith('/claim')).length).toBe(claims)
})


test('OCR lifecycle: live progress shows the actual browser and server frame counts', async ({ page }) => {
  await setup(page, { mode: 'hybrid' })
  await expect.poll(() => calls(page, 'detect')).toBe(1)
  await emit(page, [...readyEvents(), { type: 'screentext', status: 'running', count: 3,
    processing: { mode: 'hybrid', done: 8, total: 20, local: 3, server: 5 } }])
  await expect(page.locator('.hud__value', { hasText: '8/20 张' })).toContainText('本机 3 · 服务器 5')
})
