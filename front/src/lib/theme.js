import { useCallback, useEffect, useState } from 'react'
import { flushSync } from 'react-dom'
import { prefersReducedMotion } from './motion'

// Light / dark theme. The choice ('system' | 'light' | 'dark') is a per-browser convenience in
// localStorage; index.html applies it before first paint so the page never flashes the wrong theme.
// Switching by hand reveals the new theme through a circle that grows from the button (View
// Transitions: the old page is a snapshot, so the mask uncovers the real new page, sculpture included).
const KEY = 'gongjing.theme'
const CHOICES = ['system', 'light', 'dark']
export const THEME_LABEL = { system: '跟随系统', light: '浅色', dark: '深色' }
const REVEAL_MS = 800 // §12 medium
const REVEAL_EASE = 'cubic-bezier(0.45, 0, 0.55, 1)' // power2.inOut

const media = () => window.matchMedia?.('(prefers-color-scheme: dark)')

function stored() {
  try {
    const v = localStorage.getItem(KEY)
    return CHOICES.includes(v) ? v : 'system'
  } catch {
    return 'system'
  }
}

const resolve = (choice) => (choice === 'system' ? (media()?.matches ? 'dark' : 'light') : choice)

/** [resolved theme, choice, cycle to the next choice] */
export function useTheme() {
  const [choice, setChoice] = useState(stored)
  const [theme, setTheme] = useState(() => resolve(stored()))

  useEffect(() => {
    const apply = () => {
      const next = resolve(choice)
      document.documentElement.dataset.theme = next
      setTheme(next)
    }
    apply()
    const m = media()
    if (choice !== 'system' || !m) return undefined
    m.addEventListener('change', apply)
    return () => m.removeEventListener('change', apply)
  }, [choice])

  // origin: the element the switch came from; the mask grows from its centre.
  const cycle = useCallback((origin) => {
    const next = CHOICES[(CHOICES.indexOf(choice) + 1) % CHOICES.length]
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // private mode: the choice lasts for this page only
    }
    const target = resolve(next)
    const root = document.documentElement
    // Colour transitions (the frame's background eases over 1.2 s) would leave the new page half-way
    // between themes: pause them for the swap, and restore them once the new page is shown.
    const swap = (freezeTransitions = true) => {
      if (freezeTransitions) root.classList.add('theme-swapping')
      root.dataset.theme = target
      flushSync(() => {
        setChoice(next)
        setTheme(target)
      })
    }
    const settle = () => requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove('theme-swapping')))
    if (target === theme || !document.startViewTransition || prefersReducedMotion()) {
      // Without View Transitions, let the headline's CSS colour transition run.
      swap(prefersReducedMotion())
      settle()
      return
    }
    const r = origin?.getBoundingClientRect?.()
    const x = r ? r.left + r.width / 2 : window.innerWidth - 40
    const y = r ? r.top + r.height / 2 : 32
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
    const transition = document.startViewTransition(swap)
    transition.finished.finally(settle)
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: REVEAL_MS, easing: REVEAL_EASE, pseudoElement: '::view-transition-new(root)' },
      )
    }).catch(() => {})
  }, [choice, theme])

  return [theme, choice, cycle]
}
