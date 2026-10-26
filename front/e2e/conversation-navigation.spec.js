import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

async function openConversation(page, failed = false) {
  const mock = new MockApi(page)
  const messages = Array.from({ length: 18 }, (_, i) => [
    { role: 'user', content: `镜头问题 ${i + 1}：为什么这样切换？`, status: 'done' },
    { role: 'assistant', content: Array.from({ length: 8 }, (__, n) => `第 ${i + 1} 轮的画面分析 ${n + 1}。镜头从近景切换到全景，保持了运动方向与视觉中心。`).join('\n\n'), status: 'done', events: [] },
  ]).flat()
  if (failed) messages[3].status = 'failed'
  mock.addSession('nav', { title: '镜头讨论', messages })
  await mock.install()
  await page.goto('/')
  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '镜头讨论' }).locator('.session-item__open').click()
  await expect(page.locator('.chat__scroll')).toBeVisible()
  return mock
}
async function openDirectory(page) {
  const rail = page.getByRole('button', { name: '展开对话目录', exact: true })
  if (await rail.isVisible()) await rail.click()
  else await page.getByRole('button', { name: /对话目录.*18 轮/ }).click()
  await expect(page.locator('.turn-directory')).toBeVisible()
}

test('turn navigation: rail jumps only the chat scroller and returns to latest', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1000 })
  await openConversation(page)
  await expect(page.locator('.turn-rail')).toBeVisible()
  await expect(page.locator('.turn-rail__mark')).toHaveCount(18)
  await page.locator('.turn-rail__mark').nth(0).click()
  await expect.poll(() => page.locator('.chat__scroll').evaluate((el) => el.scrollTop)).toBeLessThan(20)
  await expect(page.locator('.turn-rail__mark').nth(0)).toHaveAttribute('aria-current', 'location')
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
  const box = await page.locator('.turn-rail__mark').nth(0).boundingBox()
  expect(box.width).toBeGreaterThanOrEqual(44)
  expect(box.height).toBeGreaterThanOrEqual(44)
  await page.getByRole('button', { name: '回到底部', exact: true }).click()
  await expect(page.locator('.turn-rail__mark').nth(17)).toHaveAttribute('aria-current', 'location')
})

test('turn navigation: selection is explicit, retained, and excludes failed answers', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1000 })
  await openConversation(page, true)
  await openDirectory(page)
  await expect(page.locator('.turn-directory input')).toHaveCount(0)
  await page.getByRole('button', { name: '选择加入笔记', exact: true }).click()
  const boxes = page.locator('.turn-directory__check input')
  await expect(boxes.nth(0)).toBeEnabled()
  await expect(boxes.nth(0)).not.toBeChecked()
  await expect(boxes.nth(1)).toBeDisabled()
  await boxes.nth(0).check()
  await expect(page.locator('.turn-directory__footer')).toContainText('已选 1 轮问答')
  await page.getByRole('button', { name: '退出选材', exact: true }).click()
  await expect(page.locator('.turn-directory input')).toHaveCount(0)
  await page.getByRole('button', { name: '选择加入笔记', exact: true }).click()
  await expect(boxes.nth(0)).toBeChecked()
  await page.getByRole('button', { name: '整理已选问答', exact: true }).click()
  await expect(page.getByRole('tab', { name: '笔记', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.notes-tab')).toContainText('已选 1 轮')
})

test('turn navigation: historical jump stays put when a new answer arrives', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1000 })
  const mock = await openConversation(page)
  const release = mock.holdNextRun()
  await page.locator('.composer__input').fill('再分析一个分镜')
  await page.locator('.composer__input').press('Enter')
  await expect(page.locator('.turn-rail__mark')).toHaveCount(19)
  await page.locator('.turn-rail__mark').nth(0).click()
  await expect.poll(() => page.locator('.chat__scroll').evaluate((el) => el.scrollTop)).toBeLessThan(20)
  release()
  await expect(page.locator('.msg--assistant .msg-footer')).toHaveCount(19)
  await expect.poll(() => page.locator('.chat__scroll').evaluate((el) => el.scrollTop)).toBeLessThan(20)
  await expect(page.locator('.turn-rail__mark').nth(0)).toHaveAttribute('aria-current', 'location')
  const reads = mock.requests.filter((r) => r.path === '/api/sessions/nav' && r.method === 'GET')
  expect(reads.length).toBeLessThanOrEqual(4)
})

for (const width of [360, 390, 430]) test(`turn navigation: ${width}px directory closes after jump`, async ({ page }) => {
  await page.setViewportSize({ width, height: 720 })
  await openConversation(page)
  await expect(page.locator('.turn-rail')).toHaveCount(0)
  await openDirectory(page)
  const first = page.locator('.turn-directory__item').nth(0)
  const box = await first.boundingBox()
  expect(box.height).toBeGreaterThanOrEqual(44)
  await first.click()
  await expect(page.locator('.turn-directory')).toHaveCount(0)
  await expect.poll(() => page.locator('.chat__scroll').evaluate((el) => el.scrollTop)).toBeLessThan(20)
  await expect(page.locator('.chat__message-anchor').nth(0)).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
})
