import React, { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../lib/motion'

// The homepage's sculpture — a figure-eight ribbon of thin frame-sheets — drawn flat on a 2D canvas
// for phones, where the contour terrain would be stretched out of shape. The eight stands upright
// to fit a tall screen; the sheets flow along it and the ribbon twists, so each sheet is drawn as
// wide as the twist shows it, with nearer ones larger and darker. One still frame with reduced motion.

const SHEETS = 150
const FLOW = 0.045   // laps of the eight per second
const TWIST = 0.35   // ribbon turns per second

function lemniscate(t) {
  const s = Math.sin(t)
  const d = 1 + s * s
  return { x: Math.cos(t) / d, y: (s * Math.cos(t)) / d }
}

export default function FlatSculpture({ className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return undefined
    const ctx = canvas.getContext('2d')
    const css = getComputedStyle(document.documentElement)
    const color = (name, fallback) => css.getPropertyValue(name).trim() || fallback
    const ink = color('--text-primary', '#1a1a1a')
    const paper = color('--bg-surface', '#ffffff')
    const accent = color('--accent-active', '#c8f04a')
    let frame = 0
    let width = 0
    let height = 0

    const size = () => {
      const rect = canvas.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = rect.width
      height = rect.height
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const draw = (seconds) => {
      ctx.clearRect(0, 0, width, height)
      const upright = height > width // a tall screen: the eight stands up
      const reach = upright ? Math.min(height * 0.34, width * 0.82) : Math.min(width * 0.4, height * 0.9)
      const breadth = reach * 0.32 // how far a sheet reaches across the ribbon
      const cx = width / 2
      const cy = height * (upright ? 0.55 : 0.5) // clear of the title above, the progress card below
      const sheets = []
      for (let i = 0; i < SHEETS; i += 1) {
        const t = (i / SHEETS) * Math.PI * 2 + seconds * FLOW * Math.PI * 2
        const p = lemniscate(t)
        const q = lemniscate(t + 0.002)
        let [x, y, dx, dy] = [p.x, p.y, q.x - p.x, q.y - p.y]
        if (upright) [x, y, dx, dy] = [y, x, dy, dx]
        const depth = Math.sin(t) * 0.5 + 0.5 // which lobe is nearer
        const twist = Math.cos(2 * t + seconds * TWIST * Math.PI * 2)
        sheets.push({ x: cx + x * reach * 1.1, y: cy + y * reach * 1.1, angle: Math.atan2(dy, dx), depth, twist, i })
      }
      sheets.sort((a, b) => a.depth - b.depth)
      for (const s of sheets) {
        const scale = 0.72 + s.depth * 0.42
        const across = breadth * scale * (0.25 + 0.75 * Math.abs(s.twist))
        const thick = Math.max(1.2, 3.4 * scale * (1 - Math.abs(s.twist) * 0.55))
        ctx.save()
        ctx.translate(s.x, s.y)
        ctx.rotate(s.angle + Math.PI / 2)
        ctx.globalAlpha = 0.45 + s.depth * 0.5
        ctx.fillStyle = paper
        ctx.strokeStyle = ink
        ctx.lineWidth = 0.7
        ctx.beginPath()
        ctx.rect(-across / 2, -thick / 2, across, thick)
        ctx.fill()
        ctx.stroke()
        if (s.i % 25 === 0) { // a few sheets lit, like frames being read
          ctx.fillStyle = accent
          ctx.globalAlpha = 0.9
          ctx.fillRect(-across / 2, -thick / 2, across, thick)
        }
        ctx.restore()
      }
    }

    size()
    const observer = new ResizeObserver(() => { size(); if (prefersReducedMotion()) draw(0) })
    observer.observe(canvas)
    if (prefersReducedMotion()) {
      draw(0)
    } else {
      const start = performance.now()
      const loop = (now) => { draw((now - start) / 1000); frame = requestAnimationFrame(loop) }
      frame = requestAnimationFrame(loop)
    }
    return () => { cancelAnimationFrame(frame); observer.disconnect() }
  }, [])
  return <canvas ref={ref} className={`flat-sculpture ${className}`} aria-hidden="true" />
}
