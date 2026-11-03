import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test, expect } from '@playwright/test'
import { MockApi } from './mock-api.js'

const SETTINGS_BTN = 'button[title="设置：模型、平台账号、本地运行"]'

async function start(page) {
  await page.addInitScript(() => localStorage.setItem('zhenxun.guide.v1', '1'))
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


test('关闭后丢弃未保存密钥和 Cookie，焦点回到入口', async ({ page }) => {
  await start(page)
  await page.locator(SETTINGS_BTN).click()
  await page.locator('#set-LLM_API_KEY').fill('unsubmitted-test-secret')
  await page.keyboard.press('Escape')
  await expect(page.locator(SETTINGS_BTN)).toBeFocused()
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('#set-LLM_API_KEY')).toHaveValue('')
  await page.getByRole('tab', { name: '平台账号' }).click()
  await page.getByRole('button', { name: '手动粘贴 Cookie' }).first().click()
  await page.locator('.paste-cookie textarea').fill('SESSDATA=unsubmitted-test-cookie')
  await page.keyboard.press('Escape')
  await page.locator(SETTINGS_BTN).click()
  await page.getByRole('tab', { name: '平台账号' }).click()
  await expect(page.locator('.paste-cookie')).toHaveCount(0)
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('unsubmitted-test')
  expect(page.url()).not.toContain('unsubmitted-test')
})

test('清除本地密钥和保存后重新打开', async ({ page }) => {
  const mock = await start(page)
  await page.locator(SETTINGS_BTN).click()
  await page.locator('#set-LLM_API_KEY').fill('test-local-key')
  await page.locator('.settings-actions button').click()
  await expect(page.locator('.settings-saved')).toBeVisible()
  await page.getByRole('button', { name: '清除本地值' }).first().click()
  await page.locator('.settings-actions button').click()
  await expect(page.locator('#set-LLM_API_KEY')).toHaveAttribute('placeholder', '未配置')
  expect(mock.requests.filter((r) => r.method === 'PUT' && r.path === '/api/settings').at(-1).body.clear).toContain('LLM_API_KEY')
  await page.keyboard.press('Escape')
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('#set-LLM_API_KEY')).toHaveAttribute('placeholder', '未配置')
})

test('关闭设置取消二维码会话，包括迟到的创建响应', async ({ page }) => {
  const mock = await start(page)
  let release
  const held = new Promise((resolve) => { release = resolve })
  await page.route('**/api/accounts/bilibili/login', async (route) => {
    await held
    await route.fulfill({ json: { id: 'late-login', state: 'waiting', qr: 'data:image/png;base64,', expires_in: 120 } })
  })
  await page.locator(SETTINGS_BTN).click()
  await page.getByRole('tab', { name: '平台账号' }).click()
  const sent = page.waitForRequest((req) => req.url().endsWith('/api/accounts/bilibili/login'))
  await page.locator('.account-card').first().getByRole('button', { name: '扫码登录', exact: true }).click()
  await sent
  await page.keyboard.press('Escape')
  release()
  await expect.poll(() => mock.requests.some((r) => r.method === 'DELETE' && r.path === '/api/accounts/login/late-login')).toBe(true)
})

test('公开站点不显示服务端配置，键盘可以切换分类', async ({ page }) => {
  const mock = await start(page)
  mock.publicDemo = true
  await page.locator(SETTINGS_BTN).click()
  await expect(page.locator('.settings-readonly')).toContainText('模型由站点管理')
  await expect(page.locator('#set-LLM_API_KEY')).toHaveCount(0)
  await page.getByRole('tab', { name: '模型与 API' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: '平台账号' })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Home')
  await expect(page.getByRole('tab', { name: '模型与 API' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('dialog', { name: '设置', exact: true }).getByRole('button', { name: '关闭', exact: true })).toBeFocused()
})

for (const [width, theme] of [[1440, 'light'], [360, 'light'], [360, 'dark']]) {
  test(`设置 ${width}px ${theme} 无横向溢出和页面错误`, async ({ page }) => {
    const errors = []
    page.on('pageerror', (error) => errors.push(error.message))
    page.on('console', (msg) => { if (msg.type() === 'error' || msg.text().startsWith('GSAP target')) errors.push(msg.text()) })
    await page.setViewportSize({ width, height: 960 })
    await page.addInitScript((value) => localStorage.setItem('gongjing.theme', value), theme)
    await start(page)
    await expect(page).toHaveTitle(/帧寻|Gong|井/i)
    await page.locator(SETTINGS_BTN).click()
    await expect(page.locator('#set-LLM_MODEL')).toBeVisible()
    await expect(page.locator('vite-error-overlay')).toHaveCount(0)
    expect(await page.locator('.settings-panel').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true)
    // Headless suite deliberately disables WebGL; the existing homepage uses its static fallback.
    expect(errors.filter((message) => !message.startsWith('THREE.WebGLRenderer:'))).toEqual([])
    await page.screenshot({ path: join(process.env.SETTINGS_QA_DIR || join(tmpdir(), 'zhenxun-settings-qa'), `settings-${width}-${theme}.png`) })
  })
}

test.describe('设置面板正常动画', () => {
  test.use({ reducedMotion: 'no-preference' })
  test('打开后焦点进入面板并在关闭时归还入口', async ({ page }) => {
    await start(page)
    await page.locator(SETTINGS_BTN).click()
    const close = page.getByRole('dialog', { name: '设置', exact: true }).getByRole('button', { name: '关闭', exact: true })
    await expect(close).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(page.getByRole('tab', { name: '模型与 API' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.locator(SETTINGS_BTN)).toBeFocused()
  })
})
