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
