import { useCallback, useEffect, useState } from 'react'

// Light / dark theme. The choice ('system' | 'light' | 'dark') is a per-browser convenience in
// localStorage; index.html applies it before first paint so the page never flashes the wrong theme.
const KEY = 'gongjing.theme'
const CHOICES = ['system', 'light', 'dark']
export const THEME_LABEL = { system: '跟随系统', light: '浅色', dark: '深色' }

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

  const cycle = useCallback(() => {
    setChoice((c) => {
      const next = CHOICES[(CHOICES.indexOf(c) + 1) % CHOICES.length]
      try {
        localStorage.setItem(KEY, next)
      } catch {
        // private mode: the choice lasts for this page only
      }
      return next
    })
  }, [])

  return [theme, choice, cycle]
}
