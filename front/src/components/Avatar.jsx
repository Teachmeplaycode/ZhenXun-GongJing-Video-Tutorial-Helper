import React from 'react'
import SnakeMark from './SnakeMark'

// The Agent uses the same S1 snake as the product mark; repeated message avatars
// stay static so a long conversation does not become a field of blinking icons.
export default function Avatar({ role, src, animated = false }) {
  return (
    <div className={`avatar avatar--${role}`} aria-label={role === 'user' ? '用户' : 'GongJ!ng Agent'}>
      {role === 'assistant'
        ? <SnakeMark className="avatar__snake" state={animated ? 'chat' : 'static'} />
        : src ? <img src={src} alt="" /> : null}
    </div>
  )
}
