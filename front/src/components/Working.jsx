import React, { useEffect, useState } from 'react'

// A job the person is waiting on, said plainly where its result will appear: a moving bar, what is
// being done, the seconds so far and how long it usually takes. Used by the workbench tabs.
export default function Working({ label, hint = '' }) {
  const [started] = useState(() => Date.now())
  const [now, setNow] = useState(started)
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const seconds = Math.round((now - started) / 1000)
  return (
    <div className="working" role="status" aria-live="polite">
      <div className="working__head">
        <span className="working__dot" aria-hidden="true" />
        <strong>{label}</strong>
        <span className="mono-sm muted">{seconds} 秒</span>
      </div>
      <div className="working__bar" aria-hidden="true"><span /></div>
      {hint ? <p className="caption muted">{hint}</p> : null}
    </div>
  )
}
