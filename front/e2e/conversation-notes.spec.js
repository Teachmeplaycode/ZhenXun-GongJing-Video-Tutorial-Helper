import { test, expect } from '@playwright/test'
import { MockApi, openBench, lectureNote } from './mock-api.js'

const messages = [
  { role: 'user', content: '拆解这个 PV 的分镜', status: 'done' },
  { role: 'assistant', content: '在 [00:30]，镜头推进后通过色块遮罩切入下一镜头。', status: 'done', events: [] },
  { role: 'user', content: '这个分镜为什么这样切？', status: 'done' },
  { role: 'assistant', content: '延续主体运动方向，让两个镜头的空间关系更容易理解。', status: 'done', events: [] },
  { role: 'user', content: '一次失败的问题', status: 'done' },
  { role: 'assistant', content: '部分回答', status: 'error', events: [] },
]

async function setup(page, { initial = true, conflict = false, failed = false } = {}) {
  const mock = new MockApi(page)
  mock.addSession('s1', { title: '分镜讨论', messages })
  await mock.install()
  const original = { ...lectureNote(), title: '我整理过的笔记' }
  const revised = { ...lectureNote(), title: '镜头与转场分析' }
  const board = { blocks: [{ id: 'my-note', type: 'text', text: '手动批注保持原样', x: 10, y: 20, w: 300 }] }
  let state = { status: initial ? 'done' : 'none', note: initial ? original : null, board: initial ? board : null, revision: 'base1', draft: null, generation: null, history: [] }
  const requests = []
  let pending = false
  await page.route('**/api/link-jobs/s1/notes**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname
    const body = req.postData() ? req.postDataJSON() : null
    const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
    if (path.endsWith('/export')) return route.fulfill({ contentType: 'text/html', body: `<h1>${url.searchParams.has('draft') ? revised.title : state.note?.title}</h1><p>手动批注保持原样</p>` })
    requests.push({ method: req.method(), path, body })
    if (req.method() === 'POST' && path.endsWith('/notes')) {
      pending = true
      state = { ...state, status: initial ? 'done' : 'running', generation: { status: 'running', message: '正在整理所选分镜讨论', progress: {} } }
      return json(state)
    }
    if (req.method() === 'GET' && pending) {
      pending = false
      if (failed) state = { ...state, status: initial ? 'done' : 'failed', generation: { status: 'failed', message: '模型暂时不可用' } }
      else if (!initial) state = { ...state, status: 'done', note: revised, generation: { status: 'done' } }
      else state = { ...state, generation: { status: 'done' }, draft: { id: 'draft1', base_revision: 'base1', note: revised, board, changes: ['新增小节：镜头与转场分析'], source: 'conversation' } }
    }
    if (path.endsWith('/apply')) {
      if (conflict) {
        state = { ...state, revision: 'new-editor-version', note: { ...original, title: '其他页面的新编辑' } }
        return json({ detail: '笔记已有新编辑，请重新生成修订' }, 409)
      }
      state = { ...state, note: revised, revision: 'applied2', draft: null, history: [{ id: 'old1', title: original.title, created: 1792989377, source: 'video' }] }
    } else if (path.endsWith('/draft') && req.method() === 'DELETE') state = { ...state, draft: null }
    else if (path.endsWith('/restore')) state = { ...state, note: original, revision: 'restored3', history: [{ id: 'previous2', title: revised.title, created: 1792989378, source: 'conversation' }] }
    return json(state)
  })
  await page.goto('/')
  await page.locator('.btn--history').click()
  await page.locator('.history .session-item', { hasText: '分镜讨论' }).locator('.session-item__open').click()
  await openBench(page, '笔记')
  return { requests, getState: () => state }
}

async function chooseFirst(page) {
  await page.getByRole('button', { name: '选择加入笔记的问答' }).click()
  const boxes = page.locator('.notes-turn input')
  await expect(boxes).toHaveCount(3)
  await expect(boxes.nth(0)).toBeEnabled()
  await expect(boxes.nth(0)).not.toBeChecked()
  await expect(boxes.nth(1)).not.toBeChecked()
  await expect(boxes.nth(2)).toBeDisabled()
  await boxes.nth(0).check()
}

test('selected conversations create a reviewable revision while the original note stays usable; apply and restore preserve history', async ({ page }) => {
  const { requests, getState } = await setup(page)
  await chooseFirst(page)
  await page.getByLabel('补充要求（可选）').fill('重点整理遮罩转场')
  await page.getByRole('button', { name: '根据所选对话更新笔记' }).click()
  await expect(page.getByText('正在准备修订稿…')).toBeVisible()
  await expect(page.locator('.notes-tab__title')).toHaveText('我整理过的笔记')
  await expect(page.getByRole('button', { name: '打开笔记编辑器' })).toBeEnabled()
  await expect(page.getByRole('region', { name: '待确认修订' })).toBeVisible()
  const request = requests.find((r) => r.method === 'POST' && r.path.endsWith('/notes'))
  expect(request.body).toEqual({ source: 'conversation', message_ids: [1, 2], instruction: '重点整理遮罩转场', base_revision: 'base1' })
  await page.getByRole('button', { name: '预览修订' }).click()
  await expect(page.getByRole('dialog', { name: '笔记修订预览' })).toContainText('新增小节：镜头与转场分析')
  await expect(page.frameLocator('.preview-dialog iframe').getByRole('heading')).toHaveText('镜头与转场分析')
  await page.getByRole('button', { name: '查看当前版本' }).click()
  await expect(page.frameLocator('.preview-dialog iframe').getByRole('heading')).toHaveText('我整理过的笔记')
  await page.getByRole('button', { name: '查看修订稿' }).click()
  await page.getByRole('button', { name: '应用修订' }).click()
  await expect(page.locator('.preview-dialog')).toHaveCount(0)
  await expect(page.locator('.notes-tab__title')).toHaveText('镜头与转场分析')
  expect(getState().board.blocks[0].text).toBe('手动批注保持原样')
  await page.locator('.notes-history summary').click()
  await page.getByRole('button', { name: '恢复', exact: true }).click()
  await expect(page.locator('.notes-tab__title')).toHaveText('我整理过的笔记')
  expect(requests.find((r) => r.path.endsWith('/restore')).body).toEqual({ base_revision: 'applied2' })
})

test('first conversation note is saved directly and an unrelated turn stays excluded', async ({ page }) => {
  const { requests } = await setup(page, { initial: false })
  await chooseFirst(page)
  await page.getByRole('button', { name: '根据所选对话生成笔记' }).click()
  await expect(page.locator('.notes-tab__title')).toHaveText('镜头与转场分析')
  await expect(page.getByRole('region', { name: '待确认修订' })).toHaveCount(0)
  expect(requests.find((r) => r.method === 'POST').body.message_ids).toEqual([1, 2])
})

test('discarding a draft and failed regeneration both retain the current note', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: '重新整理整段视频' }).click()
  await expect(page.getByRole('button', { name: '放弃修订' })).toBeVisible()
  await page.getByRole('button', { name: '放弃修订' }).click()
  await expect(page.getByRole('region', { name: '待确认修订' })).toHaveCount(0)
  await expect(page.locator('.notes-tab__title')).toHaveText('我整理过的笔记')
})

test('generation failure keeps the original note visible and retry available', async ({ page }) => {
  await setup(page, { failed: true })
  await page.getByRole('button', { name: '重新整理整段视频' }).click()
  await expect(page.getByRole('alert')).toContainText('模型暂时不可用')
  await expect(page.locator('.notes-tab__title')).toHaveText('我整理过的笔记')
  await expect(page.getByRole('button', { name: '重新整理整段视频' })).toBeEnabled()
})

test('an editor change during revision prevents apply and shows the newer note', async ({ page }) => {
  await setup(page, { conflict: true })
  await page.getByRole('button', { name: '重新整理整段视频' }).click()
  await page.getByRole('button', { name: '预览修订' }).click()
  await page.getByRole('button', { name: '应用修订' }).click()
  await expect(page.getByRole('dialog', { name: '笔记修订预览' }).getByRole('alert')).toContainText('笔记已有新编辑')
  await expect(page.getByRole('button', { name: '应用修订' })).toBeDisabled()
  await page.getByRole('button', { name: '关闭预览' }).click()
  await expect(page.locator('.notes-tab__title')).toHaveText('其他页面的新编辑')
})

test('an old editor stops autosaving after a revision conflict', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  const writes = []
  let conflict = false
  await page.route('**/api/link-jobs/job1/notes**', async (route) => {
    if (route.request().method() === 'PUT') {
      writes.push(route.request().postDataJSON())
      return route.fulfill({ status: conflict ? 409 : 200, contentType: 'application/json', body: JSON.stringify(conflict ? { detail: '版本变化' } : { saved: 1, revision: 'saved2' }) })
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'done', note: lectureNote(), revision: 'base1', board: { blocks: [{ id: 'sec-s1', type: 'section', title: '分镜', points: ['原内容'], x: 0, y: 0, w: 500 }], viewport: { x: 40, y: 40, zoom: 1 } } }) })
  })
  await page.goto('/#/notes/job1')
  await expect(page.locator('[data-block="sec-s1"]')).toBeVisible()
  conflict = true
  await page.locator('[data-block="sec-s1"]').dblclick()
  await page.getByLabel('小节标题').fill('未保存的改动')
  await page.getByRole('button', { name: '完成', exact: true }).click()
  await expect(page.locator('.nb-conflict')).toBeVisible()
  expect(writes.at(-1).base_revision).toBe('base1')
  const count = writes.length
  await page.getByRole('button', { name: '放大' }).click()
  await page.getByRole('button', { name: '预览', exact: true }).click()
  await expect(page.locator('.nb-world .nb-section h2')).toHaveText('未保存的改动')
  await expect(page.locator('.preview-dialog')).toHaveCount(0)
  expect(writes).toHaveLength(count)
})
