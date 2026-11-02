import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const SETTINGS_BTN = 'button[title="设置：模型、平台账号、本地运行"]'

async function start(page) {
  const mock = new MockApi(page)
  await mock.install()
  await page.goto('/')
  return mock
}

test('设置按钮打开面板，有三个 tab', async ({ page }) => {
  await start(page)
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('.settings-panel')).toBeVisible()
  for (const label of ['模型与 API', '平台账号', '本地运行']) {
    await expect(page.locator('.settings-tab', { hasText: label })).toBeVisible()
  }
})

test('模型 tab 显示字段并保存', async ({ page }) => {
  const mock = await start(page)
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('.settings-field__code', { hasText: 'LLM_MODEL' })).toBeVisible()
  await page.locator('#set-LLM_MODEL').fill('deepseek-chat')
  await page.locator('.settings-actions .btn--dark').click()
  await expect(page.locator('.settings-saved')).toBeVisible()
  const put = mock.requests.find((r) => r.method === 'PUT' && r.path === '/api/settings')
  expect(put).toBeTruthy()
  expect(put.body.values.LLM_MODEL).toBe('deepseek-chat')
})

test('账号 tab 显示平台账号', async ({ page }) => {
  await start(page)
  await page.locator(SETTINGS_BTN).click()
  await page.locator('.settings-tab', { hasText: '平台账号' }).click()
  await expect(page.locator('.account-card__name', { hasText: 'B 站' })).toBeVisible()
})

test('密钥已配置显示状态，输入新值保存', async ({ page }) => {
  const mock = await start(page)
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('#set-LLM_API_KEY')).toHaveAttribute('placeholder', /已配置/)
  await page.locator('#set-LLM_API_KEY').fill('sk-new')
  await page.locator('.settings-actions .btn--dark').click()
  await expect(page.locator('.settings-saved')).toBeVisible()
  const put = mock.requests.find((r) => r.method === 'PUT' && r.path === '/api/settings')
  expect(put.body.values.LLM_API_KEY).toBe('sk-new')
})

test('保存失败显示错误反馈', async ({ page }) => {
  const mock = await start(page)
  mock.settingsError = '模型名不能为空'
  await page.locator(SETTINGS_BTN).click()
  await page.locator('#set-LLM_MODEL').fill('x')
  await page.locator('.settings-actions .btn--dark').click()
  await expect(page.locator('.settings-body .field-error')).toBeVisible()
})

test('Escape 关闭面板', async ({ page }) => {
  await start(page)
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('.settings-panel')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.settings-panel')).not.toBeVisible()
})
