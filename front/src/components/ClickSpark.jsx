import React, { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../lib/motion'
import { token } from '../lib/tokens'

const SPARK_COUNT = 8
const DURATION = 420
const RADIUS = 18
const LENGTH = 9

// Restrained global click feedback inspired by Vue Bits' Click Spark. Canvas keeps
// the effect independent from button layout and makes repeated clicks inexpensive.
export default function ClickSpark() {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (prefersReducedMotion()) return undefined
    const canvas = canvasRef.current
    const context = canvas.getContext('2d')
    const sparks = []
    let raf = 0
    let dpr = 1

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(window.innerWidth * dpr)
      canvas.height = Math.round(window.innerHeight * dpr)
      canvas.style.width = `${window.innerWidth}px`
      canvas.style.height = `${window.innerHeight}px`
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const draw = () => {
      const now = performance.now()
      context.clearRect(0, 0, window.innerWidth, window.innerHeight)
      context.lineCap = 'round'
      context.lineWidth = 1.75
      for (let s = sparks.length - 1; s >= 0; s -= 1) {
        const spark = sparks[s]
        if (spark.last == null) spark.last = now
        else {
          // Clamp long frames so background-tab throttling cannot skip the effect.
          spark.elapsed += Math.min(34, Math.max(0, now - spark.last))
          spark.last = now
        }
        const t = Math.min(1, spark.elapsed / DURATION)
        const eased = 1 - (1 - t) ** 3
        context.strokeStyle = spark.color
        context.globalAlpha = 1 - t
        for (let i = 0; i < SPARK_COUNT; i += 1) {
          const angle = i / SPARK_COUNT * Math.PI * 2
          const inner = 3 + eased * RADIUS
          const outer = inner + LENGTH * (1 - t)
          context.beginPath()
          context.moveTo(spark.x + Math.cos(angle) * inner, spark.y + Math.sin(angle) * inner)
          context.lineTo(spark.x + Math.cos(angle) * outer, spark.y + Math.sin(angle) * outer)
          context.stroke()
        }
        if (t >= 1) sparks.splice(s, 1)
      }
      context.globalAlpha = 1
      if (sparks.length) raf = requestAnimationFrame(draw)
      else raf = 0
    }

    const onClick = (event) => {
      if (event.button !== 0) return
      sparks.push({ x: event.clientX, y: event.clientY, elapsed: 0, last: null, color: token('--accent-active') })
      if (!raf) raf = requestAnimationFrame(draw)
    }

    resize()
    window.addEventListener('resize', resize)
    // Capture keeps feedback reliable even when canvas/card interactions stop bubbling.
    window.addEventListener('click', onClick, { capture: true, passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('click', onClick, true)
    }
  }, [])

  return <canvas ref={canvasRef} className="click-spark" aria-hidden="true" />
}
