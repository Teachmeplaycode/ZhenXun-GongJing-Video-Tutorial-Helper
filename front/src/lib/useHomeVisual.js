import { useCallback, useEffect, useState } from 'react'

const KEY = 'gongjing.home-visual:v1'
const MOBILE_QUERY = '(max-width: 760px)'
const normalize = value => value === 'snake' ? 'snake' : '3d'

function readChoice() {
  try { return normalize(localStorage.getItem(KEY)) }
  catch { return '3d' }
}

// Mobile presentation is derived from the viewport; it never replaces the saved desktop choice.
export default function useHomeVisual() {
  const [choice, setChoice] = useState(readChoice)
  const [mobile, setMobile] = useState(() => window.matchMedia(MOBILE_QUERY).matches)
  useEffect(() => {
    const media = window.matchMedia(MOBILE_QUERY)
    const update = () => setMobile(media.matches)
    const syncStorage = event => {
      if (event.key === KEY || event.key === null) setChoice(readChoice())
    }
    media.addEventListener('change', update)
    window.addEventListener('storage', syncStorage)
    update()
    return () => {
      media.removeEventListener('change', update)
      window.removeEventListener('storage', syncStorage)
    }
  }, [])
  const select = useCallback(value => {
    const next = normalize(value)
    setChoice(next)
    try { localStorage.setItem(KEY, next) }
    catch { /* Storage may be disabled; this visit can still change the view. */ }
  }, [])
  return { choice, select, mobile, snakeOnly: mobile || choice === 'snake' }
}
