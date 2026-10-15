import React, { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { EASE } from '../lib/motion'

// §9.2 progress.update — inline step label + percent.
export default function ProgressPill({ step, percent }) {
  const ref = useRef(null)
  useLayoutEffect(() => {
    gsap.fromTo(ref.current, { opacity: 0, y: 4 }, { opacity: 1, y: 0, duration: 0.24, ease: EASE.enter })
  }, [step])
  return (
    <span ref={ref} className="progress-pill">
      <span className="progress-pill__dot" />
      {step}
      <span className="progress-pill__pct">{Math.round(percent)}%</span>
    </span>
  )
}
