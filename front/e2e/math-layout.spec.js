import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const answer = [
  String.raw`由罗尔定理得到 $f'(\xi)=0$，并满足 \(a<\xi<b\)。[00:30]`,
  String.raw`$$
\lim_{n\to\infty} n^2\left[\arctan(n+1)-\arctan n\right]=1
$$`,
  String.raw`- 中值点：$x_1<\xi<x_2$。`,
  String.raw`| 条件 | 公式 |
| --- | --- |
| 拉格朗日 | $f(b)-f(a)=f'(\xi)(b-a)$ |`,
  '代码保持原样：`$x^2$`，金额 $20 和 $30。',
  '```latex\n$$x^2$$\n```',
].join('\n\n')

async function openChat(page, { math = true, long = false } = {}) {
  const mock = new MockApi(page)
  const text = (math ? answer : '罗尔定理和拉格朗日定理。') + (long ? '\n\n' + '条件需要结合原片理解。\n\n'.repeat(65) : '')
  mock.addSession('math1', { title: '中值定理课堂', messages: [
    { role: 'user', content: '整理这节课的定理', status: 'done' },
    { role: 'assistant', content: text, status: 'done', events: [] },
  ] })
  await mock.install()
  await page.goto('/')
  await page.locator('.btn--history').click()
  await page.locator('.session-item', { hasText: '中值定理课堂' }).locator('.session-item__open').click()
  await expect(page.locator('.composer__input')).toBeVisible()
  return mock
}

test('math: chat renders inline, display, list and table formulas while code, prices and timestamps stay intact', async ({ page }) => {
  await openChat(page)
  const body = page.locator('.msg--assistant .streaming-text')
  await expect(body.locator('.katex')).toHaveCount(5)
  await expect(body.locator('.katex-display')).toHaveCount(1)
  await expect(body.locator('.katex-error')).toHaveCount(0)
  await expect(body.locator('math')).toHaveCount(5)
  await expect(body.locator('.md-code')).toHaveText('$x^2$')
  await expect(body.locator('.md-pre code')).toHaveText('$$x^2$$')
  await expect(body).toContainText('金额 $20 和 $30')
  await expect(body.locator('.ts-chip')).toHaveText('00:30')
})

for (const width of [390, 1108]) test(`layout: return-to-bottom clears suggestion pills and resized input at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 780 })
  await openChat(page, { math: false, long: true })
  const scroll = page.locator('.chat__scroll')
  await scroll.evaluate((node) => { node.scrollTop = 0; node.dispatchEvent(new Event('scroll')) })
  const jump = page.getByRole('button', { name: '回到底部', exact: true })
  await expect(jump).toBeVisible()
  await expect(page.locator('.composer__pills')).toBeVisible()
  const assertClear = async () => {
    const button = await jump.boundingBox()
    const composer = await page.locator('.composer').boundingBox()
    const reading = await scroll.boundingBox()
    expect(button.y + button.height).toBeLessThanOrEqual(composer.y - 6)
    expect(button.y).toBeGreaterThanOrEqual(reading.y)
    expect(button.height).toBeGreaterThanOrEqual(44)
  }
  await assertClear()
  await page.locator('.composer__input').fill('第一行\n第二行\n第三行\n第四行')
  await assertClear()
  await page.locator('.composer__input').fill('')
  await assertClear()
  await jump.click()
  await expect(jump).toHaveCount(0)
})

test('math: note editor renders formulas in prose and legacy wrapped formula fields', async ({ page }) => {
  const mock = new MockApi(page)
  mock.notes = { status: 'done', note: { title: '罗尔定理', summary: String.raw`区间条件 $a<b$`, sections: [{
    id: 's1', title: '结论', start: 0, end: 60, points: [String.raw`存在 $\xi\in(a,b)$`],
    formulas: [String.raw`$$f'(\xi)=0$$`, String.raw`\[\frac{1}{x^2+1}\]`], examples: [String.raw`代入 \(x=1\)`], figures: [],
  }] } }
  await mock.install()
  await page.goto('/#/notes/math1')
  const board = page.locator('.nb-world')
  await expect(board.locator('.katex')).toHaveCount(5)
  await expect(board.locator('.katex-error')).toHaveCount(0)
  await expect(board.locator('.nb-formula .katex-display')).toHaveCount(2)
})
