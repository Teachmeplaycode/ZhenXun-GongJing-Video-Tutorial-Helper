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
  await page.locator('.import-control__submit').click()
}

test('pictures: an upload goes straight to the picture page — no analysis screen, no timeline', async ({ page }) => {
  const mock = new MockApi(page)
  mock.frames = 2
  await uploadPictures(page, mock)
  await expect(page.locator('.pics-stage')).toBeVisible()
  expect(mock.uploadedImages).toBe(2)
  await expect(page.locator('.hud__step')).toHaveCount(0)
  await expect(page.locator('.btn--next')).toHaveCount(0)
  await expect(page.locator('.timeline')).toHaveCount(0)
  await expect(page.locator('.pics-post__tag')).toHaveText('上传 · 图文')
  await expect(page.locator('.pics-strip__thumb')).toHaveCount(2)
  await expect(page.locator('.pics-body__text')).toHaveText('燕麦加牛奶，早上十分钟搞定。') // the post's body, under the pictures
  await expect(page.locator('.pics-body__tags')).toHaveText('#早餐')
  await expect(page.locator('.pics-post__meta')).toContainText('赞 174')
  await expect(page.locator('.pics-view__count')).toHaveText('1 / 2')
  await expect(page.locator('.pics-text li')).toHaveText(['燕麦 50 克', '牛奶 250 毫升'])
  await page.getByRole('button', { name: '下一张' }).click()
  await expect(page.locator('.pics-view__count')).toHaveText('2 / 2')
  await expect(page.locator('.pics-text li')).toHaveText(['热量 320 千卡'])
  await expect(page.locator('.chat__empty h1')).toHaveText('关于这组图片，你想知道什么？')
  await openBench(page, '笔记')
  await expect(page.getByRole('tab')).toHaveText(['笔记'])
})

test('pictures: pick a picture as an attachment; 第 n 张 in an answer shows that picture', async ({ page }) => {
  const mock = new MockApi(page)
  mock.frames = 2
  mock.runs.push(pictureAnswer())
  await uploadPictures(page, mock)
  await page.getByRole('button', { name: '下一张' }).click()
  await page.getByRole('button', { name: '选第 2 张作附件' }).click()
  await expect(page.locator('.composer__scope')).toContainText('已选 1 张')
  await page.locator('.composer__input').fill('这张写了什么')
  await page.locator('.composer__input').press('Enter')
  await expect.poll(() => mock.runsSent()[0]?.scope).toEqual({ type: 'frames', frames: [1] })
  const chip = page.locator('.msg--assistant .streaming-text .ts-chip', { hasText: '第 1 张' })
  await expect(chip).toBeVisible()
  await expect(page.locator('.pics-view__count')).toHaveText('2 / 2')
  await chip.click()
  await expect(page.locator('.pics-view__count')).toHaveText('1 / 2')
})

test('pictures: back from the picture page returns to the import screen', async ({ page }) => {
  const mock = new MockApi(page)
  mock.frames = 2
  await uploadPictures(page, mock)
  await expect(page.locator('.pics-stage')).toBeVisible()
  await page.locator('.btn--back').click()
  await expect(page.locator('.pics-stage')).toBeHidden()
  await expect(page.locator('.import-control__file')).toContainText('2 张图片') // kept, like a pasted link
})
