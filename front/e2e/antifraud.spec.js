import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

async function enter(page) {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill('https://www.bilibili.com/video/BV1TEST00001')
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click()
  await expect(page.locator('.composer__input')).toBeVisible()
  return mock
}

const report = {
  version: 1, module: 'antifraud', status: 'partial', message: '尚未核查机构登记',
  summary: '规则风险高，需要结合原文复核。', score: { total: 14, base: 10, drainage_bonus: 4, level: 'high' },
  assessment: { status: 'done', risk: 'low', reason: '原文是在提醒观众识别骗局，请勿转账。' },
  claims: [{ id: 'first-low', verdict: 'safe', risk: 'low', claim: '反诈教育引用', original_text: '不要相信保本保息',
    timestamp: { start: 13, end: 20 }, reason: '这是反诈提醒', status: 'unverified', sources: [{ title: '模型', kind: 'model' }] }],
  disclaimer: '不构成权威机构认定', drainage_signals: [],
  institutions: { status: 'partial', message: '登记记录不证明视频主体关联或持牌资质。', items: [
    { name: '示例科技有限公司', status: 'official_reference', reason: '官方提及，登记仍待确认。', timestamp: { start: 16 },
      sources: [{ official: true, url: 'https://www.samr.gov.cn/reference', title: '公开通告', snippet: '页面中提及示例科技有限公司' }] },
  ] },
}

test('antifraud report shows model context, timestamp and verification limits, then closes', async ({ page }) => {
  await enter(page)
  await page.route('**/api/link-jobs/job1/antifraud', (r) => r.fulfill({ json: report }))
  await page.getByRole('button', { name: '反诈识别', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '反诈分析报告' })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('尚未核查机构登记')
  await expect(dialog).toContainText('00:13')
  await expect(dialog).toContainText('待人工核实')
  await expect(dialog.getByRole('region', { name: '机构公开证据核查' })).toContainText('官方提及 · 登记未确认')
  await expect(dialog.getByRole('link', { name: '公开通告' })).toHaveAttribute('href', 'https://www.samr.gov.cn/reference')
  await expect(dialog.locator('.antifraud__score-level')).toContainText('风险 低')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(dialog).toBeHidden()
})

test('antifraud toolbar and open panel leave the stop action usable', async ({ page }) => {
  const mock = await enter(page)
  await page.route('**/api/link-jobs/job1/antifraud', (r) => r.fulfill({ json: report }))
  const release = mock.holdNextRun()
  await page.locator('.composer__input').fill('看看视频')
  await page.locator('.composer__input').press('Enter')
  await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '反诈识别', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '反诈分析报告' })).toBeVisible()
  await page.getByRole('button', { name: '停止', exact: true }).click()
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible()
  release()
})

test('antifraud failures are explained and can be closed', async ({ page }) => {
  await enter(page)
  await page.route('**/api/link-jobs/job1/antifraud', (r) => r.fulfill({ status: 503, json: { detail: '分析服务繁忙' } }))
  await page.getByRole('button', { name: '反诈识别', exact: true }).click()
  await expect(page.locator('.antifraud--error')).toContainText('分析服务繁忙')
  await page.locator('.antifraud--error').getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.locator('.antifraud')).toHaveCount(0)
})
