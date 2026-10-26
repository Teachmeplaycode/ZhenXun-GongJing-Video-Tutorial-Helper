import { createClientOcrManager } from './clientOcrCore'

let manager
/** Start one page's OCR contribution. Call stop() on job change/unmount; duplicate subscribers share work. */
export function startClientOcr(jobId, options = {}) {
  if (options.mode === 'server') return () => {}
  if (!manager) manager = createClientOcrManager({
    apiBase: import.meta.env.VITE_API_BASE || '',
    assetBase: new URL(`${import.meta.env.BASE_URL}ocr/`, window.location.origin).href,
    workerFactory: () => new Worker(new URL('./ocr.worker.js', import.meta.url), { type: 'module', name: 'zhenxun-ocr' }),
  })
  return manager.start(jobId, options)
}
