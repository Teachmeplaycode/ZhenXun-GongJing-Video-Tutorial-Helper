import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

// Typed citations (backend modules/agent/evidence.py): each conclusion names its kind of evidence
// and time; the backend checks every citation and a failed one is shown as missing, never as a link.
const LINK = 'https://www.bilibili.com/video/BV1TEST00001'
const TEXT = '先点「报表布局」[原声 00:30-00:40] [画面 00:45]，再选「以表格形式显示」[画面文字 00:46]。'
  + '官方说明 [资料 https://support.example.com/pivot]。这样便于筛选 [推断]。结尾还有 [画面 09:59] 和 [资料 https://invented.example/x]。'
const item = (marker, kind, ok, reason = '') => ({ marker, kind, ok, reason })
const ANSWER = [
  { type: 'assistant.message.delta', delta: TEXT, t: 0.5 },
  { type: 'evidence.checked', t: 0.9, items: [
    item('[原声 00:30-00:40]', 'speech', true), item('[画面 00:45]', 'frame', true), item('[画面文字 00:46]', 'screentext', true),
    item('[资料 https://support.example.com/pivot]', 'source', true), item('[推断]', 'inference', true),
    item('[画面 09:59]', 'frame', false, '超出视频时长（02:00）'), { ...item('[资料 https://invented.example/x]', 'source', false, '这个链接不是本次检索或打开过的资料'), url: 'https://invented.example/x' }],
    summary: { counts: { speech: 1, frame: 2, screentext: 1, source: 2, inference: 1 }, failed: 2, total: 7 } },
  { type: 'run.completed', steps: 1, elapsed_ms: 1000, summary: 'ok', t: 1 },
]

test('evidence: citations show their kind, play their moment, and failed ones are not links', async ({ page }) => {
  const mock = new MockApi(page)
  mock.runs.push(ANSWER)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.locator('.composer__input').fill('第几秒点了哪个按钮')
  await page.locator('.composer__input').press('Enter')

  const answer = page.locator('.msg--assistant').last()
  await expect(answer.locator('.ev-summary')).toContainText('2 条引用缺少可回看的证据')
  await expect(answer.locator('.ev-summary__item')).toHaveText(['画面 2', '原声 1', '画面文字 1', '资料 2', '推断 1'])

  // The chips in the text are hidden until asked for; the choice is remembered for later answers.
  await expect(answer.locator('.streaming-text .ev-chip').first()).toBeHidden()
  await answer.getByRole('button', { name: '显示时间标签' }).click()
  await expect(answer.locator('.streaming-text .ev-chip').first()).toBeVisible()
  expect(await page.evaluate(() => localStorage.getItem('zhenxun.cites.v1'))).toBe('1')

  // A checked moment is a button and opens the cached frames at its start (no original in this mock).
  await answer.getByRole('button', { name: '原声 00:30-00:40' }).click()
  await expect(page.locator('.tl-sheet.is-seeking')).toHaveCount(1)
  await expect(answer.locator('.streaming-text .ev-chip--screentext')).toHaveAttribute('title', /画面里的文字/)

  // An outside source opens as a link, and says it is not the video.
  await expect(answer.getByRole('link', { name: '资料 · support.example.com/pivot' })).toHaveAttribute('title', /不是视频内容/)
  await expect(answer.locator('.streaming-text .ev-chip--inference')).toHaveText('推断')

  // Failed citations: struck through, explained, and not clickable.
  const late = answer.locator('.ev-chip.is-missing', { hasText: '画面 09:59' })
  await expect(late).toHaveAttribute('title', '该结论缺少可回看的证据：超出视频时长（02:00）')
  expect(await late.evaluate((e) => e.tagName)).toBe('SPAN')
  await expect(answer.getByRole('link', { name: /invented/ })).toHaveCount(0)
  await expect(answer.locator('.ev-chip.is-missing', { hasText: '资料' })).toHaveAttribute('title', /不是本次检索/)
})
