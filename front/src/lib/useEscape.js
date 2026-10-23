import { useEffect, useRef } from 'react'

// Esc closes the topmost open dialog or drawer, and only that one (the export preview sits on the
// export dialog; the history drawer can open from the profile drawer). Each open layer registers
// here while `active`; the last one registered gets the key.
const stack = []
let listening = false
const onKey = (e) => {
  if (e.key !== 'Escape' || !stack.length || e.defaultPrevented) return
  e.preventDefault()
  stack[stack.length - 1].current?.()
}

export function useEscape(onClose, active = true) {
  const ref = useRef(onClose)
  ref.current = onClose
  useEffect(() => {
    if (!active) return undefined
    stack.push(ref)
    if (!listening) { window.addEventListener('keydown', onKey); listening = true }
    return () => {
      const i = stack.lastIndexOf(ref)
      if (i >= 0) stack.splice(i, 1)
    }
  }, [active])
}
