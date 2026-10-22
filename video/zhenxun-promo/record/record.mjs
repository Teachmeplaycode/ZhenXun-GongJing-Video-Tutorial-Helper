// Records scenes of the live site for the promo film, one mp4 per scene, with a camera track:
// every move / click / keystroke the script makes, its time from the start of the recording and
// where on the page it happened (CSS px of a 1920×1080 page). The film's camera follows that track.
//
//   node record/record.mjs import ask         # some scenes, in order
//   node record/record.mjs                    # all of them
// Scenes run signed in as the demo account (ZX_USER / ZX_PASSWORD in video/zhenxun-promo/.env); the
// ones after `import` work in the session it creates (the newest one in 历史).
//
// The recording is made at twice the size (3840×2160) so the camera can zoom in and stay sharp: the
// page is a normal 1920×1080 window at 2× device pixels (its real layout), and the frames come from
// Chrome's screencast at full device resolution, each with its own timestamp; ffmpeg puts them
// together at 30 fps. Track coordinates are in recording pixels (CSS px × 2).
import { chromium } from 'playwright'
import { execFile } from 'node:child_process'
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'

const URL_BASE = process.env.ZX_URL || 'https://linyi.work/ZhenXun/'
const OUT = fileURLToPath(new URL('../public/rec/', import.meta.url))
const W = 1920
const H = 1080
const ZOOM = 2
// An Excel VLOOKUP tutorial from the held-out tutorial set (tut-vlookup): the film's software-tutorial case.
const LINK = process.env.ZX_LINK || 'https://www.bilibili.com/video/BV1M34y1C7HZ'
const ENV = Object.fromEntries((await readFile(new URL('../.env', import.meta.url), 'utf8').catch(() => '')).split('\n')
  .filter((l) => l.includes('=')).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1).trim()]))

// A visible cursor (recordings have none): an arrow that follows the mouse and dips on press.
const CURSOR = () => {
  const make = () => {
    if (document.getElementById('zx-cursor')) return
    const el = document.createElement('div')
    el.id = 'zx-cursor'
    el.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.5 16 L12.5 24 L16 22.4 L12 14.6 L19.5 14.6 Z" fill="#1a1a1a" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'
    Object.assign(el.style, { position: 'fixed', left: '0', top: '0', zIndex: 2147483647, pointerEvents: 'none',
      transform: 'translate(-100px,-100px)', transition: 'scale 90ms ease', transformOrigin: '3px 2px' })
    document.documentElement.appendChild(el)
    addEventListener('mousemove', (e) => { el.style.transform = `translate(${e.clientX - 3}px,${e.clientY - 2}px)` }, true)
    addEventListener('mousedown', () => { el.style.scale = '0.82' }, true)
    addEventListener('mouseup', () => { el.style.scale = '1' }, true)
  }
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', make)
  else make()
}

async function scene(name, act, { width = W, height = H, mobile = false, zoom = ZOOM } = {}) {
  const ZOOM = zoom
  await mkdir(OUT, { recursive: true })
  // A real window on the Mac's GPU: headless Chromium renders the 3D homepage at 4K on the CPU, too slowly.
  const browser = await chromium.launch({ headless: process.env.ZX_HEADLESS === '1', args: ['--enable-gpu-rasterization', '--ignore-gpu-blocklist', '--window-size=1920,1080'] })
  const context = await browser.newContext({
    viewport: { width, height }, deviceScaleFactor: ZOOM, isMobile: mobile, hasTouch: mobile,
    locale: 'zh-CN', reducedMotion: 'no-preference', colorScheme: 'light',
  })
  await context.addInitScript(() => {
    try { localStorage.setItem('zhenxun.guide.v1', '1') } catch { /* fine */ }
  })
  await context.addInitScript(CURSOR)
  const page = await context.newPage()
  // signed in as the demo account before anything is shown (the cookie comes from the API)
  if (ENV.ZX_USER) {
    const r = await context.request.post(new URL('api/auth/login', URL_BASE).href, { data: { name: ENV.ZX_USER, password: ENV.ZX_PASSWORD } })
    if (!r.ok()) throw new Error(`login failed: ${r.status()}`)
  }
  const frames = `${OUT}${name}-frames/`
  await rm(frames, { recursive: true, force: true })
  await mkdir(frames, { recursive: true })
  const shots = [] // [file, timestamp s]
  const cdp = await context.newCDPSession(page)
  const pending = []
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    const file = `${String(shots.length).padStart(5, '0')}.jpg`
    shots.push([file, metadata.timestamp])
    pending.push(writeFile(`${frames}${file}`, Buffer.from(data, 'base64')))
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
  })
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: width * ZOOM, maxHeight: height * ZOOM, everyNthFrame: 1 })
  const t0 = Date.now()
  const track = []
  let mouse = { x: width / 2, y: height * 0.6 } // CSS px; logged ×ZOOM
  const now = () => (Date.now() - t0) / 1000
  const big = (b) => b && { x: Math.round(b.x * ZOOM), y: Math.round(b.y * ZOOM), width: Math.round(b.width * ZOOM), height: Math.round(b.height * ZOOM) }
  const log = (type, extra = {}) => track.push({ t: +now().toFixed(3), type, x: Math.round(mouse.x * ZOOM), y: Math.round(mouse.y * ZOOM), ...extra })

  const cam = {
    page,
    wait: (ms) => page.waitForTimeout(ms),
    mark: (label) => log('mark', { label }),
    // Glide to an element (or a point) in steps, like a hand.
    async moveTo(target, { ms = 650 } = {}) {
      let x
      let y
      let box = null
      if (typeof target === 'string' || typeof target?.boundingBox === 'function') {
        box = await (typeof target === 'string' ? page.locator(target).first() : target).boundingBox()
        x = box.x + Math.min(box.width * 0.18, 60)
        y = box.y + box.height / 2
      } else ({ x, y } = target)
      const steps = Math.max(12, Math.round(ms / 16))
      const from = { ...mouse }
      log('move', { to: { x: Math.round(x * ZOOM), y: Math.round(y * ZOOM) }, ms, box: big(box) })
      for (let i = 1; i <= steps; i += 1) {
        const k = i / steps
        const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2
        mouse = { x: from.x + (x - from.x) * e, y: from.y + (y - from.y) * e }
        await page.mouse.move(mouse.x, mouse.y)
        await page.waitForTimeout(ms / steps)
      }
      return box
    },
    async click(target) {
      const box = await cam.moveTo(target)
      log('click', { box: big(box) })
      await page.mouse.down()
      await page.waitForTimeout(90)
      await page.mouse.up()
    },
    async type(text, { delay = 75 } = {}) {
      for (const ch of text) {
        log('key', { ch })
        await page.keyboard.type(ch)
        await page.waitForTimeout(delay + Math.random() * 40)
      }
    },
    async press(key) {
      log('press', { key })
      await page.keyboard.press(key)
    },
    /** Scroll the element (or page) under the mouse, smoothly. */
    async scroll(dy, { ms = 900 } = {}) {
      log('scroll', { dy })
      const steps = Math.max(10, Math.round(ms / 30))
      for (let i = 0; i < steps; i += 1) { await page.mouse.wheel(0, dy / steps); await page.waitForTimeout(ms / steps) }
    },
    /** Open the newest session from 历史 (the one `import` made). */
    async openLatest() {
      await cam.click('.btn--history')
      await page.waitForSelector('.session-item__open', { timeout: 15000 })
      await cam.wait(500)
      await cam.click('.session-item__open')
      await page.waitForSelector('.composer__input', { timeout: 60000 })
      await cam.wait(1200)
    },
    /** Wait until the agent has finished answering (the stop button is gone). */
    async answered({ timeout = 180000 } = {}) {
      await page.waitForSelector('button[aria-label="停止"]', { timeout: 15000 }).catch(() => {})
      await page.waitForSelector('button[aria-label="停止"]', { state: 'detached', timeout })
      await cam.wait(800)
    },
  }

  await page.goto(URL_BASE, { waitUntil: 'networkidle' })
  log('ready')
  await act(cam)
  await page.waitForTimeout(400)
  await cdp.send('Page.stopScreencast').catch(() => {})
  await Promise.all(pending)
  await context.close()
  await browser.close()
  // Frames come when the page repaints: each one lasts until the next (ffconcat durations), then 30 fps.
  const first = shots[0][1]
  const lines = ['ffconcat version 1.0']
  shots.forEach(([file, ts], i) => {
    const next = i + 1 < shots.length ? shots[i + 1][1] : ts + 0.04
    lines.push(`file '${file}'`, `duration ${Math.max(0.001, next - ts).toFixed(4)}`)
  })
  await writeFile(`${frames}list.ffconcat`, lines.join('\n') + '\n')
  await promisify(execFile)('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', `${frames}list.ffconcat`,
    '-vf', `fps=30,scale=${width * ZOOM}:${height * ZOOM}:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-crf', '14', '-preset', 'medium',
    `${OUT}${name}.mp4`])
  // The track's clock starts at t0; the video's at its first frame.
  const offset = first - t0 / 1000
  await writeFile(`${OUT}${name}.json`, JSON.stringify({ name, width: width * ZOOM, height: height * ZOOM, fps: 30,
    track: track.map((e) => ({ ...e, t: +(e.t - offset).toFixed(3) })) }, null, 1))
  await rm(frames, { recursive: true, force: true })
  console.log(`${name}: ${shots.length} frames, ${track.length} camera events → public/rec/${name}.mp4`)
}

const SCENES = {
  // the homepage: the wordmark and the sculpture, the cursor wandering over the nav
  async home(cam) {
    await cam.wait(2500)
    await cam.moveTo({ x: 1400, y: 520 }, { ms: 1400 })
    await cam.wait(800)
    await cam.moveTo('.btn--history', { ms: 900 })
    await cam.wait(500)
    await cam.moveTo('.import-control__link', { ms: 900 })
    await cam.wait(1200)
  },
  // a link pasted in, 开始解析, the whole analysis (it takes minutes: speed it up in the edit), into the chat
  async import(cam) {
    await cam.wait(1800)
    cam.mark('wide')
    await cam.click('.import-control__link')
    await cam.wait(300)
    await cam.type(LINK)
    await cam.wait(500)
    await cam.click('.import-control__submit')
    cam.mark('analysing')
    const next = cam.page.locator('.btn--next:not(.btn--early)')
    await next.waitFor({ state: 'visible', timeout: 600000 })
    cam.mark('ready')
    await cam.wait(1200)
    await cam.click('.btn--next:not(.btn--early)')
    await cam.page.waitForSelector('.composer__input', { timeout: 60000 })
    await cam.wait(2000)
  },
}

Object.assign(SCENES, {
  // asking in words: the question typed, the answer streaming in with its evidence chips
  async ask(cam) {
    await cam.openLatest()
    await cam.click('.composer__input')
    await cam.type('第二参数框选数据范围后，按哪个键做绝对引用？', { delay: 90 })
    await cam.wait(500)
    await cam.press('Enter')
    cam.mark('asked')
    await cam.answered()
    await cam.moveTo('.ev-chip', { ms: 900 })
    await cam.wait(1800)
  },
  // an evidence chip clicked: the original video opens at that moment and plays
  async evidence(cam) {
    await cam.openLatest()
    await cam.page.locator('.chat__scroll').evaluate((el) => { el.scrollTop = el.scrollHeight })
    await cam.wait(800)
    await cam.click('button.ev-chip')
    cam.mark('seek')
    await cam.page.waitForSelector('.source-player', { timeout: 20000 })
    await cam.wait(7000)
    await cam.click('button[aria-label="关闭原片"]').catch(() => {})
    await cam.wait(800)
  },
  // the timeline: slats rising as the cursor runs along them, a preview of each frame
  async timeline(cam) {
    await cam.openLatest()
    const cards = cam.page.locator('.tl-card')
    const n = await cards.count()
    for (let i = 0; i < Math.min(n, 60); i += Math.max(1, Math.floor(n / 12))) {
      await cam.moveTo(cards.nth(i), { ms: 380 })
      await cam.wait(260)
    }
    await cam.wait(1200)
  },
  // a stretch dragged out on the timeline and played back slowly, frame by frame
  async replay(cam) {
    await cam.openLatest()
    const cards = cam.page.locator('.tl-card')
    const n = await cards.count()
    const a = await cards.nth(Math.floor(n * 0.3)).boundingBox()
    const b = await cards.nth(Math.floor(n * 0.4)).boundingBox()
    await cam.moveTo({ x: a.x + a.width / 2, y: a.y + a.height / 2 })
    await cam.page.mouse.down()
    await cam.moveTo({ x: b.x + b.width / 2, y: b.y + b.height / 2 }, { ms: 1100 })
    await cam.page.mouse.up()
    await cam.wait(700)
    await cam.click('button:has-text("直接慢放")')
    cam.mark('replay')
    await cam.wait(9000)
  },
  // stuck: a screenshot of the screen attached, sent without words — the answer finds the step
  async screenshot(cam) {
    await cam.openLatest()
    // the screenshot: a frame of the tutorial itself, taken from the original player
    await cam.page.locator('button.ev-chip').first().click()
    await cam.page.waitForSelector('.source-player__video', { timeout: 20000 })
    await cam.page.waitForTimeout(3000)
    const shot = `${OUT}stuck.png`
    await cam.page.locator('.source-player__video').screenshot({ path: shot })
    await cam.page.locator('button[aria-label="关闭原片"]').click().catch(() => {})
    await cam.wait(1000)
    await cam.moveTo('.composer__attach')
    await cam.page.locator('.composer input[type=file]').setInputFiles(shot)
    cam.mark('attached')
    await cam.wait(1500)
    await cam.click('.composer__input')
    await cam.press('Enter')
    await cam.answered()
    await cam.wait(1500)
  },
  // Tab completion: a few letters typed, the rest of the question offered in grey, Tab takes it
  async tab(cam) {
    await cam.openLatest()
    await cam.click('.composer__input')
    await cam.type('VLOOKUP 多条件', { delay: 120 })
    await cam.page.waitForSelector('.composer__ghost-rest', { timeout: 12000 }).catch(() => {})
    await cam.wait(1400)
    await cam.press('Tab')
    cam.mark('completed')
    await cam.wait(2200)
  },
  // notes: generated by chapter, previewed, saved as one long picture
  async notes(cam) {
    await cam.openLatest()
    await cam.click('button.bench__tab:has-text("笔记")')
    await cam.wait(800)
    const make = cam.page.locator('.notes-tab button.btn--dark').first()
    if (await cam.page.locator('.notes-tab__done').count() === 0) await cam.click(make)
    await cam.page.waitForSelector('.notes-tab__done', { timeout: 420000 })
    cam.mark('notes')
    await cam.wait(1500)
    await cam.click('button:has-text("预览导出")')
    await cam.wait(3500)
    await cam.scroll(900, { ms: 2000 })
    await cam.wait(1000)
    await cam.press('Escape')
    await cam.wait(800)
    await cam.click('button:has-text("存为长图")')
    await cam.page.waitForSelector('.preview-dialog img', { timeout: 90000 }).catch(() => {})
    await cam.wait(2000)
    await cam.scroll(1400, { ms: 2600 })
    await cam.wait(1200)
  },
  // 历史: past sessions, with their covers
  async history(cam) {
    await cam.wait(1200)
    await cam.click('.btn--history')
    await cam.wait(900)
    await cam.moveTo('.session-item__open', { ms: 800 })
    await cam.wait(2200)
  },
  // 我的: the profile drawer (plan, daily use, platform logins)
  async profile(cam) {
    await cam.wait(1200)
    await cam.click('.member-chip')
    await cam.wait(1200)
    await cam.moveTo('.profile__meter', { ms: 900 }).catch(() => {})
    await cam.wait(2200)
  },
  // 文档
  async docs(cam) {
    await cam.wait(1200)
    await cam.click('button:has-text("文档")')
    await cam.wait(1500)
    await cam.moveTo({ x: 960, y: 600 })
    await cam.scroll(1200, { ms: 2500 })
    await cam.wait(1500)
  },
})

const MOBILE = {
  // a phone: the homepage, a session, the 画面 tab's frame grid, the notes as a long picture
  async phone(cam) {
    await cam.wait(2500)
    await cam.openLatest()
    await cam.click('.bench__handle').catch(() => {})
    await cam.wait(600)
    await cam.click('button.bench__tab:has-text("画面")').catch(() => {})
    await cam.wait(1800)
    await cam.click('.picker__tile').catch(() => {})
    await cam.wait(1200)
    await cam.click('button.bench__tab:has-text("笔记")').catch(() => {})
    await cam.wait(800)
    await cam.click('button:has-text("存为长图")').catch(() => {})
    await cam.page.waitForSelector('.preview-dialog img', { timeout: 90000 }).catch(() => {})
    await cam.wait(1500)
    await cam.scroll(1600, { ms: 3000 })
    await cam.wait(1200)
  },
}

const wanted = process.argv.slice(2)
for (const name of wanted.length ? wanted : [...Object.keys(SCENES), ...Object.keys(MOBILE)]) {
  if (SCENES[name]) await scene(name, SCENES[name])
  else if (MOBILE[name]) await scene(name, MOBILE[name], { width: 390, height: 844, mobile: true, zoom: 3 })
  else throw new Error(`no scene ${name}`)
}
