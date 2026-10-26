import Ocr, { ImageRawBase, FileUtilsBase, registerBackend } from '@gutenye/ocr-common'
import * as ort from 'onnxruntime-web/wasm'
import cv from '@techstark/opencv-js'
import { setImageBackend, splitIntoLineImages } from './ocrContours'

const MODEL_VERSION = '1.4.2'
const CACHE = 'zhenxun-ocr-assets-v1'
let ocrPromise
const imageCache = new Map()

async function asset(url) {
  let cache
  try {
    cache = await caches.open(CACHE)
    const stored = await cache.match(url)
    if (stored) return stored
  } catch { /* private mode can deny persistent storage */ }
  const response = await fetch(url, { credentials: 'same-origin', cache: 'force-cache' })
  if (!response.ok) throw new Error(`OCR 模型下载失败（${response.status}）`)
  try { await cache?.put(url, response.clone()) } catch { /* storage quota: retain the downloaded response */ }
  return response
}

class WorkerImage extends ImageRawBase {
  constructor({ data, width, height }) {
    const copy = Uint8ClampedArray.from(data)
    super({ data: copy, width, height })
    this.canvas = new OffscreenCanvas(width, height)
    this.canvas.getContext('2d').putImageData(new ImageData(copy, width, height), 0, 0)
  }
  async resize({ width, height }) {
    const w = width || Math.max(1, Math.round(this.width * height / this.height))
    const h = height || Math.max(1, Math.round(this.height * width / this.width))
    const canvas = new OffscreenCanvas(w, h)
    const context = canvas.getContext('2d', { willReadFrequently: true })
    context.drawImage(this.canvas, 0, 0, w, h)
    this.canvas = canvas
    this.width = w
    this.height = h
    this.data = context.getImageData(0, 0, w, h).data
    return this
  }
  async write() { /* debug image output is disabled in the browser */ }
}

class WorkerFiles extends FileUtilsBase {
  static async read(url) { return (await asset(url)).text() }
}

async function ready(base) {
  if (!ocrPromise) ocrPromise = (async () => {
    if (!self.OffscreenCanvas || !self.WebAssembly || !self.createImageBitmap) throw new Error('此浏览器不支持本机 OCR')
    ort.env.wasm.numThreads = 1 // works without COOP/COEP or SharedArrayBuffer
    ort.env.wasm.proxy = false
    ort.env.wasm.wasmPaths = new URL('runtime/1.20.1/', base).href
    const deadline = Date.now() + 20_000
    while (!cv.Mat) {
      if (Date.now() >= deadline) throw new Error('画面处理模块初始化超时')
      await new Promise((resolve) => setTimeout(resolve, 20))
    }
    setImageBackend(WorkerImage)
    registerBackend({ ImageRaw: WorkerImage, FileUtils: WorkerFiles, InferenceSession: ort.InferenceSession, splitIntoLineImages })
    const model = (name) => new URL(`models/${MODEL_VERSION}/${name}`, base).href
    const [detector, recognizer] = await Promise.all([
      asset(model('ch_PP-OCRv4_det_infer.onnx')).then((r) => r.arrayBuffer()),
      asset(model('ch_PP-OCRv4_rec_infer.onnx')).then((r) => r.arrayBuffer()),
    ])
    return Ocr.create({ models: {
      detectionPath: new Uint8Array(detector), recognitionPath: new Uint8Array(recognizer),
      dictionaryPath: model('ppocr_keys_v1.txt'),
    }, onnxOptions: { executionProviders: ['wasm'], graphOptimizationLevel: 'all' } })
  })().catch((error) => { ocrPromise = null; throw error })
  return ocrPromise
}

const clamp = (value) => Math.min(1, Math.max(0, value))
function linesFrom(result) {
  const width = result.resizedImageWidth, height = result.resizedImageHeight
  return (result.texts || []).flatMap((line) => {
    const text = String(line.text || '').trim().slice(0, 2000)
    const box = line.box
    if (!text || !box?.length) return []
    const xs = box.map((p) => p[0]), ys = box.map((p) => p[1])
    const x = clamp(Math.min(...xs) / width), y = clamp(Math.min(...ys) / height)
    const w = Math.min(1 - x, clamp((Math.max(...xs) - Math.min(...xs)) / width))
    const h = Math.min(1 - y, clamp((Math.max(...ys) - Math.min(...ys)) / height))
    const confidence = clamp(Number(line.mean ?? line.score ?? 0))
    return [x, y, w, h, confidence].every(Number.isFinite) && w > 0 && h > 0
      ? [{ text, confidence, x, y, w, h }] : []
  }).slice(0, 200)
}

async function detect(buffer, base) {
  const engine = await ready(base)
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer)), (b) => b.toString(16).padStart(2, '0')).join('')
  if (imageCache.has(digest)) return imageCache.get(digest)
  const bitmap = await createImageBitmap(new Blob([buffer]))
  try {
    // The server supplies 540p OCR samples. Bound an unexpected large image without upscaling it.
    const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height))
    const canvas = new OffscreenCanvas(Math.max(1, Math.round(bitmap.width * scale)), Math.max(1, Math.round(bitmap.height * scale)))
    const context = canvas.getContext('2d', { willReadFrequently: true })
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const image = context.getImageData(0, 0, canvas.width, canvas.height)
    const lines = linesFrom(await engine.detect({ data: image.data, width: image.width, height: image.height }))
    imageCache.set(digest, lines)
    if (imageCache.size > 32) imageCache.delete(imageCache.keys().next().value)
    return lines
  } finally { bitmap.close() }
}

self.onmessage = async ({ data }) => {
  const started = performance.now()
  try {
    const result = data.type === 'init' ? (await ready(data.base), null) : await detect(data.buffer, data.base)
    self.postMessage({ id: data.id, result, elapsed: performance.now() - started })
  } catch (error) {
    self.postMessage({ id: data.id, error: String(error?.message || '本机文字识别失败') })
  }
}
