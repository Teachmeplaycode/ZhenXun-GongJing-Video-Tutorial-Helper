// Step cards (backend modules/steps.py): built on request in the workbench, each with its frame and
// time; 「卡在这步」 starts a question about that step.
import { test, expect } from '@playwright/test'
import { MockApi, openBench } from './mock-api.js'

const LINK = 'https://www.bilibili.com/video/BV1TEST00001'

test('steps: built on request, a card per step, 卡在这步 fills the question', async ({ page }) => {
  await new MockApi(page).install()
  await page.goto('/')
  await page.locator('.import-control__link').fill(LINK)
  await page.locator('.import-control__submit').click()
  await page.locator('.btn--next:not(.btn--early)').click({ timeout: 30_000 })
  await openBench(page, '步骤')
  const tab = page.locator('.steps-tab')
  await expect(tab.getByRole('heading', { name: '整理操作步骤' })).toBeVisible()
  await tab.getByRole('button', { name: '整理步骤' }).click()
  await expect(tab.locator('.step-card')).toHaveCount(2)
  await expect(tab.locator('.step-card').first()).toContainText('数据验证')
  await expect(tab.locator('.step-card__time').nth(1)).toHaveText('00:40')
  await tab.locator('.step-card').nth(1).getByRole('button', { name: '卡在这步' }).click()
  await expect(page.locator('.composer__input')).toHaveValue(/第 2 步「把「允许」改成「序列」」卡住了/)
})
