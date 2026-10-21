// Phones: a one-line top bar, the timeline folded, a full-screen workbench, and logins confirmed
// on the phone itself (the QR can't scan the screen it's on).
import { test, expect } from '@playwright/test'
import { MockApi, openBench } from './mock-api.js'

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

async function start(page, setup) {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1'))
  const mock = new MockApi(page)
  setup?.(mock)
  await mock.install()
  await page.goto('/')
  return mock
}

test('phone: the chat keeps the room — timeline folded, workbench full screen', async ({ page }) => {
  await start(page)
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
  await expect(page.locator('.stepper')).toBeHidden()
  await expect(page.locator('.brand__name .wordmark__en')).toBeHidden()
  await expect(page.locator('.timeline')).not.toHaveAttribute('data-open', '')
  await openBench(page, '章节')
  const bench = await page.locator('.bench').boundingBox()
  expect(Math.round(bench.width)).toBe(390)
  await page.locator('.bench__handle').click()
  await expect(page.locator('.bench')).not.toHaveAttribute('data-open', '')
})

test('phone: B 站 is confirmed in the B 站 App, WeChat by a saved QR', async ({ page }) => {
  await start(page, (mock) => {
    mock.publicDemo = true
    mock.member = { name: '评委1', questions: { used: 0, limit: 10 }, imports: { used: 0, limit: 3 } }
  })
  await page.locator('.member-chip').click()
  await page.getByRole('dialog', { name: '我的' }).getByRole('button', { name: /平台账号/ }).click()
  const bili = page.locator('.account-card', { hasText: 'B 站' })
  await bili.getByRole('button', { name: '扫码绑定' }).click()
  await expect(bili.getByRole('link', { name: '在 B 站 App 里确认' })).toHaveAttribute('href', /^bilibili:\/\/browser\?url=https%3A%2F%2Fpassport\.bilibili\.com/)
  await expect(bili).toContainText('加密保存在你的帧寻账号里')
})
