import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

test('sampling: the preset (and only the overrides set) goes with the import, and is remembered', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await expect(page.locator('.import-entry__sampling')).toHaveText(/解析设置\s*自动/)
  await page.locator('.import-entry__sampling').click()
  await page.getByRole('radio', { name: /精细/ }).check({ force: true })
  await page.locator('.sampling__advanced summary').click()
  await page.getByLabel('画面文字识别').selectOption('0')
  await expect(page.locator('.import-entry__sampling')).toHaveText(/解析设置\s*精细 · 自定义/)
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await expect.poll(() => mock.requests.find((r) => r.path === '/api/link-jobs')?.body?.sampling).toEqual({ preset: 'fine', ocr_mode: 'hybrid', ocr_fps: 0 })

  await page.reload()
  await expect(page.locator('.import-entry__sampling')).toHaveText(/解析设置\s*精细 · 自定义/)
  await page.locator('.import-entry__sampling').click()
  await page.getByRole('button', { name: '恢复预设' }).click()
  await expect(page.locator('.import-entry__sampling')).toHaveText(/解析设置\s*精细$/)
})

test('sampling: keyframes added for missed shots join the timeline in time order', async ({ page }) => {
  const mock = new MockApi(page)
  mock.shotTimes = [10, 100] // between the 8 uniform frames (7.5 s, 22.5 s … 112.5 s)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.tl-sheet')).toHaveCount(10)
  await expect(page.locator('.timeline__head')).toContainText('10 帧')
  const labels = await page.locator('.tl-sheet').evaluateAll((els) => els.map((e) => e.getAttribute('aria-label')))
  expect(labels.slice(0, 3)).toEqual([expect.stringContaining('00:07.5'), expect.stringContaining('00:10.0'), expect.stringContaining('00:22.5')])
})


test('sampling: automatic is the default without overwriting saved choices', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-entry__sampling').click()
  await expect(page.getByRole('radio', { name: /自动/ })).toBeChecked()
  await page.locator('.sampling__advanced summary').click()
  const shots = page.getByRole('checkbox', { name: /按镜头补帧/ })
  expect(await shots.evaluate((el) => el.indeterminate)).toBe(true)
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await expect.poll(() => mock.requests.find((r) => r.path === '/api/link-jobs')?.body?.sampling).toEqual({ preset: 'auto', ocr_mode: 'hybrid' })
  await page.evaluate(() => localStorage.setItem('import.sampling', JSON.stringify({ preset: 'standard', frames: '', shots: null, ocr_fps: '' })))
  await page.reload()
  await expect(page.locator('.import-entry__sampling')).toHaveText(/解析设置\s*标准$/)
})

for (const width of [360, 390, 430]) {
  test(`sampling: four choices fit at ${width}px with usable touch targets`, async ({ page }) => {
    const mock = new MockApi(page)
    await mock.install()
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/')
    await page.locator('.import-entry__sampling').click()
    const labels = page.locator('.sampling__preset')
    await expect(labels).toHaveCount(4)
    for (const label of await labels.all()) {
      const box = await label.boundingBox()
      expect(box.height).toBeGreaterThanOrEqual(44)
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(width)
    }
    await expect(page.getByRole('radio', { name: /自动/ })).toBeChecked()
  })
}
