import React, { useEffect, useRef, useState } from 'react'
import { prefersReducedMotion } from '../lib/motion'

const TEXTURE = '/brand/mascot-full-body.png'
const BLEND_SECONDS = 0.2

/** The approved mascot, with live motion and a still image on the first paint. */
export default function HomepageMascot({ state = 'idle', active = true, placement = 'corner' }) {
  const hostRef = useRef(null)
  const canvasRef = useRef(null)
  const controlsRef = useRef(null)
  const stateRef = useRef(state)
  const activeRef = useRef(active)
  const [reduced, setReduced] = useState(prefersReducedMotion)
  const [renderer, setRenderer] = useState('loading')

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    activeRef.current = active
    controlsRef.current?.sync()
  }, [active])

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReduced(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    if (reduced) return undefined
    setRenderer('loading')
    const host = hostRef.current
    const canvas = canvasRef.current
    let disposed = false
    let rig = null
    let raf = 0
    let last = null
    let time = 0
    let visible = true
    let currentPose = null
    let failed = false
    let resizeObserver

    const stop = () => {
      cancelAnimationFrame(raf)
      raf = 0
      last = null
    }
    const canAnimate = () => !disposed && !failed && activeRef.current && visible && !document.hidden
    const frame = (now) => {
      raf = 0
      if (!canAnimate() || !rig) return
      const delta = last == null ? 0 : Math.min((now - last) / 1000, 0.05)
      last = now
      time += delta
      const target = rig.poseAt(time, stateRef.current)
      if (!currentPose) currentPose = { ...target }
      else {
        const blend = 1 - Math.exp(-delta / BLEND_SECONDS)
        for (const key of Object.keys(target)) {
          // Eye blinking is timed, while posture smoothly blends between states.
          currentPose[key] = key === 'eyeOpen' || key === 'pulse'
            ? target[key]
            : currentPose[key] + (target[key] - currentPose[key]) * blend
        }
      }
      rig.render(time, stateRef.current, currentPose)
      raf = requestAnimationFrame(frame)
    }
    const sync = () => {
      if (canAnimate() && rig) {
        if (!raf) raf = requestAnimationFrame(frame)
      } else stop()
    }
    const loseContext = (event) => {
      event.preventDefault()
      failed = true
      stop()
      setRenderer('static')
    }

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting
      sync()
    })
    observer.observe(host)
    canvas.addEventListener('webglcontextlost', loseContext)
    document.addEventListener('visibilitychange', sync)
    controlsRef.current = { sync }

    import('../lib/mascotRig').then(async ({ createMascot }) => {
      if (disposed) return
      const nextRig = await createMascot(canvas, { textureUrl: TEXTURE })
      if (disposed) { nextRig.dispose(); return }
      rig = nextRig
      const resize = () => {
        const size = Math.min(1024, Math.max(1, Math.round(host.clientWidth * Math.min(window.devicePixelRatio || 1, 1.5))))
        rig.renderer.setSize(size, size, false)
        rig.render(time, stateRef.current, currentPose)
      }
      resizeObserver = new ResizeObserver(resize)
      resizeObserver.observe(host)
      resize()
      setRenderer('live')
      sync()
    }).catch(() => {
      if (!disposed) {
        failed = true
        stop()
        setRenderer('static')
      }
    })

    return () => {
      disposed = true
      stop()
      controlsRef.current = null
      observer.disconnect()
      resizeObserver?.disconnect()
      document.removeEventListener('visibilitychange', sync)
      canvas.removeEventListener('webglcontextlost', loseContext)
      rig?.dispose()
    }
  }, [reduced])

  const live = !reduced && renderer === 'live'
  return (
    <figure className={`home-companion${placement === 'hero' ? ' home-companion--hero' : ''}`} data-exit={placement === 'hero' ? '' : undefined} data-state={state} data-renderer={live ? 'live' : 'static'}>
      <div ref={hostRef} className="home-companion__portrait" role="img" aria-label="GongJ!ng? 小蛇吉祥物">
        <img className="home-companion__still" src={TEXTURE} width="1254" height="1254" alt="" aria-hidden="true" decoding="async" />
        <canvas ref={canvasRef} className="home-companion__canvas" aria-hidden="true" />
      </div>
      <figcaption className="home-companion__caption"><i aria-hidden="true" />看见，再求证。</figcaption>
    </figure>
  )
}

