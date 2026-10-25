// 抄作业's canvas page (#/recipe/<jobId>, src/recipe/RecipeCanvas.jsx): every node of a real Blender
// tutorial drawn as Blender draws it, one node tree per tab; dragging a node saves where it went.
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { MockApi } from './mock-api.js'

const recipe = JSON.parse(readFileSync(new URL('./fixtures/recipe-canvas.json', import.meta.url), 'utf8'))

test('recipe canvas: trees as tabs, every node and link drawn, a dragged node saves its place', async ({ page }) => {
  const mock = new MockApi(page)
  mock.recipe = recipe
  await mock.install()
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/recipe/job1')
  const first = recipe.trees[0]
  await expect(page.getByRole('tab', { name: new RegExp(first.name.slice(0, 4)) })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.rc-node')).toHaveCount(first.nodes.length)
  await expect(page.locator('.rc-world > path')).toHaveCount(first.links.length)
  await expect(page.locator('.rc-world > path[stroke-dasharray="7 6"]')).toHaveCount(first.links.filter((l) => l.inferred).length)
  await page.screenshot({ path: 'test-results/recipe-canvas.png' })

  const head = page.locator('.rc-node').first().locator('path').first()
  const box = await head.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2) // the title bar is a few pixels tall when the whole tree fits
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 200, box.y + 100, { steps: 6 })
  await page.mouse.up()
  await expect.poll(() => (mock.recipeLayouts || []).length).toBe(1)
  expect(Object.keys(mock.recipeLayouts[0]['0']).length).toBe(first.nodes.length)

  await page.getByRole('tab', { name: new RegExp(recipe.trees[1].name.slice(0, 4)) }).click()
  await expect(page.locator('.rc-node')).toHaveCount(recipe.trees[1].nodes.length)
})

test('recipe canvas: a session without one says how to get it', async ({ page }) => {
  await new MockApi(page).install()
  await page.goto('/#/recipe/job1')
  await expect(page.locator('.rc-empty')).toContainText('还没有抄作业')
})

test('recipe canvas: a Math node is titled by its operation, a vector setting gets X / Y / Z rows', async ({ page }) => {
  const mock = new MockApi(page)
  mock.recipe = JSON.parse(readFileSync(new URL('./fixtures/recipe-zone.json', import.meta.url), 'utf8')) // a real Blender tutorial
  await mock.install()
  await page.goto('/#/recipe/job1')
  const loop = page.locator('.rc-node', { hasText: '循环' }).first()
  await expect(loop).toContainText('Math')
  const transform = page.locator('.rc-node', { hasText: '变换几何体' })
  await expect(transform.locator('text', { hasText: /^Z$/ })).toHaveCount(3) // 移动, 旋转, 缩放 each with an X / Y / Z
})

test('recipe canvas: the Blender script is one click away; add-ons and a low resolution are said', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  const mock = new MockApi(page)
  mock.recipe = { ...JSON.parse(readFileSync(new URL('./fixtures/recipe-zone.json', import.meta.url), 'utf8')), source_height: 480,
    plugins: [{ term: 'Node Wrangler', plugin: 'Node Wrangler', provides: '节点快捷操作', install: '扩展平台安装', url: 'https://extensions.blender.org/add-ons/node-wrangler/' }] }
  await mock.install()
  await page.goto('/#/recipe/job1')
  await page.getByRole('button', { name: '复制 Blender 脚本' }).click()
  await expect(page.getByRole('button', { name: '脚本已复制' })).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('import bpy')
  await expect(page.locator('.rc-panel')).toContainText('需要的插件')
  await expect(page.locator('.rc-panel a', { hasText: '出处' })).toHaveAttribute('href', /extensions\.blender\.org/)
  await expect(page.locator('.rc-warn')).toContainText('480p')
})

test('recipe canvas: with Blender connected, apply the graph and 对答案 marks what is missing', async ({ page }) => {
  const mock = new MockApi(page)
  mock.recipe = JSON.parse(readFileSync(new URL('./fixtures/recipe-zone.json', import.meta.url), 'utf8'))
  mock.blender = { available: true, connected: true, blender: '5.0.1', object: 'Cube' }
  const transform = mock.recipe.trees[0].nodes.find((n) => n.ref === 'GeometryNodeTransform')
  mock.checkResult = { done: false, summary: '还差 1 个节点、1 根线、1 处参数', theirs: '几何节点', matched: 9, nodes: 10, findings: [
    { kind: 'missing_node', node: transform.id, text: '少了节点「变换几何体」：Shift+A 搜「变换几何体」添加' },
    { kind: 'missing_link', from: 'n1', to: 'n8', text: '缺一根线：组输入.几何数据 → 切换.真' },
    { kind: 'setting', text: '「循环」的「最大值」应为 3，你的是 5' }] }
  await mock.install()
  await page.goto('/#/recipe/job1')
  await page.getByRole('button', { name: '应用到 Blender' }).click()
  await expect(page.locator('.rc-warn')).toContainText('已在 Blender 里建好')
  await page.getByRole('button', { name: '对答案' }).click()
  await expect(page.locator('.rc-result h4')).toHaveText('对答案 · 还差 1 个节点、1 根线、1 处参数')
  await expect(page.locator('.rc-result li')).toHaveCount(3)
  await expect(page.locator('.rc-node rect[stroke="#FF5A4E"]')).toHaveCount(1) // the missing Transform outlined
  expect(mock.blenderCalls).toEqual(['apply', 'check'])
})

test('recipe canvas: Blender not connected yet shows how to connect it', async ({ page }) => {
  const mock = new MockApi(page)
  mock.recipe = JSON.parse(readFileSync(new URL('./fixtures/recipe-zone.json', import.meta.url), 'utf8'))
  mock.blender = { available: true, connected: false, message: '没有连上 Blender' }
  await mock.install()
  await page.goto('/#/recipe/job1')
  await page.getByRole('button', { name: '连接 Blender' }).click()
  await expect(page.locator('.rc-steps li')).toHaveCount(4)
  await expect(page.getByRole('link', { name: '下载「帧寻 Bridge」插件' })).toHaveAttribute('href', /\/api\/blender\/addon$/)
})

test('recipe canvas: AI 修改 fixes the graph, shows what Blender made, and can be undone', async ({ page }) => {
  const mock = new MockApi(page)
  const zone = JSON.parse(readFileSync(new URL('./fixtures/recipe-zone.json', import.meta.url), 'utf8'))
  mock.recipe = zone
  mock.blender = { available: true, connected: true, blender: '5.0.1', object: 'Grid' }
  const added = { id: 'ai1', name: '法向', en: 'Normal', ref: 'GeometryNodeInputNormal', params: [], inputs: [],
    outputs: [{ name: '法向', en: 'Normal', type: 'Vector' }] }
  mock.revision = { summary: '补上了法向，Blender 里能建出来。', changes: ['加节点「法向」(ai1)'], problems: [],
    checks: ['建出 11 个节点、12 根线\n没有无效连线\n修改器输出：400 个点、380 个面'],
    preview: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    recipe: { trees: [{ ...zone.trees[0], nodes: [...zone.trees[0].nodes, added] }, ...zone.trees.slice(1)] } }
  await mock.install()
  await page.goto('/#/recipe/job1')
  await page.getByRole('button', { name: 'AI 修改' }).click()
  await page.getByRole('button', { name: '补全没连上的节点和线' }).click()
  await expect(page.locator('.rc-summary')).toHaveText('补上了法向，Blender 里能建出来。')
  await expect(page.locator('.rc-node')).toHaveCount(zone.trees[0].nodes.length + 1)
  await expect(page.getByRole('img', { name: 'Blender 按改后的节点图做出的效果' })).toBeVisible()
  await expect(page.locator('.rc-blender')).toContainText('400 个点')
  await page.screenshot({ path: 'test-results/recipe-revise.png' })
  expect(mock.reviseCalls[0]).toEqual({ tree: 0, instruction: '补全没连上的节点和线' })

  await page.getByLabel('修改要求').fill('等高线没出来')
  await page.getByRole('button', { name: '让 AI 改' }).click()
  await expect.poll(() => mock.reviseCalls.length).toBe(2)
  expect(mock.reviseCalls[1].instruction).toBe('等高线没出来')

  await page.getByRole('button', { name: '撤销这次修改' }).click()
  await expect.poll(() => mock.reviseCalls.at(-1)).toBe('undo')
  await expect(page.locator('.rc-node')).toHaveCount(zone.trees[0].nodes.length) // reloaded the graph before
})
