// Keyframes of the demo account's sessions, for the ad's collage: public/ad/frames/<name>/NN.jpg.
//   node record/fetch-frames.mjs
import { chromium } from 'playwright'
import { mkdir, readFile, writeFile } from 'node:fs/promises'

const BASE = process.env.ZX_URL || 'https://linyi.work/ZhenXun/'
const env = Object.fromEntries((await readFile(new URL('../.env', import.meta.url), 'utf8')).split('\n').filter((l) => l.includes('='))
  .map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1).trim()]))
const WANT = { vlookup: /vlookup/i, meme: /奶龙/ }
const browser = await chromium.launch()
const { request } = await browser.newContext()
await request.post(new URL('api/auth/login', BASE).href, { data: { name: env.ZX_USER, password: env.ZX_PASSWORD } })
const { sessions } = await (await request.get(new URL('api/sessions', BASE).href)).json()
for (const [name, title] of Object.entries(WANT)) {
  const s = sessions.find((x) => title.test(x.title))
  if (!s) { console.log(`no ${name} session`); continue }
  const job = await (await request.get(new URL(`api/sessions/${s.id}`, BASE).href)).json()
  const dir = new URL(`../public/ad/frames/${name}/`, import.meta.url)
  await mkdir(dir, { recursive: true })
  const times = []
  for (const slot of job.slots.filter((x) => x.status === 'ok')) {
    const r = await request.get(new URL(`api/link-jobs/${s.id}/frames/${slot.index}.jpg`, BASE).href)
    if (!r.ok()) continue
    await writeFile(new URL(`${String(slot.index).padStart(2, '0')}.jpg`, dir), await r.body())
    times.push({ index: slot.index, time: slot.time })
  }
  await writeFile(new URL('frames.json', dir), JSON.stringify({ title: s.title, times }, null, 1))
  console.log(name, s.title, times.length, 'frames')
}
await browser.close()
