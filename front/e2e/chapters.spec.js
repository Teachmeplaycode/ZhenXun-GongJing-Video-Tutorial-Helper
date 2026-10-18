// Chapters panel and timeline bands (backend modules/chapters, Issue #1): the panel lists titles
// with time ranges, a click seeks the timeline, a failed build shows its reason.
import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

async function enterChat(page) {
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
}

test('the chapter panel lists titles with time ranges and folds away', async ({ page }) => {
  await new MockApi(page).install()
  await page.goto('/')
  await enterChat(page)

  const panel = page.locator('.chapters')
  await expect(panel).toBeVisible()
  await expect(panel.locator('.chapters__overview')).toContainText('整段视频介绍')
  await expect(panel.locator('.chapters__item')).toHaveCount(5)
  const first = panel.locator('.chapters__item').first()
  await expect(first).toContainText('开场')
  await expect(first).toContainText('00:00–00:20')
  await expect(panel.locator('.chapters__head')).toContainText('5 章')

  await panel.locator('.chapters__fold').click()
  await expect(panel.locator('.chapters__item')).toHaveCount(0)
  await panel.locator('.chapters__fold').click()
  await expect(panel.locator('.chapters__item').first()).toBeVisible()
})

test('clicking a chapter seeks the timeline to its start', async ({ page }) => {
  await new MockApi(page).install()
  await page.goto('/')
  await enterChat(page)

  await page.locator('.chapters__item', { hasText: '作用机制' }).click()
  // 45 s lands between two sheets: the nearest one rises with its preview, offset shown as ≈.
  await expect(page.locator('.tl-sheet.is-seeking')).toBeVisible()
  await expect(page.locator('.sheet-preview')).toBeVisible()
  await expect(page.locator('.sheet-preview')).toContainText('≈ 00:45')
})

test('a failed chapter build shows its reason', async ({ page }) => {
  const mock = new MockApi(page)
  mock.chaptersStatus = 'failed'
  mock.chaptersMessage = '章节生成失败：模型不可用'
  await mock.install()
  await page.goto('/')
  await enterChat(page)

  await expect(page.locator('.chapters')).toBeVisible()
  await expect(page.locator('.chapters__error')).toHaveText('章节生成失败：模型不可用')
  await expect(page.locator('.chapters__item')).toHaveCount(0)
})

test('chapters show as faint bands on the timeline', async ({ page }) => {
  await new MockApi(page).install()
  await page.goto('/')
  await enterChat(page)

  await expect(page.locator('.tl-chapterband')).toHaveCount(5)
  await expect(page.locator('.timeline__legend[data-kind="chapter"]')).toContainText('章节 5')
})
