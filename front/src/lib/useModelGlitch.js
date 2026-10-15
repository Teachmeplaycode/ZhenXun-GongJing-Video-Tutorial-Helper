import { useEffect, useState } from 'react'
import { SCULPTURE_SETTINGS } from '../config/workspace'

const SETTINGS = SCULPTURE_SETTINGS.glitch

// Frame looks, in the spirit of PV signal interruptions: hard cuts, no easing in between.
// warp: wave distortion (fraction of width) · slice: share of torn bands · tear: max band shift ·
// rgb: channel split in px · blocks: share of displaced data strips · scan: interlace strength
const LOOKS = {
  clean: { warp: 0, slice: 0, tear: 0, rgb: 0, blocks: 0, scan: 0 },
  jitter: { warp: 0.003, slice: 0.35, tear: 0.02, rgb: 3, blocks: 0, scan: 0.6 },
  warp: { warp: 0.012, slice: 0.15, tear: 0.015, rgb: 4, blocks: 0, scan: 0.5 },
  slice: { warp: 0.005, slice: 1, tear: 0.06, rgb: 6, blocks: 0.2, scan: 1 },
  tear: { warp: 0.008, slice: 1, tear: 0.1, rgb: 8, blocks: 0.4, scan: 1 },
}

// Each burst is a stutter of short frames [look, ms]; clean gaps between hits sell the rhythm.
const BURSTS = [
  [['jitter', 50], ['clean', 40], ['warp', 90], ['slice', 50], ['clean', 50], ['jitter', 40]],
  [['tear', 60], ['warp', 110], ['slice', 40], ['clean', 60], ['jitter', 50]],
  [['warp', 70], ['clean', 40], ['slice', 50], ['tear', 50], ['clean', 50], ['warp', 60]],
]

/**
 * Occasional signal interruption (distortion only) on the homepage model.
 * Returns the current glitch frame ({ look, seed, ...params }) or null when the picture is clean.
 * Inactive scenes, hidden tabs and reduced motion stop the timer.
 */
export function useModelGlitch(enabled) {
  const [frame, setFrame] = useState(null)

  useEffect(() => {
    if (!enabled || !SETTINGS.enabled) return undefined
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    let timer
    const allowed = () => !document.hidden && !reduced.matches
    const cancel = () => {
      clearTimeout(timer)
      setFrame(null)
    }
    const schedule = (delay) => {
      timer = setTimeout(burst, delay * 1000)
    }
    const burst = () => {
      if (!allowed()) return
      const steps = BURSTS[Math.floor(Math.random() * BURSTS.length)]
      let i = 0
      const step = () => {
        if (i >= steps.length) {
          setFrame(null)
          schedule(SETTINGS.minInterval + Math.random() * (SETTINGS.maxInterval - SETTINGS.minInterval))
          return
        }
        const [look, ms] = steps[i]
        i += 1
        setFrame(look === 'clean' ? null : { look, seed: Math.random() * 100, ...LOOKS[look] })
        timer = setTimeout(step, ms * SETTINGS.tempo)
      }
      step()
    }
    const sync = () => {
      cancel()
      if (allowed()) schedule(SETTINGS.firstDelay)
    }
    sync()
    document.addEventListener('visibilitychange', sync)
    reduced.addEventListener('change', sync)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', sync)
      reduced.removeEventListener('change', sync)
      setFrame(null)
    }
  }, [enabled])

  return enabled && SETTINGS.enabled ? frame : null
}
