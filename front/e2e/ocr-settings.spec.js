import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'
const MODES = [['hybrid', '混合加速'], ['local', '本机处理'], ['server', '服务器处理']]

async function openSettings(page, saved = null) {
  const mock = new MockApi(page)
  await mock.install()
  if (saved) await page.addInitScript((value) => localStorage.setItem('import.sampling', JSON.stringify(value)), saved)
  await page.goto('/')
  await page.locator('.import-entry__sampling').click()
  return mock
}

async function submit(page, mock) {
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await expect.poll(() => mock.requests.find((r) => r.path === '/api/link-jobs')?.body?.sampling).toBeTruthy()
  return mock.requests.find((r) => r.path === '/api/link-jobs').body.sampling
}

test('ocr settings: new imports default to hybrid with the scope explained', async ({ page }) => {
  const mock = await openSettings(page)
  const group = page.getByRole('radiogroup', { name: '画面文字处理位置' })
  await expect(group.getByRole('radio', { name: /混合加速/ })).toBeChecked()
  await expect(page.locator('.sampling__scope')).toContainText('上传、语音转写和 AI 回答仍使用服务器')
  await expect(page.locator('#sampling-mode-hint')).toContainText('服务器接续')
  expect(await submit(page, mock)).toEqual({ preset: 'auto', ocr_mode: 'hybrid' })
})

for (const [key, label] of MODES) {
  test(`ocr settings: ${key} is saved and sent on the next import`, async ({ page }) => {
    const mock = await openSettings(page)
    if (key === 'hybrid') await page.getByRole('radio', { name: /服务器处理/ }).check({ force: true })
    await page.getByRole('radio', { name: new RegExp(label) }).check({ force: true })
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('import.sampling')).ocr_mode)).toBe(key)
    await page.reload()
    await page.locator('.import-entry__sampling').click()
    await expect(page.getByRole('radio', { name: new RegExp(label) })).toBeChecked()
    if (key === 'local') await expect(page.locator('#sampling-mode-hint')).toContainText('保持页面打开')
    expect((await submit(page, mock)).ocr_mode).toBe(key)
  })
}

test('ocr settings: old saved density and overrides survive the hybrid default', async ({ page }) => {
  const old = { preset: 'fine', frames: '96', shots: false, ocr_fps: '1' }
  const mock = await openSettings(page, old)
  await expect(page.getByRole('radio', { name: /混合加速/ })).toBeChecked()
  await expect(page.getByRole('radio', { name: /^精细/ })).toBeChecked()
  await expect(page.getByLabel('关键帧数量')).toHaveValue('96')
  await expect(page.getByLabel('画面文字识别')).toHaveValue('1')
  await expect(page.getByRole('checkbox', { name: /按镜头补帧/ })).not.toBeChecked()
  expect(await submit(page, mock)).toEqual({ preset: 'fine', frames: 96, shots: false, ocr_fps: 1, ocr_mode: 'hybrid' })
})

test('ocr settings: invalid saved processing mode cannot reach the API', async ({ page }) => {
  const mock = await openSettings(page, { preset: 'standard', ocr_mode: 'remote-random' })
  await expect(page.getByRole('radio', { name: /混合加速/ })).toBeChecked()
  expect(await submit(page, mock)).toEqual({ preset: 'standard', ocr_mode: 'hybrid' })
})

test('ocr settings: restoring density leaves the selected OCR mode intact', async ({ page }) => {
  const mock = await openSettings(page, { preset: 'fine', frames: '96', shots: false, ocr_fps: '1', ocr_mode: 'local' })
  await page.getByRole('button', { name: '恢复预设' }).click()
  await expect(page.getByRole('radio', { name: /本机处理/ })).toBeChecked()
  await expect(page.getByLabel('关键帧数量')).toHaveValue('')
  expect(await submit(page, mock)).toEqual({ preset: 'fine', ocr_mode: 'local' })
})

for (const [width, theme] of [[360, 'light'], [390, 'dark'], [430, 'light']]) {
  test(`ocr settings: ${width}px ${theme} has readable choices and full touch targets`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.addInitScript((choice) => localStorage.setItem('gongjing.theme', choice), theme)
    await openSettings(page)
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    const labels = page.locator('.sampling__mode')
    await expect(labels).toHaveCount(3)
    for (const label of await labels.all()) {
      await label.scrollIntoViewIfNeeded()
      const box = await label.boundingBox()
      expect(box.height).toBeGreaterThanOrEqual(44)
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(width)
      expect(await label.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true)
    }
    await expect(page.locator('.sampling__scope')).toBeVisible()
    await page.getByRole('radio', { name: /服务器处理/ }).check({ force: true })
    await expect(page.getByRole('radio', { name: /服务器处理/ })).toBeChecked()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  })
}
