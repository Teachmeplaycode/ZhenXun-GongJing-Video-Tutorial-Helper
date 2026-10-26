import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'
const NOTE = '重点检查罗尔定理的证明条件。'

async function chat(page, setup) {
  const mock = new MockApi(page)
  setup?.(mock)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early), .processing__continue').first().click()
  await expect(page.locator('.composer__input')).toBeVisible()
  return mock
}
async function pick(page, key) {
  await page.locator('.composer__input').fill(`/${key}`)
  await page.locator('.composer__input').press('Enter')
}
const command = (page) => page.locator('.composer__command')

test('commands: choosing a task creates a token and leaves template text out of the user input', async ({ page }) => {
  await chat(page)
  await pick(page, '核实')
  await expect(page.locator('.composer__input')).toHaveValue('')
  await expect(command(page)).toContainText('核实')
  await expect(page.locator('.composer__ghost')).toHaveCount(0)
  await page.getByRole('button', { name: '查看指令', exact: true }).click()
  await expect(page.locator('.composer')).toContainText('核实视频里的主要说法是否正确')
  await expect(page.locator('.composer__input')).toHaveValue('')
  await page.locator('.composer__input').fill(NOTE)
  await page.locator('.bench__handle').click()
  await page.screenshot({ path: `/tmp/zhenxun-command-qa/desktop-${test.info().project.name}.png`, fullPage: false })
})

test('commands: the command menu and task changes preserve the person\'s own words', async ({ page }) => {
  await chat(page)
  const input = page.locator('.composer__input')
  await input.fill(NOTE)
  await page.getByRole('button', { name: '常用任务', exact: true }).click()
  await page.locator('.slash-menu__item', { hasText: '/核实' }).click()
  await expect(input).toHaveValue(NOTE)
  await page.getByRole('button', { name: '常用任务', exact: true }).click()
  await page.locator('.slash-menu__item', { hasText: '/总结' }).click()
  await expect(input).toHaveValue(NOTE)
  await expect(command(page)).toContainText('总结')
  await page.getByRole('button', { name: /移除任务/ }).click()
  await expect(input).toHaveValue(NOTE)
  await expect(command(page)).toHaveCount(0)
})

test('commands: the request and sent bubble retain command identity separately from user text', async ({ page }) => {
  const mock = await chat(page)
  await pick(page, '核实')
  await page.locator('.composer__input').fill(NOTE)
  await page.locator('.composer__input').press('Enter')
  await expect.poll(() => mock.runsSent().length).toBe(1)
  expect(mock.runsSent()[0]).toMatchObject({ question: NOTE, command: '核实' })
  const user = page.locator('.msg--user').last()
  await expect(user.locator('.message-command')).toContainText('核实')
  await expect(user.locator('.bubble__text')).toHaveText(NOTE)
  await expect(user.locator('.bubble__text')).not.toContainText('核实视频里的主要说法')
})


test('commands: a skill can run without pretending its instruction was user-written text', async ({ page }) => {
  const mock = await chat(page)
  await pick(page, '科普核查')
  await expect(command(page)).toContainText('技能')
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect.poll(() => mock.runsSent().length).toBe(1)
  expect(mock.runsSent()[0]).toMatchObject({ question: '', command: '科普核查' })
  const user = page.locator('.msg--user').last()
  await expect(user.locator('.message-command')).toContainText('科普核查')
  await expect(user).not.toContainText('用科普核查技能，逐条核查')
  await expect(command(page)).toHaveCount(0)
  await expect(page.locator('.composer__input')).toHaveValue('')
})

test('commands: all ten menu entries select a task without injecting their templates', async ({ page }) => {
  await chat(page)
  for (const key of ['总结', '时间线', '卡点', '科普核查', '反诈识别', '核实', '论文', '细看', '慢放', 'GIF']) {
    await pick(page, key)
    await expect(command(page)).toHaveAttribute('data-command', key)
    await expect(page.locator('.composer__input')).toHaveValue('')
  }
})

test('commands: a selected task disables inline ghost text but ordinary questions still work', async ({ page }) => {
  const mock = await chat(page, (api) => { api.completion = '不应该混入的自动补全' })
  await pick(page, '核实')
  await page.locator('.composer__input').fill('重点检查')
  await page.waitForTimeout(650)
  await expect(page.locator('.composer__ghost')).toHaveCount(0)
  await page.getByRole('button', { name: '移除任务', exact: true }).click()
  await page.locator('.composer__input').fill('这是普通问题')
  await page.locator('.composer__input').press('Enter')
  await expect.poll(() => mock.runsSent().length).toBe(1)
  expect(mock.runsSent()[0].question).toBe('这是普通问题')
  expect(mock.runsSent()[0].command || null).toBeNull()
  await expect(page.locator('.msg--user .message-command')).toHaveCount(0)
})

test('commands: IME Enter does not choose or submit and Escape leaves the typed text', async ({ page }) => {
  const mock = await chat(page)
  const input = page.locator('.composer__input')
  await input.fill('/科')
  await expect(page.locator('.slash-menu')).toBeVisible()
  await input.evaluate((element) => element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, isComposing: true, keyCode: 229 })))
  await expect(page.locator('.slash-menu')).toBeVisible()
  await expect(command(page)).toHaveCount(0)
  expect(mock.runsSent()).toEqual([])
  await input.press('Escape')
  await expect(page.locator('.slash-menu')).toHaveCount(0)
  await expect(input).toHaveValue('/科')
  await input.fill(NOTE)
  await page.getByRole('button', { name: '常用任务', exact: true }).click()
  await input.press('Escape')
  await expect(input).toHaveValue(NOTE)
  await expect(page.locator('.slash-menu')).toHaveCount(0)
})

test('commands: Backspace removes a token only when the user input is empty', async ({ page }) => {
  await chat(page)
  await pick(page, '总结')
  const input = page.locator('.composer__input')
  await input.fill('要点')
  await input.press('Backspace')
  await expect(input).toHaveValue('要')
  await expect(command(page)).toHaveAttribute('data-command', '总结')
  await input.fill('')
  await input.press('Backspace')
  await expect(command(page)).toHaveCount(0)
  await expect(input).toBeFocused()
})

test('commands: regeneration retains the task, custom question, frame and tool settings', async ({ page }) => {
  const mock = await chat(page)
  await pick(page, '核实')
  await page.locator('.chip-btn', { hasText: '联网' }).click()
  await page.locator('.chip-btn', { hasText: '论文' }).click()
  await page.locator('.tl-sheet').nth(2).dispatchEvent('click')
  await expect(page.locator('.tl-sheet.is-selected')).toHaveCount(1)
  await page.locator('.composer__input').fill(NOTE)
  await page.locator('.composer__input').press('Enter')
  await expect(page.locator('.msg--assistant .msg-footer').last()).toBeVisible()
  await page.getByRole('button', { name: '重新回答', exact: true }).last().click()
  await expect.poll(() => mock.runsSent().length).toBe(2)
  for (const body of mock.runsSent()) {
    expect(body).toMatchObject({ question: NOTE, command: '核实', web: false, papers: false, scope: { type: 'frames', frames: [2] } })
  }
  await expect(page.locator('.msg--user .message-command')).toHaveCount(2)
})

test('commands: reopening history restores task metadata and regeneration does not lose it', async ({ page }) => {
  const mock = new MockApi(page)
  mock.addSession('past', { title: '有任务标签的会话', messages: [
    { role: 'user', content: '历史普通问题', frames: [] },
    { role: 'assistant', content: '普通回答', status: 'done', events: [] },
    { role: 'user', content: NOTE, command: '核实', web: false, papers: true, frames: [2], images: [] },
    { role: 'assistant', content: '历史核实回答', status: 'done', events: [] },
  ] })
  await mock.install()
  await page.goto('/')
  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '有任务标签的会话' }).locator('.session-item__open').click()
  const users = page.locator('.msg--user')
  await expect(users).toHaveCount(2)
  await expect(users.first().locator('.message-command')).toHaveCount(0)
  await expect(users.last().locator('.message-command')).toContainText('核实')
  await expect(users.last().locator('.bubble__text')).toHaveText(NOTE)
  await page.getByRole('button', { name: '重新回答', exact: true }).last().click()
  await expect.poll(() => mock.runsSent().length).toBe(1)
  expect(mock.runsSent()[0]).toMatchObject({ question: NOTE, command: '核实', web: false, papers: true, scope: { type: 'frames', frames: [2] } })
})

test('commands: a custom time is sent as user text with the selected slow-motion task', async ({ page }) => {
  const mock = await chat(page)
  await pick(page, '慢放')
  await page.locator('.composer__input').fill('重点看 01:00 到 01:05，观察手部动作。')
  await page.locator('.composer__input').press('Enter')
  await expect.poll(() => mock.runsSent().length).toBe(1)
  expect(mock.runsSent()[0]).toMatchObject({ question: '重点看 01:00 到 01:05，观察手部动作。', command: '慢放' })
  expect(mock.runsSent()[0].question).not.toContain('00:00')
})

test('commands: the GIF task still opens the local clip studio instead of asking the model', async ({ page }) => {
  const mock = await chat(page)
  await pick(page, 'GIF')
  await page.locator('.composer__input').fill('00:10 到 00:14')
  await page.locator('.composer__input').press('Enter')
  await expect(page.locator('.clip-studio')).toBeVisible()
  await expect(page.locator('.clip-studio__readout')).toContainText('起点 00:10.0')
  await expect(page.locator('.clip-studio__readout')).toContainText('终点 00:14.0')
  await expect.poll(() => mock.studios.length).toBe(1)
  expect(mock.studios[0]).toMatchObject({ command: 'GIF', text: '00:10 到 00:14', start: 10, end: 14, format: 'gif' })
  expect(mock.studios[0].text).not.toContain('我要这段的 GIF')
  await expect(page.locator('.msg--user .message-command')).toHaveAttribute('data-command', 'GIF')
  await expect(page.locator('.msg--user .bubble__text')).toHaveText('00:10 到 00:14')
  expect(mock.runsSent()).toEqual([])
})

test('commands: empty-supplement GIF history restores the task token and its clip studio', async ({ page }) => {
  const mock = new MockApi(page)
  mock.addSession('gifpast', { title: '无补充文字的 GIF 任务', messages: [
    { role: 'assistant', content: '', status: 'done', manual: 'clip', request: '', command: 'GIF', range: [10, 14], format: 'gif' },
  ] })
  await mock.install()
  await page.goto('/')
  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '无补充文字的 GIF 任务' }).locator('.session-item__open').click()
  const user = page.locator('.msg--user')
  await expect(user).toHaveCount(1)
  await expect(user.locator('.message-command')).toHaveAttribute('data-command', 'GIF')
  await expect(user.locator('.bubble__text')).toHaveCount(0)
  await expect(user).not.toContainText('我要这段的 GIF')
  await expect(page.locator('.clip-studio')).toBeVisible()
  await expect(page.locator('.clip-studio__readout')).toContainText('起点 00:10.0')
  await expect(page.locator('.clip-studio__readout')).toContainText('终点 00:14.0')
  expect(mock.runsSent()).toEqual([])
})

for (const [width, theme] of [[360, 'light'], [390, 'dark'], [430, 'light']]) {
  test(`commands: ${width}px ${theme} keeps task, preview and user text separate`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.emulateMedia({ colorScheme: theme })
    await chat(page)
    await pick(page, '科普核查')
    await page.locator('.composer__input').fill(NOTE)
    const token = command(page)
    await expect(token).toContainText('科普核查')
    for (const button of [page.getByRole('button', { name: '查看指令', exact: true }), page.getByRole('button', { name: '移除任务', exact: true })]) {
      const box = await button.boundingBox()
      expect(box.height).toBeGreaterThanOrEqual(44)
      expect(box.width).toBeGreaterThanOrEqual(44)
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(width)
    }
    await page.getByRole('button', { name: '查看指令', exact: true }).click()
    await expect(page.locator('.composer__instruction')).toBeVisible()
    await expect(page.locator('.composer__input')).toHaveValue(NOTE)
    const preview = await page.locator('.composer__instruction').boundingBox()
    const input = await page.locator('.composer__input').boundingBox()
    expect(preview.y + preview.height).toBeLessThanOrEqual(input.y + 1)
    expect(await page.locator('.composer').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true)
    await page.screenshot({ path: `/tmp/zhenxun-command-qa/settings-${width}-${theme}.png`, fullPage: false })
  })
}
