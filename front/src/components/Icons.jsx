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
export const IconImage = (p) => <Icon {...p}><rect x="2.5" y="3" width="11" height="10" rx="1.5" /><circle cx="6" cy="6.5" r="1.1" /><path d="M2.5 11l3.2-3 2.6 2.4L10.5 8l3 3" /></Icon>
export const IconLink = (p) => <Icon {...p}><path d="M7 9a2.5 2.5 0 003.5 0l2-2a2.5 2.5 0 00-3.5-3.5l-.75.75M9 7a2.5 2.5 0 00-3.5 0l-2 2A2.5 2.5 0 007 12.5l.75-.75" /></Icon>
export const IconHistory = (p) => <Icon {...p}><path d="M2.5 8a5.5 5.5 0 101.6-3.9M2.5 2.5v2.5H5" /><path d="M8 5v3l2 1.5" /></Icon>
export const IconCopy = (p) => <Icon {...p}><rect x="5.5" y="5.5" width="7.5" height="7.5" rx="1" /><path d="M10.5 5.5V3.5a.8.8 0 00-.8-.8H3.5a.8.8 0 00-.8.8v6.2a.8.8 0 00.8.8h2" /></Icon>
export const IconPlus = (p) => <Icon {...p}><path d="M8 3v10M3 8h10" /></Icon>
export const IconGlobe = (p) => <Icon {...p}><circle cx="8" cy="8" r="5.5" /><path d="M2.5 8h11M8 2.5c1.6 1.6 2.4 3.5 2.4 5.5S9.6 11.9 8 13.5M8 2.5C6.4 4.1 5.6 6 5.6 8s.8 3.9 2.4 5.5" /></Icon>
export const IconBook = (p) => <Icon {...p}><path d="M3 3.5h4a1.5 1.5 0 011.5 1.5v8A1.5 1.5 0 007 11.5H3zM13 3.5H9.5A1.5 1.5 0 008 5v8a1.5 1.5 0 011.5-1.5H13z" /></Icon>
export const IconArrowDown = (p) => <Icon {...p}><path d="M8 3v10M4 9l4 4 4-4" /></Icon>
export const IconSlash = (p) => <Icon {...p}><path d="M10.5 2.5l-5 11" /></Icon>
export const IconTheme = (p) => <Icon {...p}><circle cx="8" cy="8" r="5.5" /><path d="M8 2.5a5.5 5.5 0 010 11z" fill="currentColor" /></Icon>
export const IconUser = (p) => <Icon {...p}><circle cx="8" cy="5.5" r="2.5" /><path d="M3 13.5a5 5 0 0110 0" /></Icon>
