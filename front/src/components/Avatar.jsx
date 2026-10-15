import React from 'react'

// Rounded-rect avatar (§10). Image slot is reserved; solid block until assets land.
export default function Avatar({ role, src }) {
  return (
    <div className={`avatar avatar--${role}`} aria-label={role === 'user' ? '用户' : 'AI'}>
      {src ? <img src={src} alt="" /> : null}
    </div>
  )
}
