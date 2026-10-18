import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'
import { readFile } from 'node:fs/promises'

// A saved session as the backend returns it: two Q&A turns (the second's answer cites a slow-motion
// replay) plus one hand-framed replay, with the row ids the backend assigns from 1.
function savedMessages() {
  const replay = { start: 60, end: 61, fps: 3, times: [60, 60.33, 60.67, 61],
    frames: ['00', '01', '02', '03'].map((n) => `/api/link-jobs/s1/replay/0006000-0006100-030/${n}.jpg`) }
  return [
    { role: 'user', content: '柚子会影响药物吗？', status: 'done', frames: [0] },
    { role: 'assistant', content: '会影响，在 [00:30] 提到 CYP3A4。', status: 'done', events: [] },
    { role: 'user', content: '他在哪里起跳？', status: 'done', frames: [] },
    { role: 'assistant', content: '他在 [01:00] 起跳。', status: 'done', events: [
      { type: 'tool_call.started', call_id: 'r1', tool_name: 'frames.replay', t: 0.1 },
      { type: 'tool_call.output', call_id: 'r1', stdout: '复看', exit_code: 0, data: replay, t: 0.5 },
      { type: 'tool_call.completed', call_id: 'r1', result_count: 4, t: 0.5 },
    ] },
    { role: 'assistant', content: '', status: 'done', manual: 'replay', events: [
      { type: 'tool_call.started', call_id: 'manual1', tool_name: 'frames.replay', t: 0 },
      { type: 'tool_call.output', call_id: 'manual1', stdout: '复看', exit_code: 0, data: replay, t: 0.4 },
      { type: 'tool_call.completed', call_id: 'manual1', result_count: 4, t: 0.4 },
    ] },
  ]
}

async function openExportDialog(page) {
  const mock = new MockApi(page)
  mock.addSession('s1', { title: '导出会话', messages: savedMessages() })
  await mock.install()
  await page.goto('/')
  await page.locator('.recent .session-item', { hasText: '导出会话' }).locator('.session-item__open').click()
  await expect(page.locator('.chat__export')).toBeVisible()
  await page.locator('.chat__export').click()
  const dialog = page.locator('.export-dialog')
  await expect(dialog).toBeVisible()
  return { mock, dialog }
}

test('export: the dialog lists the turns, checked by default', async ({ page }) => {
  const { dialog } = await openExportDialog(page)
  const turns = dialog.locator('.export-item:not(.export-item--all)')
  await expect(turns).toHaveCount(3)
  await expect(turns.nth(0)).toContainText('柚子会影响药物吗？')
  await expect(turns.nth(1)).toContainText('他在哪里起跳？')
  await expect(turns.nth(2)).toContainText('手动慢放 01:00.0–01:01.0')
  await expect(dialog.locator('.export-item--all input')).toBeChecked()
  await expect(turns.locator('input')).toHaveCount(3)
  for (const box of await turns.locator('input').all()) await expect(box).toBeChecked()
})

test('export: unchecked turns are left out of the markdown download', async ({ page }) => {
  const { mock, dialog } = await openExportDialog(page)
  // Leave out the first Q&A (backend rows 1–2): the note keeps the second pair and the replay.
  await dialog.locator('.export-item:not(.export-item--all) input').nth(0).uncheck()
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    dialog.getByRole('button', { name: '导出 Markdown' }).click(),
  ])
  expect(download.suggestedFilename()).toBe('note.zip')
  const req = mock.requests.find((r) => r.path === '/api/sessions/s1/export')
  expect(req).toBeTruthy()
  expect(new URLSearchParams(req.query).get('ids')).toBe('3,4,5')
  const bytes = await readFile(await download.path())
  expect(bytes.readUInt32LE(0)).toBe(0x04034b50)
  expect(bytes.includes(Buffer.from('笔记.md'))).toBe(true)
  expect(bytes.includes(Buffer.from('images/frame_000.jpg'))).toBe(true)
  expect(bytes.includes(Buffer.from('他在哪里起跳？'))).toBe(true)
  expect(bytes.includes(Buffer.from('柚子会影响药物吗？'))).toBe(false)
  await expect(dialog).toHaveCount(0) // the dialog closes after the export
})

test('export: all visible saved turns use explicit durable ids', async ({ page }) => {
  const { mock, dialog } = await openExportDialog(page)
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    dialog.getByRole('button', { name: '导出 Markdown' }).click(),
  ])
  expect(download.suggestedFilename()).toBe('note.zip')
  const req = mock.requests.find((r) => r.path === '/api/sessions/s1/export')
  expect(req).toBeTruthy()
  expect(new URLSearchParams(req.query).get('ids')).toBe('1,2,3,4,5')
})

test('export: the PDF format opens the print page in a new tab', async ({ page, context }) => {
  const { mock, dialog } = await openExportDialog(page)
  const [popup] = await Promise.all([
    context.waitForEvent('page'),
    dialog.getByRole('button', { name: '导出 PDF（打印页）' }).click(),
  ])
  await popup.waitForLoadState('domcontentloaded')
  await expect(popup.locator('h1')).toHaveText('测试视频：柚子与药物')
  await expect(popup.locator('body')).toContainText('另存为 PDF')
  const req = mock.requests.find((r) => r.path === '/api/sessions/s1/export')
  expect(req).toBeTruthy()
  expect(new URLSearchParams(req.query).get('format')).toBe('pdf')
  expect(new URLSearchParams(req.query).get('ids')).toBe('1,2,3,4,5')
})

test('export: an answer still streaming cannot be picked yet', async ({ page }) => {
  const mock = new MockApi(page)
  mock.addSession('s1', { title: '导出会话', messages: savedMessages() })
  await mock.install()
  await page.goto('/')
  await page.locator('.recent .session-item', { hasText: '导出会话' }).locator('.session-item__open').click()
  // A new question with the answer held mid-run: the turn exists but is not saved yet.
  const release = mock.holdNextRun()
  await page.locator('.composer__input').fill('一个还没保存的问题')
  await page.locator('.composer__input').press('Enter')
  await page.locator('.chat__export').click()
  const turns = page.locator('.export-dialog .export-item:not(.export-item--all)')
  await expect(turns).toHaveCount(4)
  await expect(turns.nth(3)).toContainText('一个还没保存的问题')
  await expect(turns.nth(3)).toHaveAttribute('data-pending', 'true')
  await expect(turns.nth(3).locator('input')).toBeDisabled()
  release()
})

test('export: clearing every selection disables both formats and sends no export', async ({ page }) => {
  const { mock, dialog } = await openExportDialog(page)
  const all = dialog.locator('.export-item--all input')
  await expect(all).toBeChecked()
  await all.uncheck()
  await expect(dialog.getByRole('button', { name: '导出 Markdown' })).toBeDisabled()
  await expect(dialog.getByRole('button', { name: '导出 PDF（打印页）' })).toBeDisabled()
  expect(mock.requests.filter((request) => request.path.endsWith('/export'))).toHaveLength(0)
})

test('export: a fresh completed chat exports without reopening the session', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.locator('.composer__input').fill('刚刚提出的新问题')
  await page.locator('.composer__input').press('Enter')
  await expect(page.locator('.msg--assistant .msg-footer')).toBeVisible()
  await page.locator('.chat__export').click()
  const dialog = page.locator('.export-dialog')
  await expect(dialog.locator('.export-item:not(.export-item--all) input')).toBeEnabled()
  const [download] = await Promise.all([
    page.waitForEvent('download'), dialog.getByRole('button', { name: '导出 Markdown' }).click(),
  ])
  const request = mock.requests.find((r) => r.path === '/api/sessions/job1/export')
  expect(new URLSearchParams(request.query).get('ids')).toBe('1,2')
  const bytes = await readFile(await download.path())
  expect(bytes.includes(Buffer.from('刚刚提出的新问题'))).toBe(true)
  expect(bytes.includes(Buffer.from('CYP3A4'))).toBe(true)
})

test('export: the pending turn becomes selectable after completion without replacing the chat', async ({ page }) => {
  const { mock, dialog } = await openExportDialog(page)
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  const release = mock.holdNextRun()
  await page.locator('.composer__input').fill('等待完成再导出')
  await page.locator('.composer__input').press('Enter')
  await page.locator('.chat__export').click()
  const turn = page.locator('.export-dialog .export-item:not(.export-item--all)').last()
  await expect(turn.locator('input')).toBeDisabled()
  release()
  await expect(turn.locator('input')).toBeEnabled()
  await expect(page.locator('.msg--assistant').last().locator('.msg-footer')).toBeVisible()
})

test('export: a failed bundle request remains visible instead of downloading an error page', async ({ page }) => {
  const { dialog } = await openExportDialog(page)
  const downloads = []
  page.on('download', (download) => downloads.push(download))
  await page.route('**/api/sessions/s1/export?**', (route) => route.fulfill({ status: 503, body: 'unavailable' }))
  await dialog.getByRole('button', { name: '导出 Markdown' }).click()
  await expect(dialog.getByRole('alert')).toContainText('HTTP 503')
  await expect(dialog.getByRole('button', { name: '重新读取保存状态' })).toBeVisible()
  expect(downloads).toHaveLength(0)
})
