import { test, expect } from '@playwright/test'
import { MockApi, openBench } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'
const initialChapter = { start: 0, end: 120, title: '根据已有画面生成的章节', summary: '画面展示了存储器结构。' }

for (const progress of ['provisional', 'updating']) {
  test(`chapters: ${progress} results stay visible and refresh until settled`, async ({ page }) => {
    const mock = new MockApi(page)
    await mock.install()
    let requests = 0
    let settled = false
    await page.route('**/api/link-jobs/job1/chapters', async (route) => {
      requests += 1
      await route.fulfill({ json: {
        status: 'done',
        chapters: [settled ? { ...initialChapter, title: '存储器层次与访问原理' } : initialChapter],
        summary: '',
        message: progress === 'updating' ? '正在根据新增内容更新章节' : '已根据现有内容生成，后续自动补充',
        provisional: !settled && progress === 'provisional',
        updating: !settled && progress === 'updating',
      } })
    })
    await page.goto('/')
    await page.locator('.import-control__link').fill(LINK)
    await page.locator('.import-control__submit').click()
    await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
    await expect(page.locator('.composer__input')).toBeVisible()
    await openBench(page, /章节/)

    const chapter = page.locator('.chapters__item')
    await expect(chapter).toContainText(initialChapter.title)
    // A finished first pass must keep polling while source evidence is still arriving.
    await expect.poll(() => requests, { timeout: 6000 }).toBeGreaterThan(1)
    await expect(chapter).toContainText(initialChapter.title)
    await expect(page.locator('.chapters').getByRole('status')).toContainText(
      progress === 'updating' ? '正在根据新增内容更新章节' : '已根据现有内容生成，后续自动补充',
    )
    await expect(page.locator('.steps-tab__working')).toHaveCount(0)

    settled = true
    await expect(chapter).toContainText('存储器层次与访问原理')
    await expect(page.locator('.chapters').getByRole('status')).toHaveCount(0)
    const finalRequests = requests
    await page.waitForTimeout(3400)
    expect(requests).toBe(finalRequests)
  })
}

test('chapters: exhausted summary retries keep the chapters and show the incomplete result', async ({ page }) => {
  await new MockApi(page).install()
  let requests = 0
  await page.route('**/api/link-jobs/job1/chapters', async (route) => {
    requests += 1
    await route.fulfill({ json: {
      status: 'done',
      chapters: [initialChapter],
      summary: '',
      message: '部分章节摘要暂未生成，已有章节仍可使用',
      provisional: false,
      updating: false,
      needs_retry: true,
    } })
  })
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
  await openBench(page, /章节/)
  await expect(page.locator('.chapters__item')).toContainText(initialChapter.title)
  await expect(page.locator('.chapters').getByRole('status')).toHaveText('部分章节摘要暂未生成，已有章节仍可使用')
  await page.waitForTimeout(3400)
  expect(requests).toBe(1)
})
