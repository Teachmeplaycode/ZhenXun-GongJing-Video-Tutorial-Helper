import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { MockApi, replayAnswer, researchAnswer } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

async function start(page, setup) {
  const mock = new MockApi(page)
  setup?.(mock)
  await mock.install()
  await page.goto('/')
  return mock
}

// Paste a link, let the (mock) job finish, and enter the chat.
async function enterChat(page) {
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
}

async function ask(page, question) {
  await page.locator('.composer__input').fill(question)
  await page.locator('.composer__input').press('Enter')
}

const lastAnswer = (page) => page.locator('.msg--assistant').last()

test('link → analysis → chat', async ({ page }) => {
  await start(page)
  await page.locator('.import-control__link').fill(LINK)
  await expect(page.locator('.import-control__submit')).toHaveText(/解析链接/)
  await page.locator('.import-control__submit').click()
  const next = page.locator('.btn--next:not(.btn--early)')
  await expect(next).toBeVisible({ timeout: 30_000 }) // after the 2.4 s minimum and the mask's exit
  await expect(page.locator('.hud__step', { hasText: '语音转写' })).toContainText('12 句')
  await expect(page.locator('.hud__step', { hasText: '抓取关键帧' })).toContainText('8 / 8')
  await next.click()
  await expect(page.locator('.chat__empty h1')).toHaveText('关于这段视频，你想知道什么？')
  await expect(page.locator('.tl-sheet')).toHaveCount(8)
})

test('a failed link is explained on the import screen', async ({ page }) => {
  await start(page, (m) => { m.linkError = { code: 'not_found', message: '视频不存在或已删除', retryable: false } })
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await expect(page.locator('.field-error')).toHaveText('视频不存在或已删除')
})

test('uploading a local file runs the same flow', async ({ page }) => {
  const mock = await start(page)
  await page.locator('input[type=file]').setInputFiles(fileURLToPath(new URL('./fixtures/clip.mp4', import.meta.url)))
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click()
  await expect(page.locator('.composer__input')).toBeVisible()
  expect(mock.requests.some((r) => r.method === 'POST' && r.path === '/api/videos')).toBe(true)
})

test('an answer shows its steps inline, then the text, sources and footer', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  const release = mock.holdNextRun()
  await ask(page, '柚子会影响药物吗？帮我查一下')

  // While the run is held, the answer is a working step group and the stop button replaces send.
  await expect(lastAnswer(page).locator('.step-group[data-working]')).toBeVisible()
  await expect(page.locator('button[aria-label="停止"]')).toBeVisible()
  release()

  const answer = lastAnswer(page)
  await expect(answer.locator('.msg-footer__meta')).toContainText('4 步') // model rounds are not listed as steps
  await expect(answer.locator('.step-group')).toContainText('执行了 4 步')
  // Steps come before the text, as they happened.
  const order = await answer.locator('.bubble--assistant > *').evaluateAll((els) => els.map((e) => e.className))
  expect(order.findIndex((c) => c.includes('step-group'))).toBeLessThan(order.findIndex((c) => c.includes('streaming-text')))

  await expect(answer.locator('.streaming-text strong')).toHaveText('CYP3A4')
  await expect(answer.locator('.streaming-text .ts-chip')).toHaveText('00:30')
  await expect(answer.locator('.md-link')).toHaveAttribute('href', 'https://www.fda.gov/grapefruit')
  await expect(answer.locator('.source-card')).toHaveCount(1)
  await expect(answer.locator('.source-card__title')).toHaveText("Grapefruit Juice and Some Drugs Don't Mix")

  // Narration before the tool call ("我来查一下资料。") stayed out of the answer.
  await expect(answer.locator('.streaming-text')).not.toContainText('我来查一下资料')
  await answer.locator('.step-group .thought-line__head').click()
  await expect(answer.locator('.step__mark[data-kind="web"]').first()).toBeVisible() // each step shows its kind
  await page.screenshot({ path: 'test-results/chat-steps.png' })
})

test('a search step opens to verdicts per result', async ({ page }) => {
  await start(page)
  await enterChat(page)
  await ask(page, '查一下资料')
  const answer = lastAnswer(page)
  await expect(answer.locator('.msg-footer')).toBeVisible()
  await answer.locator('.step-group .thought-line__head').click()
  await answer.locator('.step__row', { hasText: '联网搜索' }).click()
  await expect(answer.locator('.viz-result')).toHaveCount(3)
  await expect(answer.locator('.viz-stamp')).toHaveText(['可靠', '存疑', '无关'])
  await expect(answer.locator('.viz-result[data-drop]')).toHaveCount(1)
  await answer.locator('.step__row', { hasText: '判断是否需要查资料' }).click()
  await expect(answer.locator('.viz-meter__value')).toHaveText('需要查资料 0.82')
})

test('the 联网 switch travels with the question', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  await ask(page, '第一个问题')
  await expect(lastAnswer(page).locator('.msg-footer')).toBeVisible()
  await page.locator('.chip-btn', { hasText: '联网' }).click()
  await expect(page.locator('.chip-btn', { hasText: '联网' })).toHaveAttribute('aria-pressed', 'false')
  await ask(page, '第二个问题')
  await expect(page.locator('.bubble__options').last()).toHaveText('不联网')
  await expect.poll(() => mock.runsSent().length).toBe(2)
  const [first, second] = mock.runsSent()
  expect([first.web, first.papers]).toEqual([true, true])
  expect([second.web, second.papers]).toEqual([false, true])
})

test('"/" opens the task menu and selects a task separately from user text', async ({ page }) => {
  await start(page)
  await enterChat(page)
  const input = page.locator('.composer__input')
  await input.fill('/')
  await expect(page.locator('.slash-menu__item')).toHaveCount(10)
  await input.press('ArrowDown')
  await input.press('Enter')
  await expect(input).toHaveValue('')
  await expect(page.locator('.composer__command')).toHaveAttribute('data-command', '时间线')
  await expect(page.locator('.slash-menu')).toHaveCount(0)
  await input.fill('/核')
  await expect(page.locator('.slash-menu__item')).toHaveText([/科普核查/, /核实/])
  await input.fill('/慢放')
  await input.press('Enter')
  await expect(input).toHaveValue('')
  await expect(page.locator('.composer__command')).toHaveAttribute('data-command', '慢放')
})

test('the timeline folds away, remembers it, and opens for 选帧 and for times', async ({ page }) => {
  await start(page)
  await enterChat(page)
  const timeline = page.locator('.timeline')
  await expect(timeline).toHaveAttribute('data-open')
  await page.locator('.timeline__fold').click()
  await expect(timeline).not.toHaveAttribute('data-open')
  expect(await page.evaluate(() => localStorage.getItem('timeline.open'))).toBe('0')

  await page.locator('.chip-btn', { hasText: '选帧' }).click()
  await expect(timeline).toHaveAttribute('data-open')

  await page.locator('.timeline__fold').click()
  await ask(page, '讲了什么')
  await lastAnswer(page).locator('.streaming-text .ts-chip').click()
  await expect(timeline).toHaveAttribute('data-open')
  await expect(page.locator('.tl-sheet.is-seeking')).toHaveCount(1)
})

test('stopping an answer marks it stopped', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  const release = mock.holdNextRun()
  await ask(page, '讲了什么')
  await page.locator('button[aria-label="停止"]').click()
  await expect(lastAnswer(page).locator('.bubble__error')).toHaveText('已停止')
  await expect(page.locator('button[aria-label="发送"]')).toBeVisible()
  release()
})

test('regenerate asks the same question again', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  await ask(page, '同一个问题')
  await expect(lastAnswer(page).locator('.msg-footer')).toBeVisible()
  await lastAnswer(page).locator('button[aria-label="重新回答"]').click()
  await expect.poll(() => mock.runsSent().map((b) => b.question)).toEqual(['同一个问题', '同一个问题'])
  await expect(page.locator('.msg--assistant')).toHaveCount(2)
})

test('a clip studio card is saved with its session and comes back on reopening', async ({ page }) => {
  const mock = await start(page, (m) => {
    m.addSession('clip1', {
      title: '有截取卡片的会话',
      messages: [
        { role: 'user', content: '第几步？', status: 'done', frames: [] },
        { role: 'assistant', content: '第 2 步。', status: 'done', events: [] },
        { role: 'assistant', content: '', status: 'done', manual: 'clip', request: '把 00:54 到 00:58 做成表情包 GIF', range: [54, 58], format: 'gif' },
      ],
    })
  })
  await enterChat(page)
  await page.locator('.composer__input').fill('把 00:10 到 00:14 做成表情包 GIF')
  await page.locator('.composer__input').press('Enter')
  await expect(page.locator('.clip-studio')).toBeVisible()
  await expect.poll(() => mock.studios).toEqual([{ job: 'job1', text: '把 00:10 到 00:14 做成表情包 GIF', start: 10, end: 14, format: 'gif' }])

  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '有截取卡片的会话' }).locator('.session-item__open').click()
  const card = page.locator('.clip-studio')
  await expect(card).toHaveCount(1)
  await expect(card.locator('.clip-studio__readout')).toContainText('起点 00:54.0')
  await expect(page.locator('.msg--user .bubble__text').last()).toHaveText('把 00:54 到 00:58 做成表情包 GIF')
})

test('history reopens saved sessions, old and new answer formats', async ({ page }) => {
  await start(page, (m) => {
    const events = researchAnswer().filter((e) => e.type !== 'assistant.message.delta')
    // New format: text deltas saved in order with the tool events.
    m.addSession('new1', {
      title: '新格式会话',
      messages: [
        { role: 'user', content: '新的问题', status: 'done', frames: [] },
        { role: 'assistant', content: '新格式的回答', status: 'done', events: [...events.slice(0, -1), { type: 'assistant.message.delta', delta: '新格式的回答', t: 7 }, events.at(-1)] },
      ],
    })
    // Old format (before 2026-10-15): no deltas in the events, just the content.
    m.addSession('old1', {
      title: '旧格式会话',
      messages: [
        { role: 'user', content: '旧的问题', status: 'done', frames: [] },
        { role: 'assistant', content: '旧格式的回答', status: 'done', events },
      ],
    })
  })
  await page.locator('.btn--history').click()
  await expect(page.locator('.history .session-item')).toHaveCount(2)

  await page.locator('.history .session-item', { hasText: '旧格式会话' }).locator('.session-item__open').click()
  await expect(lastAnswer(page).locator('.streaming-text')).toHaveText('旧格式的回答')
  await expect(lastAnswer(page).locator('.step-group')).toContainText('执行了 4 步')

  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '新格式会话' }).locator('.session-item__open').click()
  await expect(lastAnswer(page).locator('.streaming-text')).toHaveText('新格式的回答')
  await expect(page.locator('.msg--user .bubble__text')).toHaveText('新的问题')
})

test('accounts: scan a QR code to log in, the status updates', async ({ page }) => {
  const mock = await start(page)
  await page.getByRole('button', { name: '账号' }).click()
  const bili = page.locator('.account-card', { hasText: 'B 站' })
  await expect(bili.locator('.viz-stamp')).toHaveText('未登录')
  await expect(page.locator('.account-card', { hasText: '腾讯元宝' })).toContainText('来自 backend/.env')
  await bili.getByRole('button', { name: '扫码登录' }).click()
  await expect(bili.locator('.qr-login__code img')).toBeVisible()
  await expect(bili.locator('.qr-login__hint')).toHaveText('用 B 站 App 扫码登录')
  await expect(bili.locator('.qr-login__veil')).toHaveText('已扫码', { timeout: 5000 })
  await expect(bili.locator('.viz-stamp')).toHaveText('已登录 · 测试用户', { timeout: 5000 })
  await expect(bili.locator('.qr-login')).toHaveCount(0)
  await expect(bili).toContainText('来自 扫码登录')
  // Cookie values are never sent to the page, only status.
  expect(mock.requests.filter((r) => r.path.startsWith('/api/accounts')).every((r) => !JSON.stringify(r.body || '').includes('SESSDATA'))).toBe(true)
})

test('a 视频号 link without a 元宝 login offers to scan', async ({ page }) => {
  await start(page, (mock) => {
    mock.linkError = { code: 'login_required', message: '解析视频号需要登录腾讯元宝：点右上角「账号」用微信扫码登录' }
  })
  await page.locator('.import-control__link').fill('https://weixin.qq.com/sph/AbCdEf')
  await page.locator('.import-control__submit').click()
  await page.locator('.field-error__action').click()
  await expect(page.locator('.account-card').first()).toContainText('腾讯元宝')
})

test('the web demo has no platform logins', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1')) // past the first-visit guide
  await start(page, (mock) => {
    mock.publicDemo = true
    mock.member = { name: '评委1', questions: { used: 0, limit: 10 }, imports: { used: 0, limit: 3 } }
    mock.linkError = { code: 'login_required', message: '解析视频号需要登录腾讯元宝：点右上角「账号」用微信扫码登录' }
  })
  await expect(page.locator('.btn--theme')).toBeVisible()
  await expect(page.getByRole('button', { name: '账号', exact: true })).toHaveCount(0) // the shared logins; 平台账号 is one's own
  await expect(page.locator('.import-entry')).toContainText('支持 B 站、抖音、小红书、快手、视频号')
  await page.locator('.import-control__link').fill('https://weixin.qq.com/sph/AbCdEf')
  await page.locator('.import-control__submit').click()
  await expect(page.locator('.field-error')).toBeVisible()
  await expect(page.locator('.field-error__action')).toHaveCount(0)
})

test('the web demo: importing asks for an account, then shows what is left today', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1')) // past the first-visit guide
  await start(page, (mock) => { mock.publicDemo = true; mock.oauth = ['github'] })
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  const register = page.getByRole('dialog', { name: '注册账号' })
  await expect(register).toContainText('登录后才能导入视频和提问')
  await expect(register.getByRole('link', { name: '用 GitHub 登录' })).toHaveAttribute('href', /\/api\/auth\/github\/start$/)
  await register.getByLabel('用户名').fill('评委1')
  await register.getByLabel(/密码/).fill('secret1')
  await register.getByRole('button', { name: '注册', exact: true }).click()
  await expect(page.locator('.member-chip')).toContainText('评委1')
  await expect(page.locator('.member-chip')).toContainText('今日提问 10/10')
  await page.locator('.member-chip').click()
  const mine = page.getByRole('dialog', { name: '我的' })
  await expect(mine).toContainText('今天的额度')
  await mine.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
})

test('the web demo greets a first visit with the mascot guide, once; 文档 can replay it', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' }) // let the snake crawl
  await start(page, (mock) => { mock.publicDemo = true })
  const guide = page.getByRole('dialog', { name: '新手引导' })
  await expect(guide).toContainText('你好，我是帧寻的小蛇')
  if (process.env.GUIDE_SHOTS) await page.screenshot({ path: `${process.env.GUIDE_SHOTS}/guide-1.png` })
  await guide.getByRole('button', { name: /下一步/ }).click()
  await expect(guide).toContainText('第一步：导入视频')
  await expect(guide.locator('.guide__snake img')).toHaveAttribute('src', /crawl-right\.webp$/)
  if (process.env.GUIDE_SHOTS) await page.screenshot({ path: `${process.env.GUIDE_SHOTS}/guide-2-crawl.png` })
  await expect(guide.locator('.guide__snake img')).toHaveAttribute('src', /think\.webp$/)
  await guide.getByRole('button', { name: /下一步/ }).click()
  await guide.getByRole('button', { name: /下一步/ }).click()
  await expect(guide.locator('.ev-chip--frame')).toHaveText('画面 00:56')
  if (process.env.GUIDE_SHOTS) await page.screenshot({ path: `${process.env.GUIDE_SHOTS}/guide-4.png` })
  await guide.getByRole('button', { name: /下一步/ }).click()
  await guide.getByRole('button', { name: '注册并开始' }).click()
  await expect(page.getByRole('dialog', { name: '注册账号' })).toBeVisible()
  await page.getByRole('dialog', { name: '注册账号' }).getByRole('button', { name: '关闭' }).click()

  await page.reload()
  await expect(page.locator('.import-control__link')).toBeVisible()
  await expect(guide).toHaveCount(0) // seen once: not again
  await page.getByRole('button', { name: '文档' }).click()
  const docs = page.getByRole('dialog', { name: '使用文档' })
  await expect(docs).toContainText('证据标签怎么看')
  if (process.env.GUIDE_SHOTS) await page.screenshot({ path: `${process.env.GUIDE_SHOTS}/docs.png` })
  await docs.getByRole('button', { name: '重新看新手引导' }).click()
  await expect(guide).toBeVisible()
})

test('the web demo: a signed-in person links their own platform login by QR only', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1'))
  await start(page, (mock) => {
    mock.publicDemo = true
    mock.member = { name: '评委1', questions: { used: 0, limit: 10 }, imports: { used: 0, limit: 3 } }
  })
  await page.locator('.member-chip').click()
  await page.getByRole('dialog', { name: '我的' }).getByRole('button', { name: /平台账号/ }).click()
  const drawer = page.getByRole('dialog', { name: '平台账号' })
  await expect(drawer).toContainText('只用于你自己导入的视频')
  const bili = drawer.locator('.account-card', { hasText: 'B 站' })
  await expect(bili.getByRole('button', { name: '扫码绑定' })).toBeVisible()
  await expect(drawer.getByRole('button', { name: '手动粘贴 Cookie' })).toHaveCount(0)
})

test('the web demo: an owner sees the site\'s spend today against its cap; others are told 今日额度已满', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1'))
  await start(page, (mock) => {
    mock.publicDemo = true
    mock.member = { name: 'linyi', plan: 'owner', questions: { used: 3, limit: null }, imports: { used: 1, limit: null },
      spend: { day: '2026-10-23', limit: 10, yuan: 10.4, kinds: { llm: { yuan: 9.9, units: 1, calls: 40 }, asr: { yuan: 0.5, units: 1, calls: 3 } } } }
  })
  await page.locator('.member-chip').click()
  const mine = page.getByRole('dialog', { name: '我的' })
  await expect(mine).toContainText('网站今日花费')
  await expect(mine).toContainText('模型 ¥9.90 · 语音识别 ¥0.50')
  await expect(mine).toContainText('¥10.40 / ¥10')
  await expect(mine).toContainText('已到上限')
})

test('the web demo: 先用示例视频体验 lists finished tutorials and opens one at once', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1'))
  await start(page, (mock) => {
    mock.publicDemo = true
    mock.addSession('tut1', { title: 'Excel VLOOKUP 教程', messages: [] })
    mock.addSession('tut2', { title: 'PS 抠图教程', messages: [] })
    mock.samples = ['tut1', 'tut2']
  })
  await page.getByRole('button', { name: /先用示例视频体验/ }).click()
  const list = page.getByRole('list', { name: '示例视频' })
  await expect(list.locator('.sample-card__title')).toHaveText(['Excel VLOOKUP 教程', 'PS 抠图教程'])
  await list.getByRole('button', { name: /PS 抠图教程/ }).click()
  await expect(page.locator('.composer__input')).toBeVisible()
  await expect(page.locator('.header__title, .app-header, body')).toContainText('PS 抠图教程')
})

test('the web demo: one click to try it as a guest', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1'))
  await start(page, (mock) => { mock.publicDemo = true })
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByRole('button', { name: /游客体验/ }).click()
  await expect(page.locator('.member-chip')).toContainText('游客1234')
})

test('theme: follows the system, then light, then dark, and is remembered', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await start(page)
  const html = page.locator('html')
  const button = page.locator('.btn--theme')
  await expect(html).toHaveAttribute('data-theme', 'dark') // system
  await button.click()
  await expect(html).toHaveAttribute('data-theme', 'light')
  await expect(button).toHaveAttribute('aria-label', '主题：浅色')
  await button.click()
  await expect(html).toHaveAttribute('data-theme', 'dark')
  await page.emulateMedia({ colorScheme: 'light' })
  await page.reload()
  await expect(html).toHaveAttribute('data-theme', 'dark') // the stored choice wins over the system
  const ink = await page.evaluate(() => getComputedStyle(document.body).color)
  expect(ink).toBe('rgb(237, 234, 228)')
})

test('replayed and closer-look frames: on the timeline in their colours, enlargeable', async ({ page }) => {
  await start(page, (m) => m.runs.push(replayAnswer()))
  await enterChat(page)
  await ask(page, '慢放 01:00 到 01:01')
  const answer = lastAnswer(page)
  await expect(answer.locator('.msg-footer')).toBeVisible()

  // the timeline gains the 4 + 2 frames, each kind with its legend and band
  await expect(page.locator('.tl-sheet.is-extra[data-kind="replay"]')).toHaveCount(4)
  await expect(page.locator('.tl-sheet.is-extra[data-kind="view"]')).toHaveCount(2)
  await expect(page.locator('.timeline__legend[data-kind="replay"], .timeline__legend[data-kind="view"]')).toHaveText(['慢放 4 帧清除', '补看 2 帧清除'])
  await expect(page.locator('.tl-band')).toHaveCount(2)
  await expect(page.locator('.timeline__head')).toContainText('8 帧') // the keyframe count is unchanged

  // a timeline frame opens enlarged; arrows step through its group, Esc closes
  await page.locator('.tl-sheet.is-extra[data-kind="replay"]').nth(1).dispatchEvent('click')
  const box = page.locator('.lightbox')
  await expect(box).toContainText('01:00.33')
  await expect(box).toContainText('2 / 4')
  await page.keyboard.press('ArrowRight')
  await expect(box).toContainText('3 / 4')
  await page.keyboard.press('Escape')
  await expect(box).toHaveCount(0)

  // the step shows its range as mm:ss, and the player's thumbnails enlarge too
  await answer.locator('.step-group .thought-line__head').click()
  const row = answer.locator('.step__row', { hasText: '慢放复看' })
  await expect(row).toContainText('01:00–01:01')
  await row.click()
  await answer.locator('.viz-replay__strip button').nth(2).click()
  await expect(box).toContainText('3 / 4')
  await expect(box).toContainText('慢放')
  await box.locator('button[aria-label="关闭"]').click()
  await expect(box).toHaveCount(0)
})

test('timeline marks shot changes and the times answers cite', async ({ page }) => {
  await start(page)
  await enterChat(page)
  await expect(page.locator('.tl-cut')).toHaveCount(2)
  await expect(page.locator('.timeline__legend[data-kind="cut"]')).toHaveText('镜头切换 2')
  await ask(page, '柚子能和药一起吃吗')
  await expect(lastAnswer(page).locator('.msg-footer')).toBeVisible()
  await expect(page.locator('.tl-cite')).toHaveCount(1) // the answer points at [00:30]
  await expect(page.locator('.tl-cite')).toHaveAttribute('title', '回答提到 00:30')
})

// Drag across the track between two fractions of its width; returns the menu.
async function frame(page, from, to) {
  const box = await page.locator('.timeline__track').boundingBox()
  const y = box.y + box.height * 0.6
  await page.mouse.move(box.x + box.width * from, y)
  await page.mouse.down()
  for (let k = 1; k <= 6; k++) await page.mouse.move(box.x + box.width * (from + ((to - from) * k) / 6), y)
  await page.mouse.up()
  return page.locator('.tl-range__menu')
}

test('frame a stretch on the timeline: replay it now, or ask about it', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  await expect(page.locator('.tl-sheet.is-selected')).toHaveCount(0)

  // 8 keyframes over 120 s: a drag across the middle sheets frames a few seconds, capped at 10
  let menu = await frame(page, 0.45, 0.55)
  await expect(menu).toBeVisible()
  const label = await page.locator('.tl-range__label').innerText()
  const [a, b] = label.match(/\d\d:\d\d\.\d/g).map((t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3)))
  expect(b - a).toBeGreaterThan(0.4)
  expect(b - a).toBeLessThanOrEqual(10)
  await expect(page.locator('.tl-sheet.is-selected')).toHaveCount(0) // a drag doesn't pick frames

  await menu.getByRole('menuitem', { name: '直接慢放' }).click()
  const card = page.locator('.msg--manual')
  await expect(card.locator('.manual-replay__tag')).toHaveText('手动慢放')
  await expect(card.locator('.viz-replay__strip button')).toHaveCount(4)
  await expect(page.locator('.tl-sheet.is-extra[data-kind="replay"]')).toHaveCount(4)
  expect(mock.requests.filter((r) => r.path.endsWith('/replay')).map((r) => r.body)).toEqual([{ start: a, end: b }])
  expect(mock.runsSent()).toEqual([]) // no model involved

  // Esc closes the menu without doing anything
  menu = await frame(page, 0.2, 0.3)
  await page.keyboard.press('Escape')
  await expect(menu).toHaveCount(0)

  menu = await frame(page, 0.2, 0.3)
  await menu.getByRole('menuitem', { name: '带着这段提问' }).click()
  await expect(page.locator('.clip-chip')).toContainText('慢放')
  await page.locator('.composer__input').press('Enter') // no question typed: the stretch alone is enough
  await expect.poll(() => mock.runsSent().map((r) => r.question)).toEqual([expect.stringMatching(/^慢放 \d\d:\d\d(\.\d)? 到 \d\d:\d\d(\.\d)?：这段发生了什么？$/)])
  await expect(page.locator('.clip-chip')).toHaveCount(0)
})

test('a framed stretch can be cut out as a GIF, and points to 求原图 for whole videos', async ({ page }) => {
  await start(page)
  await enterChat(page)
  const asked = []
  await page.route('**/clip?**', (route) => {
    asked.push(new URL(route.request().url()).searchParams)
    return route.fulfill({ status: 200, contentType: 'image/gif', body: Buffer.from('GIF89a'),
      headers: { 'content-disposition': "attachment; filename*=utf-8''%E5%B8%A7%E5%AF%BB_%E6%B5%8B%E8%AF%95_0054-0058.gif" } })
  })
  const menu = await frame(page, 0.45, 0.55)
  await expect(menu.getByRole('menuitem', { name: /求原图/ })).toHaveAttribute('href', /ynvan\.com/)
  const download = page.waitForEvent('download')
  await menu.getByRole('menuitem', { name: '截成 GIF' }).click()
  expect((await download).suggestedFilename()).toBe('帧寻_测试_0054-0058.gif')
  await expect(page.locator('.clip-toast')).toContainText('已保存 帧寻_测试_0054-0058.gif')
  expect(asked[0].get('format')).toBe('gif')
  expect(Number(asked[0].get('end'))).toBeGreaterThan(Number(asked[0].get('start')))
})

test('"我要片段的 GIF" opens the clip studio, not the model: pick, tune, make, keep', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  const asked = []
  await page.route('**/clip?**', (route) => {
    asked.push(Object.fromEntries(new URL(route.request().url()).searchParams))
    return route.fulfill({ status: 200, contentType: 'image/gif', body: Buffer.from('GIF89a'),
      headers: { 'content-disposition': "attachment; filename*=utf-8''%E5%B8%A7%E5%AF%BB_t_0054-0058.gif", 'x-clip-fps': '9', 'x-clip-width': '384',
        'x-clip-note': encodeURIComponent('为了压到 1 MB 以内，降到了 9 fps、384 px') } })
  })
  await page.locator('.composer__input').fill('把 00:54 到 00:58 做成表情包 GIF')
  await page.locator('.composer__input').press('Enter')
  const card = page.locator('.clip-studio')
  await expect(card).toBeVisible()
  await expect(card.locator('.clip-studio__readout')).toContainText('起点 00:54.0')
  await expect(card.locator('.clip-studio__readout')).toContainText('终点 00:58.0')
  await expect(card.getByRole('tab', { name: 'GIF 动图' })).toHaveAttribute('aria-selected', 'true')
  expect(mock.runsSent()).toEqual([]) // no model involved

  // 画面范围: 1:1 makes a centred square of the picture; a corner drag shrinks it, keeping the shape
  await card.getByRole('radio', { name: '1:1' }).click()
  const box = card.locator('.clip-studio__crop')
  await expect(box).toBeVisible()
  const before = await box.boundingBox()
  expect(Math.abs(before.width - before.height)).toBeLessThan(3)
  const corner = await card.locator('.clip-studio__crop-handle--se').boundingBox()
  await page.mouse.move(corner.x + corner.width / 2, corner.y + corner.height / 2)
  await page.mouse.down()
  await page.mouse.move(corner.x - 40, corner.y - 10, { steps: 5 })
  await page.mouse.up()
  const after = await box.boundingBox()
  expect(after.width).toBeLessThan(before.width - 20)
  expect(Math.abs(after.width - after.height)).toBeLessThan(3)
  await page.screenshot({ path: 'test-results/clip-crop.png' })
  await card.getByRole('radio', { name: '整个画面' }).click()
  await expect(box).toHaveCount(0)
  await card.getByRole('radio', { name: '16:9' }).click()

  await card.locator('.clip-studio__slider input').first().fill('20') // 帧率
  await card.getByRole('button', { name: '生成 GIF' }).click()
  await expect(card.locator('.clip-studio__result img')).toBeVisible()
  await expect(card.locator('.clip-studio__result')).toContainText('9 fps · 384 px')
  await expect(card.locator('.clip-studio__result')).toContainText('降到了 9 fps')
  expect(asked[0]).toMatchObject({ start: '54.00', end: '58.00', format: 'gif', fps: '20', width: '480', dither: 'bayer', max_mb: '1' })
  expect(asked[0].crop.split(',').map(Number)).toHaveLength(4) // the 16:9 frame went with it
  const download = page.waitForEvent('download')
  await card.getByRole('button', { name: '下载' }).click()
  expect((await download).suggestedFilename()).toBe('帧寻_t_0054-0058.gif')
  await expect(card.getByRole('link', { name: /求原图/ })).toHaveAttribute('href', /ynvan\.com/)
  await page.screenshot({ path: 'test-results/clip-studio.png', fullPage: false })

  // "/GIF" is in the task menu; MP4 asks for sound
  await page.locator('.composer__input').fill('/GIF')
  await expect(page.locator('.slash-menu__item', { hasText: '/GIF' })).toBeVisible()
  await page.locator('.composer__input').fill('截一段 00:10-00:20 的视频片段 mp4')
  await page.locator('.composer__input').press('Enter')
  await expect(page.locator('.clip-studio').last().getByRole('tab', { name: /MP4/ })).toHaveAttribute('aria-selected', 'true')
  expect(mock.runsSent()).toEqual([])
})

test('a question about cutting or GIFs in the video is answered, not taken for a clip request', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  await page.locator('.composer__input').fill('剪映里怎么导出这一段片段？')
  await page.locator('.composer__input').press('Enter')
  await expect.poll(() => mock.runsSent().map((r) => r.question)).toEqual(['剪映里怎么导出这一段片段？'])
  await expect(page.locator('.clip-studio')).toHaveCount(0)
})

test('a hand-framed replay comes back with its session', async ({ page }) => {
  const data = { start: 60, end: 61, fps: 3, times: [60, 60.33, 60.67], frames: ['00', '01', '02'].map((n) => `/api/link-jobs/s1/replay/0006000-0006100-030/${n}.jpg`) }
  await start(page, (m) => m.addSession('s1', {
    title: '有手动慢放的会话',
    messages: [{ role: 'assistant', content: '', status: 'done', manual: 'replay', events: [
      { type: 'tool_call.started', call_id: 'manual1', tool_name: 'frames.replay', t: 0 },
      { type: 'tool_call.output', call_id: 'manual1', stdout: '复看', exit_code: 0, data, t: 0.4 },
      { type: 'tool_call.completed', call_id: 'manual1', result_count: 3, t: 0.4 },
    ] }],
  }))
  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '有手动慢放的会话' }).locator('.session-item__open').click()
  await expect(page.locator('.msg--manual .manual-replay__head')).toContainText('01:00.0 – 01:01.0')
  await expect(page.locator('.msg--manual .viz-replay__strip button')).toHaveCount(3)
  await expect(page.locator('.tl-sheet.is-extra[data-kind="replay"]')).toHaveCount(3)
  await page.locator('.timeline__legend[data-kind="replay"] .timeline__legend-clear').click()
  await expect(page.locator('.tl-sheet.is-extra[data-kind="replay"]')).toHaveCount(0) // off the timeline
  await expect(page.locator('.msg--manual .viz-replay__strip button')).toHaveCount(3) // the replay itself stays in the chat
})

test('back goes straight to the homepage behind the pixel wipe, from the chat too', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' }) // the suite turns motion off; this test is about it
  await start(page)
  await enterChat(page)
  await expect(page.locator('.wipe')).toBeHidden()
  await expect(page.locator('.btn--back')).toHaveText(/返回首页/)
  await page.locator('.btn--back').click()
  await expect(page.locator('.wipe')).toBeVisible() // the cells cover the switch
  await expect(page.locator('.wipe')).toBeHidden()
  await expect(page.locator('.import-control__link')).toBeVisible()
  await expect(page.locator('.import-control__link')).toHaveValue(LINK) // kept, to adjust and parse again
  await expect(page.locator('.composer__input')).toBeHidden()
})

test('a replay framed on one video is not replayed again when the next one opens', async ({ page }) => {
  const mock = await start(page)
  await enterChat(page)
  const menu = await frame(page, 0.45, 0.55)
  await menu.getByRole('menuitem', { name: '直接慢放' }).click()
  await expect(page.locator('.msg--manual .viz-replay__strip button')).toHaveCount(4)
  // back to the import screen, and the next video
  while (await page.locator('.btn--back').isVisible()) await page.locator('.btn--back').click()
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
  await page.waitForTimeout(800)
  await expect(page.locator('.msg--manual')).toHaveCount(0)
  expect(mock.requests.filter((r) => r.path.endsWith('/replay'))).toHaveLength(1)
})

test('a slow replay can be cancelled from its card', async ({ page }) => {
  await start(page, (m) => { m.replayDelay = 5000 })
  await enterChat(page)
  const menu = await frame(page, 0.45, 0.55)
  await menu.getByRole('menuitem', { name: '直接慢放' }).click()
  const card = page.locator('.msg--manual')
  await expect(card).toContainText('正在读取这一段')
  await card.getByRole('button', { name: '取消' }).click()
  await expect(card).toContainText('已取消慢放')
  await expect(card.getByRole('button', { name: '取消' })).toHaveCount(0)
})
