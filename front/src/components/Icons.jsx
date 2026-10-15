import React from 'react'

// Minimal stroke icons (no emoji per §13). 16px grid, currentColor.
const Icon = ({ children, size = 16, ...rest }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
    {children}
  </svg>
)

export const IconCheck = (p) => <Icon {...p}><path d="M3.5 8.5l3 3 6-7" /></Icon>
export const IconChevron = (p) => <Icon {...p}><path d="M6 4l4 4-4 4" /></Icon>
export const IconUpload = (p) => <Icon {...p}><path d="M8 11V3M4.5 6.5L8 3l3.5 3.5M3 13h10" /></Icon>
export const IconArrowRight = (p) => <Icon {...p}><path d="M3 8h10M9 4l4 4-4 4" /></Icon>
export const IconArrowLeft = (p) => <Icon {...p}><path d="M13 8H3M7 4L3 8l4 4" /></Icon>
export const IconSend = (p) => <Icon {...p}><path d="M8 13V3M4 7l4-4 4 4" /></Icon>
export const IconLock = (p) => <Icon {...p}><rect x="4" y="7" width="8" height="6" rx="1" /><path d="M5.5 7V5.5a2.5 2.5 0 015 0V7" /></Icon>
export const IconRefresh = (p) => <Icon {...p}><path d="M13 8a5 5 0 11-1.5-3.5M13 3v2.5h-2.5" /></Icon>
export const IconExpand = (p) => <Icon {...p}><path d="M9.5 3H13v3.5M6.5 13H3V9.5M13 3L9 7M3 13l4-4" /></Icon>
export const IconStop = (p) => <Icon {...p}><rect x="4.5" y="4.5" width="7" height="7" rx="1" /></Icon>
export const IconClose = (p) => <Icon {...p}><path d="M4 4l8 8M12 4l-8 8" /></Icon>
export const IconAlert = (p) => <Icon {...p}><path d="M8 3l5.5 10h-11z" /><path d="M8 7v2.5M8 11.3v.2" /></Icon>
export const IconFilm = (p) => <Icon {...p}><rect x="2.5" y="3" width="11" height="10" rx="1" /><path d="M5 3v10M11 3v10M2.5 6h2.5M2.5 10h2.5M11 6h2.5M11 10h2.5" /></Icon>
export const IconLink = (p) => <Icon {...p}><path d="M7 9a2.5 2.5 0 003.5 0l2-2a2.5 2.5 0 00-3.5-3.5l-.75.75M9 7a2.5 2.5 0 00-3.5 0l-2 2A2.5 2.5 0 007 12.5l.75-.75" /></Icon>
export const IconHistory = (p) => <Icon {...p}><path d="M2.5 8a5.5 5.5 0 101.6-3.9M2.5 2.5v2.5H5" /><path d="M8 5v3l2 1.5" /></Icon>
