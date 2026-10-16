import React, { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../lib/motion'

const RANGE = 92
const MAX_SCALE = 1.15

// Vue Bits Dock behaviour, tuned down for a utility navigation rather than an
// app launcher: the nearest control lifts, and its neighbours answer softly.
export default function DockNav({ children, className = '' }) {
  const rootRef = useRef(null)

  useEffect(() => {
    if (prefersReducedMotion()) return undefined
    const root = rootRef.current
    let buttons = []
    let raf = 0

    const reset = () => {
      buttons.forEach((button) => {
        button.style.setProperty('--dock-scale', '1')
        button.style.setProperty('--dock-lift', '0px')
      })
    }
    const syncButtons = () => {
      buttons = [...root.querySelectorAll(':scope > .btn')]
      reset()
    }
    const update = (clientX) => {
      buttons.forEach((button) => {
        const rect = button.getBoundingClientRect()
        const distance = Math.abs(clientX - (rect.left + rect.width / 2))
        const influence = Math.max(0, 1 - distance / RANGE)
        button.style.setProperty('--dock-scale', String(1 + influence * (MAX_SCALE - 1)))
        button.style.setProperty('--dock-lift', `${-influence * 3}px`)
      })
    }
    const onMove = (event) => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => update(event.clientX))
    }

    root.addEventListener('pointermove', onMove)
    root.addEventListener('pointerleave', reset)
    const observer = new MutationObserver(syncButtons)
    observer.observe(root, { childList: true })
    syncButtons()
    return () => {
      cancelAnimationFrame(raf)
      observer.disconnect()
      root.removeEventListener('pointermove', onMove)
      root.removeEventListener('pointerleave', reset)
    }
  }, [])

  return <div ref={rootRef} className={`dock-nav ${className}`}>{children}</div>
}
