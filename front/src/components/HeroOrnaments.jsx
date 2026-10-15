import React, { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { DUR, EASE, prefersReducedMotion } from '../lib/motion'

// Concave four-point star in a 24×24 box.
function Star({ className }) {
  return (
    <svg className={`ornament-star ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 0C12.9 8 16 11.1 24 12C16 12.9 12.9 16 12 24C11.1 16 8 12.9 0 12C8 11.1 11.1 8 12 0Z" />
    </svg>
  )
}

/**
 * Homepage line ornaments: a few hairlines, four-point stars and dot grids.
 * Sits behind the sculpture canvas so the model overlaps them. Positions live in workspace.css.
 */
export default function HeroOrnaments() {
  const rootRef = useRef(null)

  useLayoutEffect(() => {
    if (prefersReducedMotion()) return undefined
    const root = rootRef.current
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ delay: 0.3 })
      tl.from('.ornament-line--h', { scaleX: 0, duration: DUR.long, ease: EASE.move, stagger: 0.12 }, 0)
        .from('.ornament-line--v', { scaleY: 0, duration: DUR.long, ease: EASE.move }, 0.1)
        .from('.ornament-star:not(.ornament-star--twinkle)', { scale: 0, rotation: -90, opacity: 0, duration: DUR.medium, ease: EASE.enter, stagger: 0.1 }, 0.5)
        .from('.ornament-dots', { opacity: 0, duration: DUR.medium, ease: EASE.enter, stagger: 0.1 }, 0.6)
    }, root)
    return () => ctx.revert()
  }, [])

  return (
    <div ref={rootRef} className="ornaments" aria-hidden="true">
      <i className="ornament-line ornament-line--h ornament-line--top" />
      <Star className="ornament-star--top" />
      <i className="ornament-line ornament-line--v ornament-line--right" />
      <i className="ornament-dots ornament-dots--top" />
      <Star className="ornament-star--model ornament-star--twinkle" />
      <i className="ornament-line ornament-line--h ornament-line--base" />
      <Star className="ornament-star--base" />
      <i className="ornament-dots ornament-dots--bottom" />
    </div>
  )
}
