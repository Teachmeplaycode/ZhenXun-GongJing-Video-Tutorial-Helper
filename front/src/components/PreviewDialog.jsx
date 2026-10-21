import React from 'react'
import { createPortal } from 'react-dom'
import { IconClose } from './Icons'
import '../styles/export.css'

// What an export will look like, before it's downloaded: the page the backend renders, in a frame.
export default function PreviewDialog({ title, src, onClose, children }) {
  return createPortal(
    <div className="overlay preview-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="preview-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <header className="export-dialog__head">
          <strong>{title}</strong>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>
        </header>
        <iframe className="preview-dialog__frame" src={src} title={title} />
        {children ? <footer className="export-dialog__actions">{children}</footer> : null}
      </div>
    </div>,
    document.body,
  )
}
