import { test, expect } from '@playwright/test'
import { MockApi, openBench } from './mock-api.js'

const pictureAnswer = () => [
  { type: 'tool_call.started', call_id: 'frames', tool_name: 'frames.select', t: 0.01 },
  { type: 'tool_call.completed', call_id: 'frames', result_count: 2, t: 0.02 },
  { type: 'assistant.message.delta', delta: '第 2 张写着热量 320 千卡，第 1 张是燕麦。', t: 1 },
  { type: 'run.completed', steps: 1, elapsed_ms: 1000, summary: '2 张图片', t: 1.1 },
]

async function uploadPictures(page, mock) {
  await mock.install()
  await page.goto('/')
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64')
  await page.locator('input[type=file]').setInputFiles([
    { name: '早餐.png', mimeType: 'image/png', buffer: png },
    { name: '热量.png', mimeType: 'image/png', buffer: png },
  ])
  await expect(page.locator('.import-control__file')).toContainText('2 张图片')
  await expect(page.locator('.import-control__submit')).toHaveText(/开始分析/)
  await page.locator('.import-control__submit').click()
}

test('pictures: several images import as a picture set, without the video steps', async ({ page }) => {
  const mock = new MockApi(page)
  mock.frames = 2
  await uploadPictures(page, mock)
  await expect(page.locator('.hud__step', { hasText: '读取图片' })).toContainText('2 / 2')
  await expect(page.locator('.hud__step', { hasText: '图片文字' })).toBeVisible()
  await expect(page.locator('.hud__step', { hasText: '语音转写' })).toHaveCount(0)
  await expect(page.locator('.hud__step', { hasText: '建立时间轴索引' })).toHaveCount(0)
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  expect(mock.uploadedImages).toBe(2)

  await expect(page.locator('.chat__empty h1')).toHaveText('关于这组图片，你想知道什么？')
  await expect(page.locator('.timeline__head')).toContainText('2 张图片')
  await expect(page.getByRole('button', { name: '输入区间' })).toHaveCount(0) // no time to frame
  await expect(page.locator('.tl-sheet').first()).toHaveAttribute('aria-label', '第 1 张')
  await expect(page.locator('.composer__scope')).toContainText('范围：全部图片')
  await openBench(page, '笔记')
  await expect(page.getByRole('tab')).toHaveText(['反诈', '科普', '笔记']) // no chapters in a picture set
})

test('pictures: 第 n 张 in an answer points the timeline at that picture', async ({ page }) => {
  const mock = new MockApi(page)
  mock.frames = 2
  mock.runs.push(pictureAnswer())
  await uploadPictures(page, mock)
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.locator('.composer__input').fill('这两张图说了什么')
  await page.locator('.composer__input').press('Enter')
  const chip = page.locator('.msg--assistant .streaming-text .ts-chip', { hasText: '第 2 张' })
  await expect(chip).toBeVisible()
  await chip.click()
  await expect(page.locator('.sheet-preview')).toContainText('第 2 张')
})
