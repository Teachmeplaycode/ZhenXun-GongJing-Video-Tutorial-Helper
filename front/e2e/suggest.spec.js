import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

// Suggested questions as pills above the input (backend modules/suggest.py writes them for the video),
// pictures attached to a question, and the grey Tab completion while typing.
const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

async function chat(page, setup) {
  const mock = new MockApi(page)
  setup?.(mock)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
  return mock
}

const TAILORED = { status: 'done', questions: [
  { question: '数据透视表是在哪一步改成表格形式的？', kind: 'tutorial', label: '教程操作', hint: '找到关键操作' },
  { question: '去掉分类汇总后为什么还要去掉总计？', kind: 'tutorial', label: '教程操作', hint: '弄清这样做的原因' },
  { question: '视频里一共用了哪几个设置？', kind: 'content', label: '视频内容', hint: '列出全部步骤' },
] }

test('suggestions: pills above the input, written for this video; one click asks; asked ones go', async ({ page }) => {
  const mock = await chat(page, (m) => { m.suggestions = TAILORED })
  await expect(page.locator('.chat-task')).toHaveCount(0) // no big cards any more
  const pills = page.locator('.composer__pill')
  await expect(pills).toHaveCount(3)
  await expect(pills.first()).toHaveText('数据透视表是在哪一步改成表格形式的？')
  await pills.first().click()
  await expect.poll(() => mock.runsSent()[0]?.question).toBe('数据透视表是在哪一步改成表格形式的？')
  await expect(page.locator('.msg--assistant .streaming-text').last()).toBeVisible()
  await expect(pills).toHaveCount(2) // the asked one is gone
  await page.locator('.composer__input').fill('x')
  await expect(pills).toHaveCount(0) // typing: out of the way
})

test('suggestions: without written ones the general questions show as pills', async ({ page }) => {
  await chat(page)
  await expect(page.locator('.composer__pill')).toHaveCount(3)
})

test('a picture rides with the question; alone it asks where one is stuck', async ({ page }) => {
  const mock = await chat(page)
  await page.locator('.composer input[type=file]').setInputFiles({ name: 'shot.png', mimeType: 'image/png', buffer: Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64') })
  await expect(page.locator('.image-chip')).toHaveAttribute('data-state', 'ready')
  await page.locator('.composer button[aria-label="发送"]').click()
  await expect.poll(() => mock.runsSent()[0]?.images).toEqual(['a00000000001'])
  expect(mock.runsSent()[0].question).toContain('卡在这一步')
  await expect(page.locator('.msg--user .attach-thumb--mine')).toHaveCount(1)
  await expect(page.locator('.image-chip')).toHaveCount(0)
})

test('desktop: grey completion after the caret, Tab takes it', async ({ page }) => {
  await chat(page, (m) => { m.suggestions = TAILORED; m.completion = '是怎么加的？' })
  const input = page.locator('.composer__input')
  await input.fill('数据透视')
  await expect(page.locator('.composer__ghost-rest')).toHaveText('表是在哪一步改成表格形式的？') // a known question: no request
  await input.press('Tab')
  await expect(input).toHaveValue('数据透视表是在哪一步改成表格形式的？')
  await input.fill('字幕')
  await expect(page.locator('.composer__ghost-rest')).toHaveText('是怎么加的？') // asked the model
  await input.press('Escape')
  await expect(page.locator('.composer__ghost')).toHaveCount(0)
})
