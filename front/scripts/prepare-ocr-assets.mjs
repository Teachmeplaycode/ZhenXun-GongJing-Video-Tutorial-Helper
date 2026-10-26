import { mkdir, copyFile, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
const root = fileURLToPath(new URL('../', import.meta.url))
const items = [
  ['@gutenye/ocr-models/assets/ch_PP-OCRv4_det_infer.onnx', 'models/1.4.2/ch_PP-OCRv4_det_infer.onnx'],
  ['@gutenye/ocr-models/assets/ch_PP-OCRv4_rec_infer.onnx', 'models/1.4.2/ch_PP-OCRv4_rec_infer.onnx'],
  ['@gutenye/ocr-models/assets/ppocr_keys_v1.txt', 'models/1.4.2/ppocr_keys_v1.txt'],
  ['onnxruntime-web/dist/ort-wasm-simd-threaded.wasm', 'runtime/1.20.1/ort-wasm-simd-threaded.wasm'],
  ['onnxruntime-web/dist/ort-wasm-simd-threaded.mjs', 'runtime/1.20.1/ort-wasm-simd-threaded.mjs'],
]
const manifest = {}
for (const [source, target] of items) {
  const from = resolve(root, 'node_modules', source), to = resolve(root, 'public/ocr', target)
  await mkdir(resolve(to, '..'), { recursive: true })
  await copyFile(from, to)
  manifest[target] = createHash('sha256').update(await readFile(from)).digest('hex')
}
await writeFile(resolve(root, 'public/ocr/manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
console.log('Prepared self-hosted OCR models and WASM runtime')
