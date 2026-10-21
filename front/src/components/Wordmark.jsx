import React from 'react'
import { BRAND } from '../config/workspace'

/**
 * "帧寻?" — searching the frames. The trailing "?" turns into "!" when `confirmed`
 * (analysis done: found), and flickers to "!" for a frame while the model glitches (CSS).
 */
export default function Wordmark({ confirmed = false, className = '' }) {
  return (
    <span className={`wordmark ${confirmed ? 'is-confirmed' : ''} ${className}`} aria-label={confirmed ? BRAND.confirmed : BRAND.name}>
      <span aria-hidden="true">
        帧寻
        <span className="wordmark__end"><span className="wordmark__q">?</span><span className="wordmark__x">!</span></span>
      </span>
    </span>
  )
}
