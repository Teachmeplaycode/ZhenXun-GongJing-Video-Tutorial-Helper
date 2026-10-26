import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
const OCR_FRAME = readFileSync(new URL('./fixtures/ocr-course.png', import.meta.url)).toString('base64')

test('browser Worker really recognizes Chinese course text with self-hosted models', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/ocr/README.md')
  const origin = new URL(page.url()).origin
  const external = []
  page.on('request', (request) => { if (!request.url().startsWith(origin + '/') && !request.url().startsWith('blob:') && !request.url().startsWith('data:')) external.push(request.url()) })
  const result = await page.evaluate(async (base64) => {
    const { createClientOcrManager } = await import('/src/lib/clientOcrCore.js')
    const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0)).buffer
    let claim = 0, received, manager
    const statuses = []
    const started = performance.now()
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { manager.close(); reject(new Error(JSON.stringify(statuses))) }, 100_000)
      const json = (value) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
      manager = createClientOcrManager({
        workerFactory: () => new Worker(new URL('/src/lib/ocr.worker.js', location.origin), { type: 'module' }),
        assetBase: new URL('/ocr/', location.origin).href,
        events: null, visibility: null, hidden: () => false,
        fetch: async (url, options = {}) => {
          if (url.endsWith('/claim')) return json(++claim === 1 ? { state: 'ready', mode: 'local', lease_id: 'real', lease_seconds: 20,
            frames: [{ id: 0, time: 0, url: '/api/link-jobs/ocr-real/ocr/frames/real/0.jpg' }] } : { state: 'done', mode: 'local' })
          if (url.endsWith('/result')) { received = JSON.parse(options.body); return json({ accepted: 1, progress: { done: 1, total: 1, local: 1, server: 0 } }) }
          if (url.endsWith('/heartbeat') || url.endsWith('/release')) return json({ state: 'ready' })
          return new Response(bytes.slice(0), { headers: { 'Content-Type': 'image/png' } })
        },
      })
      manager.start('ocr-real', { mode: 'local', onStatus: (status) => {
        statuses.push(status)
        if (status.phase === 'error') { clearTimeout(timeout); manager.close(); reject(new Error(status.message)) }
        if (status.phase === 'done') {
          clearTimeout(timeout); manager.close()
          resolve({ received, elapsed: performance.now() - started, statuses })
        }
      } })
    })
  }, OCR_FRAME)
  const lines = result.received.results[0].lines
  const text = lines.map((line) => line.text).join(' ')
  console.log(`Real OCR ${test.info().project.name}: ${Math.round(result.elapsed)}ms, ${text}`)
  expect(text).toContain('数据结构')
  expect(text).toContain('二叉树')
  expect(lines.length).toBeLessThanOrEqual(200)
  for (const line of lines) for (const key of ['confidence', 'x', 'y', 'w', 'h']) expect(line[key]).toBeGreaterThanOrEqual(0)
  for (const line of lines) for (const key of ['confidence', 'x', 'y', 'w', 'h']) expect(line[key]).toBeLessThanOrEqual(1)
  expect(external.filter((url) => /onnx|wasm|ocr-model|jsdelivr|unpkg/.test(url))).toEqual([])
})
