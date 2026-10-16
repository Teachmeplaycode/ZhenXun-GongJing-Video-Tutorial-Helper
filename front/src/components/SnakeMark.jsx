import React from 'react'

/**
 * S1 snake mark. Each visual part stays separate so state motion can use
 * transforms only; no path morphing is required.
 */
export default function SnakeMark({ state = 'idle', framed = false, className = '' }) {
  return (
    <svg
      className={`snake-mark snake-mark--${state} ${framed ? 'is-framed' : ''} ${className}`}
      viewBox={framed ? '0 0 64 64' : '14 8 44 48'}
      aria-hidden="true"
      focusable="false"
    >
      {framed && (
        <path
          className="snake-mark__frame"
          d="M7 19V9a2 2 0 0 1 2-2h10 M45 7h10a2 2 0 0 1 2 2v10 M57 45v10a2 2 0 0 1-2 2H45 M19 57H9a2 2 0 0 1-2-2V45"
        />
      )}
      <path
        className="snake-mark__body"
        d="M38.5 12.5c8.7 0 14.5 4.7 14.5 11.2 0 5.8-4.9 9.3-11.5 10.7-5.3 1.1-8.6 3.5-8.6 7.2 0 4.6 4.9 7.6 10.4 9.2-8.4 3.3-17.5.4-21.4-5.7-5.2-8.2-1.1-17.7 8.8-21.4 3.2-1.2 5.3-2.6 5.3-5.6 0-3.6 2.7-6.1 6.5-6.1Z"
      />
      <path
        className="snake-mark__question"
        d="M25 24c0-7 5.2-11.5 13-11.5 7.5 0 12.5 4.2 12.5 10.5 0 5.2-3.1 8.2-8.3 10.6-4.6 2.1-6.1 4.2-6.1 8.4"
      />
      <ellipse className="snake-mark__eye" cx="37" cy="22.5" rx="3.8" ry="5.8" />
      <circle className="snake-mark__status" cx="46" cy="20" r="3.2" />
    </svg>
  )
}
