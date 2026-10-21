import React from 'react'
import { BRAND } from '../config/workspace'

/**
 * 帧寻 over "GongJ!ng?" (dialect for "真的吗？"); side by side in the top bar. The trailing "?"
 * turns into "!" when `confirmed` (analysis done: "真的！"), and flickers to "!" for a frame
 * while the model glitches (CSS).
 */
export default function Wordmark({ confirmed = false, stacked = false, className = '' }) {
  return (
    <span className={`wordmark${stacked ? ' wordmark--stacked' : ''}${confirmed ? ' is-confirmed' : ''} ${className}`}
      aria-label={confirmed ? BRAND.confirmed : BRAND.name}>
      <span className="wordmark__cn" aria-hidden="true">帧寻</span>
      <span className="wordmark__en" aria-hidden="true">
        GongJ<span className="wordmark__mark">!</span>ng
        <span className="wordmark__end"><span className="wordmark__q">?</span><span className="wordmark__x">!</span></span>
      </span>
    </span>
  )
}
