import { test, expect } from '@playwright/test'
import { MockApi, video } from './mock-api.js'

const examples = [
  { name: 'YouTube watch', platform: 'youtube', label: 'YouTube', link: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
  { name: 'YouTube short link', platform: 'youtube', label: 'YouTube', link: 'https://youtu.be/dQw4w9WgXcQ', id: 'dQw4w9WgXcQ' },
  { name: 'Douyin video', platform: 'douyin', label: '抖音', link: 'https://www.douyin.com/video/7123456789', id: '7123456789' },
  { name: 'Douyin share text', platform: 'douyin', label: '抖音', link: '复制此链接，打开抖音观看视频 https://v.douyin.com/AbCdEf/', id: '7123456789' },
]

for (const example of examples) {
  test(`${example.name}: detected import hint and readable analysis platform`, async ({ page }) => {
    const mock = new MockApi(page)
    const snapshot = mock.snapshot.bind(mock)
    mock.snapshot = (jobId, options = {}) => snapshot(jobId, { ...options,
      v: video({ platform: example.platform, video_id: example.id, canonical_url: example.link }),
    })
    await mock.install()
    await page.goto('/')
    await expect(page.locator('.import-control__field small')).toContainText('YouTube、抖音')
    await expect(page.locator('.import-entry__footer')).toContainText('YouTube · 抖音')
    await page.getByRole('textbox', { name: '视频链接' }).fill(example.link)
    await expect(page.locator('.import-control__field small')).toHaveText(`已识别 ${example.label} 链接 · 直接读取画面，不下载视频`)
    expect(mock.requests.filter((r) => r.method === 'POST' && r.path === '/api/link-jobs')).toEqual([])
    await page.getByRole('button', { name: '解析链接' }).click()
    await expect(page.locator('.hud__step', { hasText: '解析链接' }).locator('.hud__value'))
      .toContainText(`${example.label} · ${example.id}`, { timeout: 30_000 })
    await expect(page.locator('.btn--next:not(.btn--early)')).toBeVisible()
    expect(mock.requests.find((r) => r.method === 'POST' && r.path === '/api/link-jobs').body.url).toBe(example.link)
  })
}

test('platform hints follow edits and preserve the generic link fallback', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  const input = page.getByRole('textbox', { name: '视频链接' })
  const hint = page.locator('.import-control__field small')
  await input.fill('https://youtu.be/dQw4w9WgXcQ')
  await expect(hint).toContainText('已识别 YouTube 链接')
  await input.fill('https://v.douyin.com/AbCdEf/')
  await expect(hint).toContainText('已识别 抖音 链接')
  await input.fill('https://example.org/video')
  await expect(hint).toHaveText('已识别链接 · 直接读取画面，不下载视频')
  await input.fill('尚未粘贴链接')
  await expect(hint).toHaveText('没有识别到链接，请粘贴完整的分享链接')
  await input.clear()
  await expect(hint).toContainText('支持 B 站、视频号、YouTube、抖音分享链接')
})
