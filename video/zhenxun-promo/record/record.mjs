// Records scenes of the live site for the promo film, one webm per scene, with a camera track:
// every move / click / keystroke the script makes, its time from the start of the recording and
// where on the page it happened (CSS px of a 1920×1080 page). The film's camera follows that track.
//
//   node record/record.mjs opening            # one scene
//   ZX_URL=https://linyi.work/ZhenXun/ node record/record.mjs opening
//
// The recording is made at twice the size (3840×2160) so the camera can zoom in and stay sharp: the
// page is a normal 1920×1080 window at 2× device pixels (its real layout), and the frames come from
// Chrome's screencast at full device resolution, each with its own timestamp; ffmpeg puts them
// together at 30 fps. Track coordinates are in recording pixels (CSS px × 2).
import { chromium } from 'playwright'
import { execFile } from 'node:child_process'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'

const URL_BASE = process.env.ZX_URL || 'https://linyi.work/ZhenXun/'
const OUT = fileURLToPath(new URL('../public/rec/', import.meta.url))
const W = 1920
const H = 1080
const ZOOM = 2
const LINK = process.env.ZX_LINK || 'https://www.bilibili.com/video/BV1gD421u75J'

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

async function scene(name, act, { width = W, height = H, mobile = false } = {}) {
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
      if (typeof target === 'string') {
        box = await page.locator(target).first().boundingBox()
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
  // 0–6 s: the homepage, then a close-up of typing the link, Enter.
  async opening(cam) {
    await cam.wait(2600) // the sculpture settles: the wide shot of the homepage
    cam.mark('wide')
    await cam.click('.import-control__link')
    await cam.wait(300)
    await cam.type(LINK)
    await cam.wait(450)
    await cam.press('Enter')
    cam.mark('enter')
    await cam.wait(700)
  },
}

const wanted = process.argv.slice(2)
for (const name of wanted.length ? wanted : Object.keys(SCENES)) {
  if (!SCENES[name]) throw new Error(`no scene ${name}`)
  await scene(name, SCENES[name])
}
