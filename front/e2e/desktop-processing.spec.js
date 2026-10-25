import { test, expect } from '@playwright/test'
import { MockApi, video } from './mock-api.js'

async function openProcessing(page, { total = 80, theme = 'light' } = {}) {
  await page.addInitScript(theme => {
    localStorage.setItem('gongjing.theme', theme)
    const original = window.fetch.bind(window)
    window.desktopFeeds = []
    window.fetch = (input, options) => /\/link-jobs\/[^/]+\/events\?/.test(typeof input === 'string' ? input : input.url)
      ? Promise.resolve(new Response(new ReadableStream({ start(controller) { window.desktopFeeds.push(controller) } }), { headers: { 'Content-Type': 'text/event-stream' } }))
      : original(input, options)
  }, theme)
  const mock = new MockApi(page)
  mock.frames = total
  await mock.install()
  await page.route('**/api/link-jobs', route => route.fulfill({ json: mock.snapshot('job1', { v: video({ title: 'Blender 地形建模：从轮廓到材质的完整操作流程与细节讲解', duration: 180 }) }) }))
  await page.goto('/')
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await expect(page.locator('.hud__state-copy strong')).toHaveText('正在切分视频帧')
}

async function emit(page, events, feed = 0, close = false) {
  await expect.poll(() => page.evaluate(() => window.desktopFeeds.length)).toBeGreaterThan(feed)
  await page.evaluate(({ events, feed, close }) => {
    const controller = window.desktopFeeds[feed]
    controller.enqueue(new TextEncoder().encode(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')))
    if (close) controller.close()
  }, { events, feed, close })
}
const frames = (start, count) => Array.from({ length: count }, (_, i) => ({ type: 'frame', index: start + i, time: (start + i) * 2.25 }))
const done = (ok, missing = 0) => ({ type: 'done', coverage: { ok, missing, total: ok + missing, pending: 0, missing_ranges: missing ? [[175, 180]] : [], reasons: {} } })

test('desktop: parsing information stays visible; missing frames remain separate and retryable', async ({ page }) => {
  await openProcessing(page, { total: 20 })
  await emit(page, [...frames(0, 19), { type: 'missing', index: 19, message: '读取超时', reason: 'timeout' }])
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '95')
  await expect(page.locator('.filmstrip__count')).toHaveText('19 / 20 帧')
  await expect(page.locator('.hud__state-copy strong')).toHaveText('正在整理索引')
  await expect(page.locator('.hud__step', { hasText: '解析链接' })).toBeVisible()
  await expect(page.locator('.hud__step', { hasText: '语音转写' })).toBeVisible()
  await expect(page.locator('.filmstrip__title')).toContainText('1 帧未获取')
  await emit(page, [done(19, 1)], 0, true)
  await page.route('**/api/link-jobs/job1/retry', route => route.fulfill({ json: { retrying: 1, transcript: false, screentext: false, since: 21 } }))
  await page.locator('.hud__retry').click()
  await emit(page, [...frames(19, 1), { type: 'transcript', status: 'done', count: 12 }, done(20)], 1, true)
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
  await page.getByRole('button', { name: '进入对话分析', exact: true }).click()
  await expect(page.locator('.composer__input')).toBeVisible()
})

test('desktop: original frame queue and early entry preserve background work', async ({ page }) => {
  await openProcessing(page)
  await emit(page, frames(0, 24))
  await expect(page.locator('.filmstrip__item[data-status="done"]')).toHaveCount(24)
  await expect(page.locator('.filmstrip__item[data-status="pending"]')).toHaveCount(56)
  await page.getByRole('button', { name: '先进入对话', exact: false }).click()
  await expect(page.locator('.composer__input')).toBeVisible()
  await emit(page, [...frames(24, 56), { type: 'transcript', status: 'done', count: 12 }, done(80)], 0, true)
  await expect(page.locator('.composer__input')).toBeVisible()
})

for (const { width, height, theme } of [{ width: 761, height: 600, theme: 'light' }, { width: 1280, height: 720, theme: 'dark' }, { width: 1920, height: 1080, theme: 'light' }]) {
  test(`desktop: original scene and simplified information at ${width}x${height} ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await openProcessing(page, { theme, total: 120 })
    await emit(page, [...frames(0, 120), { type: 'transcript', status: 'done', count: 12 }, done(120)], 0, true)
    await expect(page.locator('.hud__file')).toBeVisible()
    await expect(page.locator('.hud__steps')).toBeVisible()
    const hud = await page.locator('.hud').boundingBox()
    const strip = await page.locator('.filmstrip-shell').boundingBox()
    expect(hud.y + hud.height).toBeLessThan(strip.y)
    const scene = await page.locator('.layer--sculpture').boundingBox()
    const canvas = await page.locator('.wireframe').boundingBox()
    expect(scene.width).toBeGreaterThan(canvas.width * .95)
    const button = page.getByRole('button', { name: '进入对话分析', exact: true })
    await button.scrollIntoViewIfNeeded()
    await expect(button).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    expect(errors).toEqual([])
  })
}
