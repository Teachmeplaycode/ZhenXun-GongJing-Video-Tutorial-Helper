import { test, expect } from '@playwright/test'
import { MockApi, video } from './mock-api.js'

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

// Hold real UI states deterministically: the job uses the normal API mock, while its SSE
// response remains open so frames / warnings / completion can arrive in separate batches.
async function setup(page, { total = 24, delayLink = false, theme = 'light', start = true } = {}) {
  await page.addInitScript(({ theme }) => {
    localStorage.setItem('gongjing.theme', theme)
    localStorage.setItem('zhenxun.guide.v1', '1')
    const originalFetch = window.fetch.bind(window)
    window.processingFeeds = []
    window.fetch = (input, options) => {
      const url = typeof input === 'string' ? input : input.url
      if (/\/link-jobs\/[^/]+\/events\?/.test(url)) {
        return Promise.resolve(new Response(new ReadableStream({
          start(controller) { window.processingFeeds.push(controller) },
        }), { headers: { 'Content-Type': 'text/event-stream' } }))
      }
      return originalFetch(input, options)
    }
  }, { theme })
  const mock = new MockApi(page)
  mock.frames = total
  await mock.install()
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/link-jobs', async route => {
    if (delayLink) await gate
    await route.fulfill({ json: mock.snapshot('job1', { v: video({ title: '从建模到渲染：一段很长的教程标题，用来确认手机端换行后不会挤压进度与操作按钮' }) }) })
  })
  await page.goto('/')
  if (start) {
    await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
    await page.locator('.import-control__submit').click()
  }
  return { mock, release }
}

async function emit(page, events, { feed = 0, close = false } = {}) {
  await expect.poll(() => page.evaluate(() => window.processingFeeds.length)).toBeGreaterThan(feed)
  await page.evaluate(({ events, feed, close }) => {
    const controller = window.processingFeeds[feed]
    controller.enqueue(new TextEncoder().encode(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')))
    if (close) controller.close()
  }, { events, feed, close })
}
const frames = (start, count) => Array.from({ length: count }, (_, i) => ({ type: 'frame', index: start + i, time: (start + i) * 5 }))
const done = (ok, missing = 0) => ({ type: 'done', coverage: { ok, missing, total: ok + missing, pending: 0, missing_ranges: missing ? [[115, 120]] : [], reasons: {} } })

test('mobile: parsing is indeterminate, then real counts, preview selection, early entry and background work', async ({ page }) => {
  const { release } = await setup(page, { delayLink: true })
  await expect(page.getByRole('heading', { name: '正在解析链接' })).toBeVisible()
  await expect(page.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  await expect(page.locator('.processing__continue')).toHaveCount(0)
  await expect(page.locator('.upload-mask')).toHaveCount(0)
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/processing-parsing.png` })
  release()
  await expect(page.getByRole('heading', { name: '正在提取画面' })).toBeVisible()
  await emit(page, frames(0, 4))
  await expect(page.locator('.processing__count strong')).toHaveText('4')
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '17')
  await page.locator('.processing__frame').first().click()
  const selected = await page.locator('.processing__preview-image').getAttribute('src')
  await emit(page, frames(4, 12))
  await expect(page.locator('.processing__count strong')).toHaveText('16')
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/processing-extracting.png` })
  await expect(page.locator('.processing__preview-image')).toHaveAttribute('src', selected)
  await page.getByRole('button', { name: '跟随最新画面' }).click()
  await expect(page.locator('.processing__preview-image')).not.toHaveAttribute('src', selected)
  await page.getByRole('button', { name: '先开始分析', exact: true }).click()
  await expect(page.locator('.composer__input')).toBeVisible()
  await emit(page, [...frames(16, 8), { type: 'transcript', status: 'done', count: 12 }, done(24)], { close: true })
  await expect(page.locator('.composer__input')).toBeVisible()
  await expect(page.locator('.processing')).toHaveCount(0)
})

test('mobile: all frames do not announce completion before the index; ongoing speech stays explicit', async ({ page }) => {
  await setup(page, { total: 8 })
  await emit(page, frames(0, 8))
  await expect(page.getByRole('heading', { name: '正在整理索引' })).toBeVisible()
  await expect(page.getByRole('button', { name: '开始分析', exact: true })).toHaveCount(0)
  await emit(page, [done(8)])
  await expect(page.getByRole('heading', { name: '画面已就绪' })).toBeVisible()
  await expect(page.locator('.processing__status')).toContainText('文字处理仍在继续')
  await page.locator('.processing__details summary').click()
  await expect(page.locator('.processing__details')).toContainText('正在读取音轨')
  await emit(page, [{ type: 'transcript', status: 'done', count: 12 }], { close: true })
  await expect(page.locator('.processing__status')).toContainText('画面与索引已准备好')
})

test('mobile: missing frames are separate from successes; retry fills them and clears the warning', async ({ page }) => {
  await setup(page, { total: 8 })
  await emit(page, [...frames(0, 7), { type: 'missing', index: 7, message: '读取超时', reason: 'timeout' }, { type: 'transcript', status: 'failed', message: '音轨读取失败' }, done(7, 1)], { close: true })
  await expect(page.locator('.processing__count strong')).toHaveText('7')
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '88')
  await expect(page.locator('.processing__notice')).toContainText('1 帧未能获取')
  await expect(page.locator('.processing__notice')).toContainText('语音转写失败')
  await page.route('**/api/link-jobs/job1/retry', route => route.fulfill({ json: { retrying: 1, transcript: true, screentext: false, since: 9 } }))
  await page.getByRole('button', { name: '重试未完成内容' }).click()
  await expect(page.getByRole('heading', { name: '正在补充素材' })).toBeVisible()
  await emit(page, [...frames(7, 1), { type: 'transcript', status: 'done', count: 12 }, done(8)], { feed: 1, close: true })
  await expect(page.locator('.processing__count strong')).toHaveText('8')
  await expect(page.locator('.processing__notice')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '开始分析', exact: true })).toBeEnabled()
})

test('mobile: returning during parsing aborts the flow; link errors return a readable import error', async ({ page }) => {
  const { release } = await setup(page, { delayLink: true })
  await page.getByRole('button', { name: '返回导入视频', exact: true }).click()
  await expect(page.locator('.import-control__link')).toBeVisible()
  release()
  await expect(page.locator('.processing')).toHaveCount(0)
  await page.route('**/api/link-jobs', route => route.fulfill({ status: 422, json: { detail: '无法解析此视频，请检查链接' } }))
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await expect(page.getByText('无法解析此视频，请检查链接', { exact: true })).toBeVisible()
  await expect(page.locator('.processing')).toHaveCount(0)
})

test('mobile: local upload shows measured progress then hands over to the same frame flow', async ({ page }) => {
  const { mock } = await setup(page, { total: 8, start: false })
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/videos', async route => {
    await gate
    await route.fulfill({ json: mock.snapshot('upload1', { v: video({ platform: 'local' }) }) })
  })
  await page.locator('input[type="file"]').setInputFiles('e2e/fixtures/playback.mp4')
  await page.locator('.import-control__submit').click()
  await expect(page.getByRole('heading', { name: '正在上传视频' })).toBeVisible()
  await expect(page.getByRole('progressbar', { name: '上传进度' })).toHaveAttribute('aria-valuenow', /^\d+$/)
  await expect(page.locator('.processing__bytes')).toContainText('/')
  release()
  await emit(page, [...frames(0, 8), { type: 'transcript', status: 'done', count: 12 }, done(8)], { close: true })
  await expect(page.getByRole('button', { name: '开始分析', exact: true })).toBeVisible()
  await expect(page.locator('.processing__source')).toContainText('本地文件')
})

test('mobile: unknown totals and added shot frames keep counts and stage honest', async ({ page }) => {
  await setup(page, { total: 0 })
  await expect(page.getByRole('heading', { name: '正在提取画面' })).toBeVisible()
  await expect(page.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
  await emit(page, [{ type: 'slots', slots: Array.from({ length: 8 }, (_, index) => ({ index, time: index * 5 })) }, ...frames(0, 8), done(8)])
  await expect(page.locator('.processing__count')).toContainText('/ 8 · 帧')
  await expect(page.getByRole('heading', { name: '画面已就绪' })).toBeVisible()
  await emit(page, [{ type: 'slots', slots: [{ index: 8, time: 17.5 }, { index: 9, time: 23.5 }] }])
  await expect(page.getByRole('heading', { name: '正在提取画面' })).toBeVisible()
  await expect(page.locator('.processing__count')).toContainText('/ 10 · 帧')
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '80')
  await emit(page, [...frames(8, 2), { type: 'transcript', status: 'done', count: 12 }, done(10)], { close: true })
  await expect(page.getByRole('heading', { name: '画面已就绪' })).toBeVisible()
  await expect(page.locator('.processing__preview figcaption time')).toHaveText('00:23')
})

test('mobile: resizing uses desktop presentation without losing the active task', async ({ page }) => {
  await setup(page, { total: 8 })
  await emit(page, frames(0, 4))
  await expect(page.locator('.processing__count strong')).toHaveText('4')
  await page.setViewportSize({ width: 1024, height: 768 })
  await expect(page.locator('.processing')).toHaveCount(0)
  await expect(page.locator('.hud__step', { hasText: '抓取关键帧' })).toContainText('4 / 8')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('.processing__count strong')).toHaveText('4')
  await emit(page, [...frames(4, 4), { type: 'transcript', status: 'done', count: 12 }, done(8)], { close: true })
  await expect(page.getByRole('button', { name: '开始分析', exact: true })).toBeVisible()
  await expect(page.locator('.processing__status')).toHaveCSS('animation-name', 'none')
})

test.describe('standard motion', () => {
  test.use({ reducedMotion: 'no-preference' })
  test('mobile: desktop pixel-and-logo wipe connects import, parsing, frames, chat and back', async ({ page }) => {
    const { release } = await setup(page, { delayLink: true, start: false })
    await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
    await page.locator('.import-control__submit').click()
    await expect(page.locator('.wipe')).toBeVisible()
    await expect(page.locator('.wipe__pixel')).toHaveCount(160)
    await expect(page.locator('.wipe__snake')).toBeVisible()
    await expect(page.getByRole('heading', { name: '正在解析链接' })).toBeVisible()
    await expect(page.locator('.wipe')).toBeHidden()
    await expect(page.locator('.upload-mask, .processing canvas')).toHaveCount(0)
    await expect(page.locator('.processing__progress > span')).toHaveCSS('animation-name', 'processing-scan')
    release()
    await expect(page.locator('.wipe')).toBeVisible()
    await expect(page.getByRole('heading', { name: '正在提取画面' })).toBeVisible()
    await expect(page.locator('.wipe')).toBeHidden()
    await emit(page, frames(0, 16))
    await page.getByRole('button', { name: '先开始分析', exact: true }).click()
    await expect(page.locator('.wipe')).toBeVisible()
    await expect(page.locator('.composer__input')).toBeVisible()
    await expect(page.locator('.wipe')).toBeHidden()
    await page.getByRole('button', { name: /返回首页/ }).click()
    await expect(page.locator('.wipe')).toBeVisible()
    await expect(page.locator('.import-control__link')).toBeVisible()
    await expect(page.locator('.wipe')).toBeHidden()
  })
})

for (const { width, height, theme } of [{ width: 360, height: 640, theme: 'light' }, { width: 390, height: 844, theme: 'dark' }, { width: 430, height: 932, theme: 'light' }]) {
  test(`mobile: ${width}px ${theme} has readable long content and reachable controls`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await setup(page, { total: 120, theme })
    await emit(page, [...frames(0, 120), { type: 'transcript', status: 'done', count: 12 }, done(120)], { close: true })
    const button = page.getByRole('button', { name: '开始分析', exact: true })
    await expect(button).toBeVisible()
    const box = await button.boundingBox()
    expect(box.height).toBeGreaterThanOrEqual(52)
    expect(box.y + box.height).toBeLessThanOrEqual(height)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/processing-${width}-${theme}.png` })
    await page.locator('.processing__details summary').click()
    await expect(page.locator('.processing__details')).toContainText('已建立')
    await expect(button).toBeInViewport()
    expect(errors).toEqual([])
  })
}
