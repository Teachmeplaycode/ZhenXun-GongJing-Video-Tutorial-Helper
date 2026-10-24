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
