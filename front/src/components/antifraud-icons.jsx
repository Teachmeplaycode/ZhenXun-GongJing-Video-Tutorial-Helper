import React from 'react'
const Icon = ({ children, size = 16 }) => <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
export const IconShield = (p) => <Icon {...p}><path d="M8 2l5 2v4c0 3-5 6-5 6S3 11 3 8V4z" /><path d="M5.5 8l1.5 1.5 3.5-4" /></Icon>
export const IconQrCode = (p) => <Icon {...p}><path d="M2 2h4v4H2zM10 2h4v4h-4zM2 10h4v4H2zM10 10h2v2h2v2h-4z" /></Icon>
export const IconPhone = (p) => <Icon {...p}><rect x="4" y="1.5" width="8" height="13" rx="1.5" /><path d="M7 12h2" /></Icon>
