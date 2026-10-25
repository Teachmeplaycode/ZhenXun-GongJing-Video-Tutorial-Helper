// Tutorials side by side (backend modules/compare.py): pick another session, rows of the same
// operation; this video's time seeks here, another's opens that session.
import { test, expect } from '@playwright/test'
import { MockApi, openBench } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

test('compare: pick another tutorial, rows per operation, its time opens that session', async ({ page }) => {
  const mock = new MockApi(page)
  mock.addSession('other1', { title: '另一个教程', messages: [{ role: 'user', content: '另一个教程里问过的', status: 'done', frames: [] }] })
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await openBench(page, '对照')
  const tab = page.locator('.compare-tab')
  const go = tab.getByRole('button', { name: /对照这|先选/ })
  await expect(go).toBeDisabled()
  await tab.locator('.compare-pick', { hasText: '另一个教程' }).click()
  await expect(go).toHaveText('对照这 2 个教程')
  await go.click()
  await expect(tab.locator('.compare-row')).toHaveCount(2)
  await expect(tab.locator('.compare-tab__summary')).toContainText('先看甲')
  await expect(tab.locator('.compare-row').nth(1)).toContainText('乙 没讲')
  await tab.locator('.compare-row').first().locator('.compare-cell').nth(1).click() // 乙 · 00:30
  await expect(page.locator('.msg--user .bubble__text')).toHaveText('另一个教程里问过的') // that session is open now
})

test('compare: a related Bilibili tutorial is imported in the background and ticked when ready', async ({ page }) => {
  const mock = new MockApi(page)
  mock.related = [{ url: 'https://www.bilibili.com/video/BV1REL000001/', title: '相关教程一', author: 'up', duration: 300, views: 123456, cover: '', imported: false }]
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await openBench(page, '对照')
  const tab = page.locator('.compare-tab')
  await expect(tab.locator('.related__item')).toContainText('12 万 播放')
  mock.nextJob = { id: 'rel1', title: '相关教程一' }
  await tab.locator('.related__item').getByRole('button', { name: '导入' }).click()
  await expect(tab.locator('.related .working')).toContainText('正在解析：相关教程一')
  await expect(tab.locator('.compare-pick', { hasText: '相关教程一' }).locator('input')).toBeChecked({ timeout: 15_000 })
  await expect(tab.locator('.related__item').getByRole('button', { name: '已导入，勾上' })).toBeVisible()
  await expect(tab.getByRole('button', { name: '对照这 2 个教程' })).toBeEnabled()
})

test('compare from the homepage: several links pasted, each imported, then lined up; a failed one is said', async ({ page }) => {
  const mock = new MockApi(page)
  mock.batch = { fail: [2] } // the second link doesn't resolve
  await mock.install()
  await page.goto('/')
  const field = page.locator('.import-control__link')
  await field.fill('【透视表】 https://www.bilibili.com/video/BV1TEST00001 https://b23.tv/abcd123【另一个】https://www.bilibili.com/video/BV1TEST00003')
  await expect(page.locator('#import-link-hint')).toContainText('识别到 3 个链接')
  await page.locator('.import-control__submit').click()
  const stage = page.locator('.compare-stage')
  await expect(stage.locator('.compare-stage__videos li')).toHaveCount(3)
  await expect(stage.locator('.compare-stage__videos li').nth(1)).toContainText('链接解析失败')
  await expect(stage.locator('.compare-row')).toHaveCount(2, { timeout: 20_000 })
  expect(mock.batchUrls).toEqual(['https://www.bilibili.com/video/BV1TEST00001', 'https://b23.tv/abcd123', 'https://www.bilibili.com/video/BV1TEST00003'])
  expect(mock.compared.ids).toEqual(['multi1', 'multi3'])
  await page.screenshot({ path: 'test-results/compare-home.png' })
  await stage.locator('.compare-row').first().locator('.compare-cell').nth(1).click() // 乙 · 00:30 opens that session
  await expect(page.locator('.compare-stage')).toHaveCount(0)
})

test('compare from the homepage: more than five links are refused before importing', async ({ page }) => {
  const mock = new MockApi(page)
  mock.batch = {}
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill([1, 2, 3, 4, 5, 6].map((n) => `https://www.bilibili.com/video/BV1TEST0000${n}`).join(' '))
  await expect(page.locator('#import-link-hint')).toContainText('一次最多对照 5 个')
  await page.locator('.import-control__submit').click()
  await expect(page.locator('.field-error')).toContainText('一次最多对照 5 个')
  expect(mock.batchUrls).toBeUndefined()
})
