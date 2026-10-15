import * as THREE from 'three'
import { SCULPTURE_SETTINGS } from '../config/workspace.js'

// Sample a glyph mask once, keeping a regular spacing along its strokes.
export function sampleWordMask(mask, width, height, count) {
  let ink = 0
  for (let i = 3; i < mask.length; i += 4) if (mask[i] >= 96) ink += 1
  if (!ink) return []
  let step = Math.max(1, Math.sqrt(ink / count) * 0.99)
  let points = []
  for (let attempt = 0; attempt < 12; attempt += 1) {
    points = []
    for (let y = step / 2; y < height; y += step) {
      for (let x = step / 2; x < width; x += step) {
        if (mask[(Math.floor(y) * width + Math.floor(x)) * 4 + 3] >= 96) points.push({ x, y })
      }
    }
    if (points.length >= count) break
    step *= 0.97
  }
  if (!points.length) return []
  const selected = Array.from({ length: count }, (_, i) => points[Math.floor((i + 0.5) * points.length / count)])
  // Stable shuffle makes individual sheets fan into all characters together.
  let seed = 7351
  for (let i = selected.length - 1; i > 0; i -= 1) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0
    const j = seed % (i + 1)
    ;[selected[i], selected[j]] = [selected[j], selected[i]]
  }
  return selected.map((point) => ({ ...point, step }))
}

// Fit the actual ink bounds into the viewport without stretching the characters.
export function fitWordDistance(layout, width, height, fov, padding, footerSpace = padding) {
  const inset = Math.min(padding, width * 0.24, height * 0.24)
  const bottom = Math.min(Math.max(inset, footerSpace), height * 0.4)
  const tangent = Math.tan(THREE.MathUtils.degToRad(fov) / 2)
  return Math.max(
    layout.width * height / (2 * tangent * (width - 2 * inset)),
    layout.height * height / (2 * tangent * (height - inset - bottom)),
  ) + layout.depth
}

export function buildWordLayouts(count, sheetSize, view) {
  if (typeof document === 'undefined') return []
  const settings = SCULPTURE_SETTINGS.scatterText
  const undoView = new THREE.Quaternion().setFromEuler(new THREE.Euler(view.x, view.y, view.z)).invert()
  return settings.words.map((word) => {
    const canvas = document.createElement('canvas')
    const characters = Array.from(word)
    const advance = 145
    canvas.width = advance * characters.length
    canvas.height = 160
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return { poses: [], width: 0, height: 0, depth: 0 }
    ctx.font = '800 132px "PingFang SC", "Microsoft YaHei", sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = '#ffffff'
    characters.forEach((character, i) => ctx.fillText(character, advance * (i + 0.5), 80))
    const mask = ctx.getImageData(0, 0, canvas.width, canvas.height)
    const points = sampleWordMask(mask.data, canvas.width, canvas.height, count)
    if (!points.length) return { poses: [], width: 0, height: 0, depth: 0 }
    const unit = settings.height / canvas.height
    const halfCell = points[0].step * settings.plateSize / 2
    const minX = Math.min(...points.map((p) => p.x)) - halfCell
    const maxX = Math.max(...points.map((p) => p.x)) + halfCell
    const minY = Math.min(...points.map((p) => p.y)) - halfCell
    const maxY = Math.max(...points.map((p) => p.y)) + halfCell
    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2
    const poses = points.map(({ x, y, step }, i) => {
      const size = step * unit * settings.plateSize
      const tilt = new THREE.Quaternion().setFromEuler(new THREE.Euler(
        Math.sin(i * 1.7) * 0.08, Math.cos(i * 2.1) * 0.1, Math.sin(i * 0.7) * 0.025,
      ))
      return {
        position: new THREE.Vector3(
          (x - centerX) * unit,
          (centerY - y) * unit,
          Math.sin(i * 2.4) * settings.depth,
        ).applyQuaternion(undoView),
        rotation: undoView.clone().multiply(tilt),
        scale: new THREE.Vector3(size / sheetSize.width, size / sheetSize.height, 1),
      }
    })
    return {
      poses,
      width: (maxX - minX) * unit,
      height: (maxY - minY) * unit,
      depth: settings.depth + halfCell * unit * 0.12 + sheetSize.thickness / 2,
    }
  })
}
