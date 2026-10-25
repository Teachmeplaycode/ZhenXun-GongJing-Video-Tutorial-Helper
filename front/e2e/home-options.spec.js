import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

async function home(page) {
  const mock = new MockApi(page)
  mock.addSession('recent1', { title: '保留位置的最近记录', messages: [] })
  await mock.install()
  await page.goto('/')
  await expect(page.locator('.import-slide')).toBeVisible()
  await expect(page.locator('.recent')).toHaveCount(0)
  await page.evaluate(() => document.fonts.ready)
}

test('home: adding a question animates in place without reloading or moving the heading', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await home(page)
  const timeOrigin = await page.evaluate(() => performance.timeOrigin)
  const frames = await page.evaluate(async () => {
    const read = () => {
      const slide = document.querySelector('.import-slide').getBoundingClientRect()
      return { height: slide.height, top: slide.top, heading: document.querySelector('.home-intro').getBoundingClientRect().top,
        background: document.querySelector('.layer--sculpture').getBoundingClientRect().height, scroll: scrollY }
    }
    const frames = [read()]
    document.querySelector('[aria-controls="import-task"]').click()
    for (let i = 0; i < 35; i++) {
      await new Promise(requestAnimationFrame)
      frames.push(read())
    }
    return frames
  })
  expect(await page.evaluate(() => performance.timeOrigin)).toBe(timeOrigin)
  expect(new Set(frames.map((f) => Math.round(f.height))).size).toBeGreaterThan(4)
  for (const key of ['top', 'heading', 'background', 'scroll']) {
    const values = frames.map((f) => f[key])
    expect(Math.max(...values) - Math.min(...values), key).toBeLessThan(1)
  }
  const question = page.getByRole('textbox', { name: '你想了解什么？' })
  await expect(question).toBeFocused()
  await question.fill('保留这个问题')
  await question.press('Escape')
  await expect(page.getByRole('button', { name: /已添加问题/ })).toBeFocused()
  await expect.poll(async () => (await page.locator('.import-slide').boundingBox()).height).toBeCloseTo(frames[0].height, 0)
  await page.getByRole('button', { name: /已添加问题/ }).click()
  await expect(question).toHaveValue('保留这个问题')
})

test('home: mobile question focus keeps the scroll position and survives rapid toggles', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await home(page)
  const trigger = page.getByRole('button', { name: /添加问题/ })
  await trigger.scrollIntoViewIfNeeded()
  const before = await page.evaluate(() => scrollY)
  await trigger.click()
  const question = page.getByRole('textbox', { name: '你想了解什么？' })
  await expect(question).toBeFocused()
  await expect.poll(() => page.evaluate(() => scrollY)).toBeCloseTo(before, 0)
  await question.fill('手机上的问题')
  await page.evaluate(() => {
    const trigger = document.querySelector('[aria-controls="import-task"]')
    for (let i = 0; i < 4; i++) trigger.click()
  })
  await expect(question).toHaveValue('手机上的问题')
  await question.evaluate((el) => el.setSelectionRange(el.value.length, el.value.length)) // End doesn't move the caret on macOS
  await question.press('Enter')
  await question.press('a')
  await expect(question).toHaveValue('手机上的问题\na')
  await page.locator('#import-task').getByRole('button', { name: '完成', exact: true }).click()
  await expect(page.getByRole('button', { name: /已添加问题/ })).toBeFocused()
  await expect(page.getByRole('textbox', { name: '你想了解什么？' })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
