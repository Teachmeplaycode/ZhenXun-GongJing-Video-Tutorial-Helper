import React from 'react'
import { BRAND } from '../config/workspace'

/**
 * "GongJ!ng?" — dialect for "真的吗？". The trailing "?" turns into "!" when `confirmed`
 * (analysis done: "真的！"), and flickers to "!" for a frame while the model glitches (CSS).
 */
export default function Wordmark({ confirmed = false, className = '' }) {
  return (
    <span className={`wordmark ${confirmed ? 'is-confirmed' : ''} ${className}`} aria-label={confirmed ? BRAND.confirmed : BRAND.name}>
      <span aria-hidden="true">
        GongJ<span className="wordmark__mark">!</span>ng
        <span className="wordmark__end"><span className="wordmark__q">?</span><span className="wordmark__x">!</span></span>
      </span>
    </span>
  )
}
