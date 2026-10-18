import React from 'react'

const Icon = ({children, size = 16}) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor"
    strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
)
export const IconSearch = (p) => <Icon {...p}><circle cx="6.5" cy="6.5" r="4"/><path d="m9.5 9.5 4 4"/></Icon>
export const IconHelpCircle = (p) => <Icon {...p}><circle cx="8" cy="8" r="5.5"/><path d="M6.5 6a1.5 1.5 0 1 1 2 1.4L8 8.5M8 11v.1"/></Icon>
export const IconShield = (p) => <Icon {...p}><path d="m8 2 5 2v4c0 3-5 6-5 6s-5-3-5-6V4z"/><path d="m5.5 8 1.5 1.5 3.5-4"/></Icon>
