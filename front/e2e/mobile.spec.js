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

test('phone: the chat keeps the room — no timeline, workbench full screen', async ({ page }) => {
  await start(page)
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await page.getByRole('button', { name: '开始分析', exact: true }).click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
  await expect(page.locator('.stepper')).toBeHidden()
  await expect(page.locator('.brand__name .wordmark__en')).toBeHidden()
  await expect(page.locator('.timeline')).toHaveCount(0) // the frames are in the workbench's 画面 tab
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

test('phone: frames are picked in a big grid — attach, or frame a stretch to replay', async ({ page }) => {
  const mock = await start(page)
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await page.getByRole('button', { name: '开始分析', exact: true }).click({ timeout: 30_000 })
  await page.locator('.composer').getByRole('button', { name: /选帧/ }).click()
  const picker = page.locator('.bench .picker--embedded') // the 画面 tab
  await expect(page.getByRole('tab', { name: '画面' })).toHaveAttribute('aria-selected', 'true')
  const tiles = picker.locator('.picker__tile')
  await expect(tiles.first()).toBeVisible()
  const box = await tiles.first().boundingBox()
  expect(box.width).toBeGreaterThan(150) // a fingertip, not a sliver
  await tiles.nth(1).click()
  await tiles.nth(2).click()
  await expect(picker).toContainText('已选 2 帧')
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/picker-attach.png` })
  await picker.getByRole('button', { name: '完成' }).click()
  await expect(page.locator('.bench')).not.toHaveAttribute('data-open', '')
  await expect(page.locator('.composer')).toContainText('F003') // attached to the question

  await page.locator('.composer').getByRole('button', { name: /选帧/ }).click()
  await picker.getByRole('tab', { name: '框选慢放' }).click()
  await tiles.nth(3).click()
  await tiles.nth(4).click()
  await expect(picker.locator('.picker__hint')).toContainText('秒')
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/picker-range.png` })
  await picker.getByRole('button', { name: '慢放这一段' }).click()
  await expect(page.locator('.bench')).not.toHaveAttribute('data-open', '')
  await expect.poll(() => mock.requests.some((r) => /\/replay$/.test(r.path))).toBe(true)
})
