import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

// Before the first question, questions written for this very video (backend modules/suggest.py).
const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

test('suggestions: questions written for this video replace the general ones, and one click asks', async ({ page }) => {
  const mock = new MockApi(page)
  mock.suggestions = { status: 'done', questions: [
    { question: '数据透视表是在哪一步改成表格形式的？', kind: 'tutorial', label: '教程操作', hint: '找到关键操作' },
    { question: '去掉分类汇总后为什么还要去掉总计？', kind: 'tutorial', label: '教程操作', hint: '弄清这样做的原因' },
    { question: '视频里一共用了哪几个设置？', kind: 'content', label: '视频内容', hint: '列出全部步骤' },
  ] }
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.chat__suggest-label')).toHaveText('为这个视频推荐的问题')
  const cards = page.locator('.chat-task--tailored')
  await expect(cards).toHaveCount(3)
  await expect(cards.first()).toContainText('教程操作')
  await expect(cards.first()).toContainText('找到关键操作')
  await cards.first().getByRole('button').click()
  await expect.poll(() => mock.runsSent()[0]?.question).toBe('数据透视表是在哪一步改成表格形式的？')
})

test('suggestions: without them the general cards stay', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.chat-task')).toHaveCount(3)
  await expect(page.locator('.chat-task--tailored, .chat__suggest-label')).toHaveCount(0)
})
