import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

// 科普核查 and 反诈识别 are skills (backend modules/agent/skills.py): steps the agent takes inside an
// answer, its report shown as the step's result, the answer citing it. No side-panel tabs.
const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

const science = {
  version: 1, module: 'factcheck', job_id: 'job1', status: 'done', video: { title: '柚子与降压药' },
  summary: { total: 1, partial: 1, wrong: 0, exaggerations: 1, trusted_sources: 1 },
  disclaimer: '辅助判断，不构成医疗建议',
  claims: [{ id: 'c1', claim: '西柚与某些药物相互作用', original_text: '柚子千万别和降压药一起吃',
    timestamp: { start: 12, end: 15, label: '00:12' }, evidence: { source: 'transcript', segment_index: 0 },
    verdict: 'partial', risk: 'medium', reason: '需要区分具体药物，不能一概而论。', status: 'verified',
    exaggeration: { detected: true, terms: ['千万别'], note: '恐吓式表述' },
    sources: [{ title: '模拟核查出处', url: 'https://pubmed.ncbi.nlm.nih.gov/123', snippet: '用于离线测试的来源摘要', trusted: true, name: 'PubMed', kind: 'journal' }] }],
}
const fraud = {
  version: 1, module: 'antifraud', status: 'partial', message: '尚未核查机构登记', video: { title: '理财课' },
  summary: '规则风险高，需要结合原文复核。', score: { total: 14, base: 10, drainage_bonus: 4, level: 'high' },
  assessment: { status: 'done', risk: 'low', reason: '原文是在提醒观众识别骗局，请勿转账。' },
  claims: [{ id: 'first-low', verdict: 'safe', risk: 'low', claim: '反诈教育引用', original_text: '不要相信保本保息',
    timestamp: { start: 13, end: 20 }, reason: '这是反诈提醒', status: 'unverified', sources: [{ title: '模型', kind: 'model' }] }],
  disclaimer: '不构成权威机构认定', drainage_signals: [],
  qrcodes: [{ frame_index: 0, time: 3, content: 'ordinary first QR content' }, { frame_index: 1, time: 8, content: 'ordinary second QR content' }],
  institutions: { status: 'partial', message: '登记记录不证明视频主体关联或持牌资质。', items: [
    { name: '示例科技有限公司', status: 'official_reference', reason: '官方提及，登记仍待确认。', timestamp: { start: 16 },
      sources: [{ official: true, url: 'https://www.samr.gov.cn/reference', title: '公开通告', snippet: '页面中提及示例科技有限公司' }] }] },
}
const skillAnswer = (tool, report, text) => [
  { type: 'tool_call.started', call_id: 'tool1', tool_name: tool, t: 0.1 },
  { type: 'tool_call.input', call_id: 'tool1', input: { kind: 'params', params: {} }, t: 0.1 },
  { type: 'progress.update', step: tool === 'skill.factcheck' ? '科普核查 1/1：西柚与某些药物相互作用' : '反诈识别：查话术、引流方式、二维码和机构登记', t: 0.3 },
  { type: 'tool_call.output', call_id: 'tool1', stdout: '报告摘要', exit_code: 0, data: { skill: tool.split('.')[1], report }, t: 0.8 },
  { type: 'tool_call.completed', call_id: 'tool1', result_count: 1, t: 0.8 },
  { type: 'assistant.message.delta', delta: text, t: 1 },
  { type: 'run.completed', steps: 2, elapsed_ms: 1200, summary: 'ok', t: 1.2 },
]

async function ask(page, runs, question) {
  const mock = new MockApi(page)
  mock.runs.push(...runs)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.locator('.composer__input').fill(question)
  await page.locator('.composer__input').press('Enter')
  return page.locator('.msg--assistant').last()
}

test('skills: 科普核查 runs as a step of the answer, its report a card under it', async ({ page }) => {
  const answer = await ask(page, [skillAnswer('skill.factcheck', science, '「柚子千万别和降压药一起吃」部分正确 [原声 00:12]。')], '这个视频说得对吗')
  const card = answer.locator('.skill-report[data-skill="factcheck"]')
  await expect(card.locator(':scope > summary')).toContainText('科普核查报告1 条说法 · 错误 0 · 部分正确 1')
  await card.locator(':scope > summary').click()
  const report = card.getByRole('region', { name: '科普核查报告' })
  await expect(report.getByText('部分正确', { exact: true }).last()).toBeVisible()
  await expect(report.getByRole('link', { name: '模拟核查出处' })).toHaveAttribute('href', science.claims[0].sources[0].url)
  await expect(report.getByText('辅助判断，不构成医疗建议', { exact: false })).toBeVisible()
  await expect(report.getByRole('button', { name: /开始核查|重新核查/ })).toHaveCount(0) // the agent ran it; nothing to start here
})

test('skills: 反诈识别 shows model context, moments, QR codes and institution limits', async ({ page }) => {
  const answer = await ask(page, [skillAnswer('skill.antifraud', fraud, '综合判断风险低，这是在提醒观众 [原声 00:13]。')], '这是不是骗局')
  const card = answer.locator('.skill-report[data-skill="antifraud"]')
  await expect(card.locator(':scope > summary')).toContainText('反诈识别报告风险低')
  await card.locator(':scope > summary').click()
  const report = card.getByRole('dialog', { name: '反诈分析报告' })
  await expect(report).toContainText('尚未核查机构登记')
  await expect(report).toContainText('00:13')
  await expect(report.getByRole('region', { name: '机构公开证据核查' })).toContainText('官方提及 · 登记未确认')
  await expect(report.getByRole('link', { name: '公开通告' })).toHaveAttribute('href', 'https://www.samr.gov.cn/reference')
  await expect(report.locator('.antifraud__score-level')).toContainText('风险 低')
  await expect(report.locator('.antifraud__badge')).toHaveText('二维码 ×2')
})

test('skills: the composer\'s quick tasks name them, beside 卡点 for software tutorials', async ({ page }) => {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await page.locator('.composer__input').fill('/')
  const menu = page.getByRole('listbox', { name: '常用任务' })
  await expect(menu).toContainText('卡点')
  await expect(menu).toContainText('科普核查')
  await expect(menu).toContainText('反诈识别')
})

test('skills: 抄作业 sums up the finished node graph, opened, and opens it on its own canvas page', async ({ page }) => {
  const { readFileSync } = await import('node:fs')
  const recipe = JSON.parse(readFileSync(new URL('./fixtures/recipe.json', import.meta.url), 'utf8')) // from a real Blender tutorial
  const answer = await ask(page, [skillAnswer('skill.recipe', recipe, '整体分两棵节点树，最容易连错的是模拟区域 [画面 08:39]。')], '给我最终的节点图，我直接抄作业')
  const card = answer.locator('.skill-report[data-skill="recipe"]')
  await expect(card).toHaveAttribute('open', '')
  const first = recipe.trees[0]
  await expect(card.locator(':scope > summary')).toContainText(`${first.nodes.length + recipe.trees[1].nodes.length} 个节点`)
  await expect(card.locator('.recipe__trees li')).toHaveCount(recipe.trees.length) // the graph itself is on its own page
  await expect(card.locator('.recipe__trees li').first()).toContainText(`${first.nodes.length} 个节点`)
  const opened = page.waitForEvent('popup')
  await card.getByRole('button', { name: '打开节点画布' }).click()
  expect((await opened).url()).toContain(`#/recipe/${recipe.job_id}`)
  await expect(card.locator('.recipe__notes').first()).toContainText(recipe.version_notes[0].text.slice(0, 10))
  await page.screenshot({ path: 'test-results/recipe.png', fullPage: false })
})

test('skills: a skill is its own block in the answer, and the answer may use tables, code and 知识', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const text = '## 结论\n部分正确：要看具体药物 [原声 00:12]。\n\n| 药物 | 和西柚 |\n|---|---|\n| 硝苯地平 | 明显受影响 [知识] |\n| 氨氯地平 | 影响较小 [知识] |\n\n> 吃药前请咨询医生。\n\n```\nCYP3A4 被抑制 → 血药浓度升高\n```'
  const answer = await ask(page, [skillAnswer('skill.factcheck', science, text)], '这个视频说得对吗')
  const block = answer.locator('.skill-block')
  await expect(block).toContainText('技能')
  await expect(block).toContainText('科普核查')
  await expect(block).toContainText('1 条说法')
  await expect(answer.locator('.step-group')).toHaveCount(0) // the skill was the only step: no empty fold
  await expect(answer.locator('.md-table tbody tr')).toHaveCount(2)
  await expect(answer.locator('.md-pre')).toContainText('CYP3A4')
  await expect(answer.locator('.md-quote')).toHaveText('吃药前请咨询医生。')
  await expect(answer.locator('.ev-chip--knowledge')).toHaveCount(2)
  await expect(page.locator('.msg--user .bubble--user')).toHaveCSS('border-radius', '18px')
  await page.screenshot({ path: 'test-results/chat-skill.png' })
})
