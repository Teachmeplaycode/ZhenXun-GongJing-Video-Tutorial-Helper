// Looks around the live site as the demo account: its sessions, and what can be clicked.
//   node record/probe.mjs [outdir]
import { chromium } from 'playwright'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const here = (p) => fileURLToPath(new URL(p, import.meta.url))
const env = Object.fromEntries((await readFile(here('../.env'), 'utf8')).split('\n').filter((l) => l.includes('=')).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]))
const BASE = process.env.ZX_URL || 'https://linyi.work/ZhenXun/'
const out = process.argv[2] || '.'
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: 'zh-CN' })
await context.addInitScript(() => { try { localStorage.setItem('zhenxun.guide.v1', '1') } catch {} })
const page = await context.newPage()
await page.goto(BASE, { waitUntil: 'networkidle' })
const login = await page.request.post(new URL('api/auth/login', BASE).href, { data: { name: env.ZX_USER, password: env.ZX_PASSWORD } })
console.log('login', login.status())
const sessions = await (await page.request.get(new URL('api/sessions', BASE).href)).json()
console.log('sessions', JSON.stringify(sessions).slice(0, 600))
await page.reload({ waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
await page.screenshot({ path: `${out}/home.png` })
const clickables = await page.$$eval('button, a, [role=button], input, textarea', (els) => els.map((e) => `${e.tagName.toLowerCase()}.${(e.className || '').toString().split(' ').join('.')} "${(e.getAttribute('aria-label') || e.textContent || e.getAttribute('placeholder') || '').trim().slice(0, 30)}"`))
console.log(clickables.join('\n'))
await browser.close()
