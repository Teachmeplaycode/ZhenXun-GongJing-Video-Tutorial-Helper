import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

// Looking back at a cited moment (backend modules/playback): the original when it can be played,
// the cached frames when it can't, and no link at all when there is nothing to show.
const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

async function chat(page, setup) {
  const mock = new MockApi(page)
  setup?.(mock)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.locator('.composer__input').fill('讲了什么')
  await page.locator('.composer__input').press('Enter')
  return mock
}
const chip = (page) => page.locator('.msg--assistant').last().locator('.streaming-text .ts-chip')

test('playback: a cited time plays the original from just before that moment', async ({ page }) => {
  await chat(page, (m) => { m.source = { state: 'original', label: 'bilibili 原视频', message: '点击时间点会在原片里播放' } })
  await expect(page.locator('.evidence-badge')).toHaveText('原片可回看')
  await expect(chip(page)).toHaveAttribute('title', '在原片里播放这一刻')
  await chip(page).click()
  const player = page.getByRole('complementary', { name: /从 00:30 播放/ })
  await expect(player).toBeVisible()
  await expect(player.locator('.source-player__badge')).toHaveText('回看原片')
  await expect.poll(() => player.locator('video').evaluate((v) => v.currentTime), { timeout: 10_000 }).toBeGreaterThan(28)
  await expect(page.locator('.tl-sheet.is-seeking')).toHaveCount(0) // the original, not the cached frames
  await player.getByRole('button', { name: '关闭原片' }).click()
  await expect(player).toBeHidden()
})

test('playback: an original that fails to play offers the cached frames instead', async ({ page }) => {
  await chat(page, (m) => { m.source = { state: 'original', label: '视频号 原视频' }; m.mediaBroken = true })
  await chip(page).click()
  await page.getByRole('button', { name: '改看 00:30 的缓存画面' }).click()
  await expect(page.locator('.timeline')).toHaveAttribute('data-open')
  await expect(page.locator('.tl-sheet.is-seeking')).toHaveCount(1)
})

test('playback: cached evidence is labelled as such; with nothing to show, times are not links', async ({ page }) => {
  const mock = await chat(page)
  await expect(page.locator('.evidence-badge')).toHaveText('仅缓存证据')
  await expect(chip(page)).toHaveAttribute('title', '查看这一刻的缓存画面（原视频不可用）')
  await chip(page).click()
  await expect(page.locator('.timeline')).toHaveAttribute('data-open')
  await expect(page.locator('.source-player')).toHaveCount(0)

  mock.source = { state: 'none', label: '无可回看证据', message: '原视频和抽取的画面都不可用' }
  await page.reload()
  await page.locator('.history-btn, .btn--history').first().click()
  await page.locator('.session-item__open').first().click()
  await expect(page.locator('.evidence-badge')).toHaveText('无可回看证据')
  await expect(page.locator('.msg--assistant .streaming-text .ts-chip')).toHaveCount(0)
  await expect(page.locator('.msg--assistant .streaming-text').last()).toContainText('00:30')
})

test('playback: a kept upload can have its original deleted, after confirming', async ({ page }) => {
  const mock = new MockApi(page)
  mock.source = { state: 'original', label: '本地原文件' }
  await mock.install()
  await page.goto('/')
  await page.locator('input[type=file]').first().setInputFiles({ name: 'clip.mp4', mimeType: 'video/mp4', buffer: Buffer.from('x') })
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.getByRole('button', { name: '删除原视频' }).click()
  await page.getByRole('button', { name: '确认删除' }).click()
  await expect(page.locator('.evidence-badge')).toHaveText('仅缓存证据')
  expect(mock.requests.some((r) => r.method === 'DELETE' && r.path.endsWith('/source'))).toBe(true)
})
