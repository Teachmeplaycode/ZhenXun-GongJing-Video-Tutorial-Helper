import { test, expect } from '@playwright/test'
import { MockApi, openBench, lectureNote } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

async function enterChat(page, setup) {
  const mock = new MockApi(page)
  setup?.(mock)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.locator('.composer__input')).toBeVisible()
  return mock
}

test('the workbench folds out from the right edge with its tabs, and remembers where it was', async ({ page }) => {
  await enterChat(page)
  const handle = page.locator('.bench__handle')
  await expect(handle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.chat__toolbar, .chat__factcheck, .chat__export')).toHaveCount(0) // nothing stacked above the composer
  await handle.click()
  // 反诈 and 科普 are skills the agent runs in an answer now (e2e/skills.spec.js), not tabs.
  await expect(page.getByRole('tab')).toHaveText(['步骤', '对照', /章节/, '笔记'])
  // arrow keys move between tabs
  await page.getByRole('tab', { name: /章节/ }).click()
  await page.getByRole('tab', { name: /章节/ }).press('ArrowRight')
  await expect(page.getByRole('tab', { name: '笔记' })).toHaveAttribute('aria-selected', 'true')
  await page.reload()
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await expect(page.getByRole('tab', { name: '笔记' })).toHaveAttribute('aria-selected', 'true')
})

test('notes: generate, then open the editor; the Q&A export moved into the tab', async ({ page, context }) => {
  const mock = await enterChat(page)
  await openBench(page, '笔记')
  await expect(page.getByRole('button', { name: '还没有问答' })).toBeDisabled()
  await page.getByRole('button', { name: '生成笔记' }).click()
  await expect(page.getByText('正在整理笔记…')).toBeVisible()
  await expect(page.locator('.notes-tab__title')).toHaveText('柚子与药物笔记', { timeout: 10_000 })
  await expect(page.locator('.notes-tab__done')).toContainText('2 节 · 1 张配图')
  expect(mock.requests.filter((r) => r.path.endsWith('/notes') && r.method === 'POST')).toHaveLength(1)

  const [editor] = await Promise.all([context.waitForEvent('page'), page.getByRole('button', { name: '打开笔记编辑器' }).click()])
  await editor.waitForLoadState()
  expect(editor.url()).toContain('#/notes/job1')
})

async function openEditor(page, board = null) {
  const mock = new MockApi(page)
  mock.notes = { status: 'done', message: '', progress: {}, note: lectureNote() }
  mock.noteBoard = board
  await mock.install()
  await page.goto('/#/notes/job1')
  await expect(page.locator('.nb-bar strong')).toHaveText('柚子与药物笔记')
  return mock
}

test('editor: the note is laid out as blocks — title, sections with formulas, the figure beside, a mind map', async ({ page }) => {
  await openEditor(page)
  await expect(page.locator('.nb-world .nb-block')).toHaveCount(5) // title, 2 sections, 1 figure, mind map
  await expect(page.locator('.nb-block[data-type="section"]').first()).toContainText('作用机制')
  await expect(page.locator('.nb-world .nb-formula .katex')).toHaveCount(1) // LaTeX rendered
  await expect(page.locator('.nb-world .nb-mindmap')).toHaveAttribute('aria-label', '思维导图：柚子与药物')
  const section = await page.locator('[data-block="sec-s1"]').boundingBox()
  const figure = await page.locator('[data-block="fig-s1-0"]').boundingBox()
  expect(figure.x).toBeGreaterThan(section.x + section.width - 1) // the picture sits to the section's right
  const second = await page.locator('[data-block="sec-s2"]').boundingBox()
  expect(second.y).toBeGreaterThan(Math.max(section.y + section.height, figure.y + figure.height) - 1) // no overlap
})

test('editor: drag a block, edit a section, delete and undo — the board is saved', async ({ page }) => {
  const mock = await openEditor(page)
  await expect(page.locator('.nb-bar__save')).toHaveText('已保存', { timeout: 10_000 })
  const block = page.locator('[data-block="fig-s1-0"]')
  const box = await block.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 120, box.y + box.height / 2 + 60, { steps: 6 })
  await page.mouse.up()
  const moved = await block.boundingBox()
  expect(moved.x - box.x).toBeGreaterThan(60)

  await page.locator('[data-block="sec-s2"]').dblclick()
  await page.getByLabel('小节标题').fill('服药期间怎么吃')
  await page.getByLabel('要点（一行一条）').fill('至少间隔 24 小时\n问医生')
  await page.getByRole('button', { name: '完成' }).click()
  await expect(page.locator('[data-block="sec-s2"] h2')).toHaveText('服药期间怎么吃')
  await expect(page.locator('[data-block="sec-s2"] ul li')).toHaveText(['至少间隔 24 小时', '问医生'])

  await expect(page.locator('.nb-bar__save')).toHaveText('已保存', { timeout: 10_000 })
  const saved = mock.noteBoard.blocks
  expect(saved.find((b) => b.id === 'sec-s2').title).toBe('服药期间怎么吃')
  expect(saved.find((b) => b.id === 'fig-s1-0').x).toBeGreaterThan(620) // moved right of its column

  await page.locator('[data-block="sec-s2"]').click()
  await page.keyboard.press('Delete')
  await expect(page.locator('[data-block="sec-s2"]')).toHaveCount(0)
  await page.keyboard.press('ControlOrMeta+z')
  await expect(page.locator('[data-block="sec-s2"] h2')).toHaveText('服药期间怎么吃')
})

test('editor: a saved board opens as it was left; zoom and export', async ({ page }) => {
  const board = { viewport: { x: 0, y: 0, zoom: 1 }, blocks: [
    { id: 'title', type: 'title', x: 0, y: 0, w: 600, text: '我自己的标题', summary: '' },
    { id: 'text-1', type: 'text', x: 0, y: 140, w: 300, text: '复习时先看例题' },
  ] }
  await openEditor(page, board)
  await expect(page.locator('.nb-world .nb-block')).toHaveCount(2)
  await expect(page.locator('.nb-world .nb-title h1')).toHaveText('我自己的标题')
  await expect(page.locator('.nb-zoom__value')).toHaveText('100%')
  await page.getByRole('button', { name: '放大' }).click()
  await expect(page.locator('.nb-zoom__value')).toHaveText('120%')
  const [request] = await Promise.all([
    page.waitForRequest((r) => r.url().endsWith('/api/link-jobs/job1/notes/export')),
    page.getByRole('button', { name: '导出 Markdown' }).click(),
  ])
  expect(request.method()).toBe('GET')
})

test('editor: without a note it says how to make one', async ({ page }) => {
  await new MockApi(page).install()
  await page.goto('/#/notes/job1')
  await expect(page.getByText('这个视频还没有生成笔记')).toBeVisible()
})

test('timeline: a long press on a sheet opens the frame viewer, without picking the frame', async ({ page }) => {
  await enterChat(page)
  const sheet = page.locator('.tl-sheet').nth(3)
  const box = await sheet.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 8)
  await page.mouse.down()
  await page.waitForTimeout(650)
  await page.mouse.up()
  const viewer = page.locator('.lightbox')
  await expect(viewer).toBeVisible()
  await expect(viewer).toContainText('/ 8')
  const first = await viewer.locator('.lightbox__count').innerText()
  await page.keyboard.press('ArrowRight')
  await expect(viewer.locator('.lightbox__count')).not.toHaveText(first)
  await page.keyboard.press('Escape')
  await expect(viewer).toHaveCount(0)
  await expect(page.locator('.tl-sheet.is-selected')).toHaveCount(0)
})

test('frame viewer: reads the source frame and offers native-size scrolling', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    // playwright.config.js deliberately disables WebGL; the app's existing static fallback logs this.
    const expectedWebGL = /^THREE\.WebGLRenderer: (A WebGL context could not be created\. Reason:  disabled by enterprise policy or commandline switch|Error creating WebGL context\.)/.test(message.text())
    if (message.type() === 'error' && !expectedWebGL) errors.push(message.text())
  })
  await enterChat(page)
  await expect(page).toHaveURL(/localhost:5199/)
  await expect(page).toHaveTitle(/帧寻/)
  await expect(page.locator('vite-error-overlay')).toHaveCount(0)
  await page.route('**/api/link-jobs/job1/frames/*.jpg?detail=true', (route) => route.fulfill({
    status: 200, contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="#243339"/><text x="90" y="120" fill="white" font-size="36">Original frame: 1920 x 1080</text></svg>',
  }))
  const box = await page.locator('.tl-sheet').nth(3).boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 8)
  await page.mouse.down()
  await page.waitForTimeout(650)
  await page.mouse.up()
  const viewer = page.getByRole('dialog', { name: /放大查看/ })
  await expect(viewer.getByRole('status')).toHaveText('原帧 1920×1080')
  await expect(viewer.locator('img')).toHaveAttribute('src', /^blob:/)
  await viewer.getByRole('button', { name: '原始尺寸' }).click()
  await expect(viewer.locator('.lightbox__viewport')).toHaveClass(/is-native/)
  expect(await viewer.locator('img').evaluate((img) => img.getBoundingClientRect().width)).toBe(1920)
  if (process.env.CODEX_QA_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.CODEX_QA_SCREENSHOT_DIR}/detail-native.png` })
  await viewer.getByRole('button', { name: '适应窗口' }).click()
  await expect(viewer.locator('.lightbox__viewport')).not.toHaveClass(/is-native/)
  if (process.env.CODEX_QA_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.CODEX_QA_SCREENSHOT_DIR}/detail-desktop.png` })
  await page.setViewportSize({ width: 390, height: 844 })
  // Phones replace the timeline with the workbench frame picker; its viewer unmounts.
  await expect(page.locator('.timeline')).toHaveCount(0)
  await expect(viewer).toHaveCount(0)
  await expect(page.locator('.composer__input')).toBeVisible()
  if (process.env.CODEX_QA_SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.CODEX_QA_SCREENSHOT_DIR}/detail-mobile-app.png` })
  expect(errors).toEqual([])
})

test('frame viewer: an unavailable source keeps the preview and can still advance', async ({ page }) => {
  await enterChat(page)
  await page.route('**/api/link-jobs/job1/frames/*.jpg?detail=true', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  const box = await page.locator('.tl-sheet').nth(3).boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height - 8)
  await page.mouse.down()
  await page.waitForTimeout(650)
  await page.mouse.up()
  const viewer = page.getByRole('dialog', { name: /放大查看/ })
  await expect(viewer.getByRole('status')).toHaveText('高清帧暂不可用，显示预览')
  const src = await viewer.locator('img').getAttribute('src')
  expect(src).toMatch(/\/frames\/3\.jpg$/)
  await expect(viewer.getByRole('button', { name: '原始尺寸' })).toHaveCount(0)
  await page.keyboard.press('ArrowRight')
  await expect(viewer.locator('img')).not.toHaveAttribute('src', src)
  await expect(viewer.locator('img')).toBeVisible()
})

test('timeline: a typed interval replays or attaches, and explains what it rejects', async ({ page }) => {
  const mock = await enterChat(page)
  await page.getByRole('button', { name: '输入区间' }).click()
  const form = page.getByRole('form', { name: '输入慢放区间' })
  await form.getByLabel('开始').fill('1:05')
  await form.getByLabel('结束').fill('1:30')
  await form.getByRole('button', { name: '直接慢放' }).click()
  await expect(form.getByRole('alert')).toHaveText('一次最多慢放 10 秒，现在是 25.0 秒')
  await form.getByLabel('结束').fill('abc')
  await expect(form.getByRole('alert')).toContainText('时间格式不对')
  await form.getByLabel('结束').fill('67.5')
  await expect(form).toContainText('01:05.0 – 01:07.5 · 2.5 秒')
  await form.getByRole('button', { name: '直接慢放' }).click()
  await expect(form).toHaveCount(0)
  await expect(page.locator('.msg--manual')).toBeVisible()
  expect(mock.requests.filter((r) => r.path.endsWith('/replay')).map((r) => r.body)).toEqual([{ start: 65, end: 67.5 }])

  await page.getByRole('button', { name: '输入区间' }).click()
  await form.getByLabel('开始').fill('10')
  await form.getByLabel('结束').fill('12')
  await form.getByRole('button', { name: '带着这段提问' }).click()
  await expect(page.locator('.clip-chip')).toContainText('00:10.0 – 00:12.0')
})
