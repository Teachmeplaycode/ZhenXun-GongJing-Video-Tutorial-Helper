import React, { useEffect, useRef } from 'react'
import { CONTOUR_SETTINGS } from '../config/workspace'
import { token } from '../lib/tokens'
import { isLowEndDevice, prefersReducedMotion } from '../lib/motion'

// Contour terrain loader (design_2.md §6), pure Canvas 2D pseudo-3D.
// The height field reuses the warped-fbm terrain of the videoComprehensive MVP
// (ui/src/components/Terrain.jsx), sharpened into exaggerated peaks. Closed iso-lines are
// extracted with marching squares, then stacked as terraces lifted by their elevation and
// drawn level by level from the lowest one upward, looping.

const GRID = 132
const LEVELS = CONTOUR_SETTINGS.levels
const CYCLE = CONTOUR_SETTINGS.cycle // s, bottom → top
const HOLD = CONTOUR_SETTINGS.hold // s, finished terrain stays before fading
const FADE = CONTOUR_SETTINGS.fade // s
const MAX_CANVAS = 2400
const YAW_SPEED = 0.06 // rad/s
const TILT = CONTOUR_SETTINGS.tilt // vertical squash of the ground plane
const RELIEF = CONTOUR_SETTINGS.relief // total elevation as a fraction of canvas height

const hash = (x, y) => {
  let h = Math.imul(x, 374761393) + Math.imul(y, 668265263)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295
}
const noise = (x, y) => {
  const ix = Math.floor(x); const iy = Math.floor(y)
  const fx = x - ix; const fy = y - iy
  const u = fx * fx * (3 - 2 * fx); const v = fy * fy * (3 - 2 * fy)
  const a = hash(ix, iy); const b = hash(ix + 1, iy); const c = hash(ix, iy + 1); const d = hash(ix + 1, iy + 1)
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v
}
const fbm = (x, y) => {
  let sum = 0; let amp = 0.5; let freq = 1
  for (let o = 0; o < 5; o += 1) { sum += amp * noise(x * freq, y * freq); freq *= 2; amp *= 0.5 }
  return sum
}
const rawHeight = (x, z) => {
  const wx = x + 6 * fbm(x * 0.05 + 11, z * 0.05 + 3)
  const wz = z + 6 * fbm(x * 0.05 + 5, z * 0.05 + 17)
  const base = fbm(wx * 0.055 + 3, wz * 0.055 + 7)
  const ridge = 1 - Math.abs(2 * fbm(wx * 0.04 + 20, wz * 0.04 + 9) - 1)
  return 0.62 * base + 0.38 * ridge * ridge
}
const smooth = (e0, e1, x) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)))
  return t * t * (3 - 2 * t)
}

// Height field on [-1, 1]²: sharpened terrain + two dominant summits, forced to 0 at the
// rim so every contour above sea level is a closed loop.
function buildField() {
  const n = GRID + 1
  const h = new Float32Array(n * n)
  let lo = Infinity; let hi = -Infinity
  for (let j = 0; j < n; j += 1) {
    for (let i = 0; i < n; i += 1) {
      const x = (i / GRID) * 2 - 1
      const y = (j / GRID) * 2 - 1
      const v = rawHeight(x * 40, y * 40)
      h[j * n + i] = v
      lo = Math.min(lo, v); hi = Math.max(hi, v)
    }
  }
  const peak = (x, y, px, py, r) => Math.exp(-((x - px) ** 2 + (y - py) ** 2) / (r * r))
  let max = 0
  for (let j = 0; j < n; j += 1) {
    for (let i = 0; i < n; i += 1) {
      const x = (i / GRID) * 2 - 1
      const y = (j / GRID) * 2 - 1
      const base = ((h[j * n + i] - lo) / (hi - lo)) ** 1.6
      const summits = 0.95 * peak(x, y, -0.18, -0.12, 0.34) + 0.7 * peak(x, y, 0.36, 0.28, 0.24)
      const rim = (x ** 4 + y ** 4) ** 0.25 // rounded-square plate
      const window = 1 - smooth(0.62, 0.96, rim)
      const v = (0.55 * base + summits * (0.4 + 0.6 * base)) * window
      h[j * n + i] = v
      max = Math.max(max, v)
    }
  }
  for (let k = 0; k < h.length; k += 1) h[k] /= max
  return h
}

// Marching squares → closed loops (Float32Array of x,y in [-1, 1]).
const CASES = [
  [], [[3, 2]], [[2, 1]], [[3, 1]], [[0, 1]], [[3, 0], [2, 1]], [[0, 2]], [[3, 0]],
  [[3, 0]], [[0, 2]], [[0, 1], [3, 2]], [[0, 1]], [[3, 1]], [[2, 1]], [[3, 2]], [],
] // edges: 0 top, 1 right, 2 bottom, 3 left
function contourLoops(h, level) {
  const n = GRID + 1
  const vOffset = n * n
  const px = new Map()
  const adj = new Map()
  const edgeId = (i, j, e) => (e === 0 ? j * n + i : e === 2 ? (j + 1) * n + i : e === 3 ? vOffset + j * n + i : vOffset + j * n + i + 1)
  const edgePoint = (i, j, e) => {
    let x0 = i; let y0 = j; let x1 = i + 1; let y1 = j
    if (e === 1) { x0 = i + 1; x1 = i + 1; y1 = j + 1 }
    if (e === 2) { y0 = j + 1; y1 = j + 1 }
    if (e === 3) { x1 = i; y1 = j + 1 }
    const a = h[y0 * n + x0]; const b = h[y1 * n + x1]
    const t = (level - a) / (b - a)
    return [((x0 + (x1 - x0) * t) / GRID) * 2 - 1, ((y0 + (y1 - y0) * t) / GRID) * 2 - 1]
  }
  const link = (a, b) => {
    if (!adj.has(a)) adj.set(a, [])
    if (!adj.has(b)) adj.set(b, [])
    adj.get(a).push(b)
    adj.get(b).push(a)
  }
  for (let j = 0; j < GRID; j += 1) {
    for (let i = 0; i < GRID; i += 1) {
      const idx = (h[j * n + i] > level ? 8 : 0) | (h[j * n + i + 1] > level ? 4 : 0)
        | (h[(j + 1) * n + i + 1] > level ? 2 : 0) | (h[(j + 1) * n + i] > level ? 1 : 0)
      for (const [ea, eb] of CASES[idx]) {
        const ida = edgeId(i, j, ea); const idb = edgeId(i, j, eb)
        if (!px.has(ida)) px.set(ida, edgePoint(i, j, ea))
        if (!px.has(idb)) px.set(idb, edgePoint(i, j, eb))
        link(ida, idb)
      }
    }
  }
  const seen = new Set()
  const loops = []
  for (const start of adj.keys()) {
    if (seen.has(start)) continue
    const pts = []
    let prev = -1; let cur = start
    while (cur !== undefined && !seen.has(cur)) {
      seen.add(cur)
      pts.push(...px.get(cur))
      const nb = adj.get(cur)
      const next = nb[0] !== prev ? nb[0] : nb[1]
      prev = cur
      cur = next
    }
    if (pts.length >= 24) loops.push(new Float32Array(pts))
  }
  return loops
}

const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2) // power1.inOut

export default function ContourLoader({ className = '' }) {
  const hostRef = useRef(null)
  const canvasRef = useRef(null)

  useEffect(() => {
    const host = hostRef.current
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const reduced = prefersReducedMotion()
    const levelCount = isLowEndDevice() ? LEVELS / 2 : LEVELS // low-end: 50% density
    const field = buildField()
    const levels = []
    for (let k = 0; k < levelCount; k += 1) {
      const v = (k + 0.5) / levelCount
      levels.push({ v, loops: contourLoops(field, v) })
    }
    const colors = {
      top: token('--bg-surface-alt'),
      wall: token('--sculpture-shadow'),
      line: token('--text-tertiary'),
      ink: token('--text-primary'),
      accent: token('--accent-processing'),
    }

    let W = 0; let H = 0; let scale = 1
    const resize = () => {
      const { width, height } = host.getBoundingClientRect()
      if (!width || !height) return
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      scale = Math.min(dpr, MAX_CANVAS / width, MAX_CANVAS / height)
      W = Math.round(width * scale); H = Math.round(height * scale)
      canvas.width = W; canvas.height = H
    }
    const ro = new ResizeObserver(resize)
    ro.observe(host)
    resize()

    let yaw = 0.6
    const project = (loop, lift, cosY, sinY, Sx, Sy, cx, cy, out) => {
      for (let p = 0; p < loop.length; p += 2) {
        const x = loop[p]; const y = loop[p + 1]
        out[p] = cx + (x * cosY - y * sinY) * Sx
        out[p + 1] = cy + (x * sinY + y * cosY) * Sy * TILT - lift
      }
      return out
    }
    const buffer = new Float32Array((GRID + 1) * (GRID + 1) * 4)
    const tracePath = (pts, count) => {
      ctx.beginPath()
      ctx.moveTo(pts[0], pts[1])
      for (let p = 2; p < count; p += 2) ctx.lineTo(pts[p], pts[p + 1])
    }

    const draw = (progress, alpha) => {
      ctx.clearRect(0, 0, W, H)
      if (!W) return
      const Sx = W * CONTOUR_SETTINGS.width
      const Sy = H * CONTOUR_SETTINGS.height
      const relief = H * RELIEF
      const step = relief / levelCount
      const cx = W / 2
      const cy = H * CONTOUR_SETTINGS.centerY
      const cosY = Math.cos(yaw); const sinY = Math.sin(yaw)
      const reached = progress * levelCount // fractional level index currently being drawn
      ctx.globalAlpha = alpha
      ctx.lineJoin = 'round'
      for (let k = 0; k < levelCount; k += 1) {
        const local = reached - k
        if (local <= 0) break
        const f = Math.min(1, local) // drawing progress of this level
        const lift = levels[k].v * relief
        const isFront = local < 1
        for (const loop of levels[k].loops) {
          // side wall (one terrace step tall) then the top face: stacked-paper relief
          const pts = project(loop, lift, cosY, sinY, Sx, Sy, cx, cy, buffer)
          ctx.save()
          ctx.globalAlpha = alpha * f
          ctx.translate(0, step)
          tracePath(pts, loop.length); ctx.closePath()
          ctx.fillStyle = colors.wall
          ctx.globalAlpha = alpha * f * (0.55 + 0.45 * levels[k].v) // higher terraces cast deeper steps
          ctx.fill()
          ctx.restore()
          ctx.save()
          ctx.globalAlpha = alpha * f
          tracePath(pts, loop.length); ctx.closePath()
          ctx.fillStyle = colors.top
          ctx.fill()
          ctx.restore()
          // contour stroke, drawn progressively along the loop for the active level
          const count = isFront ? Math.max(2, Math.floor((loop.length / 2) * f) * 2) : loop.length
          tracePath(pts, count)
          if (!isFront) ctx.closePath()
          ctx.lineWidth = (isFront ? 1.6 : 1) * scale
          ctx.strokeStyle = isFront ? colors.ink : colors.line
          ctx.stroke()
          if (isFront && count < loop.length) {
            ctx.fillStyle = colors.accent
            ctx.fillRect(pts[count - 2] - 2 * scale, pts[count - 1] - 2 * scale, 4 * scale, 4 * scale)
          }
        }
      }
      ctx.globalAlpha = 1
    }

    let raf = 0; let last = performance.now(); let clock = 0
    const total = CYCLE + HOLD + FADE
    const tick = (now) => {
      raf = requestAnimationFrame(tick)
      const dt = Math.min((now - last) / 1000, 0.1)
      if (now - last < 30) return // ~30fps is plenty for a line drawing
      last = now
      if (reduced) { draw(1, 1); return }
      clock = (clock + dt) % total
      yaw += YAW_SPEED * dt
      const progress = easeInOut(Math.min(1, clock / CYCLE))
      const alpha = clock < CYCLE + HOLD ? 1 : 1 - (clock - CYCLE - HOLD) / FADE
      draw(progress, Math.max(0, alpha))
    }
    const start = () => {
      if (raf) return
      last = performance.now()
      raf = requestAnimationFrame(tick)
    }
    const stop = () => { cancelAnimationFrame(raf); raf = 0 }
    const onVisibility = () => (document.hidden ? stop() : start())
    document.addEventListener('visibilitychange', onVisibility)
    start()

    return () => {
      stop()
      ro.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return (
    <div ref={hostRef} className={`contour ${className}`}>
      <canvas ref={canvasRef} aria-hidden="true" />
    </div>
  )
}
