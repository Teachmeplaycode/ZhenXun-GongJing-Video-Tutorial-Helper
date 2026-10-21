// Renders music/score.js to public/music/zhenxun-pv.wav: Tone.js offline in headless Chromium.
//   node music/render.mjs
import { chromium } from 'playwright'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const here = (p) => fileURLToPath(new URL(p, import.meta.url))
const cues = JSON.parse(await readFile(here('./cues.json'), 'utf8'))
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage()
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log(`[page] ${m.text()}`) })
page.on('pageerror', (e) => console.log(`[page error] ${e.message}`))
await page.setContent('<!doctype html><title>score</title>')
await page.addScriptTag({ path: here('../node_modules/tone/build/Tone.js') })
await page.addScriptTag({ path: here('./score.js') })
const b64 = await page.evaluate((c) => window.compose(c), cues)
await browser.close()
await mkdir(here('../public/music/'), { recursive: true })
await writeFile(here('../public/music/zhenxun-pv.wav'), Buffer.from(b64, 'base64'))
console.log('public/music/zhenxun-pv.wav')
