import React from 'react'
import { createPortal } from 'react-dom'
import { IconClose } from './Icons'
import '../styles/export.css'

// What an export will look like, before it's downloaded: the page the backend renders, in a frame —
// or, with `image`, the long picture of it (long-press to keep it on a phone).
export default function PreviewDialog({ title, src, image = false, onClose, children }) {
  const [state, setState] = React.useState(image ? 'loading' : 'ready')
  return createPortal(
    <div className="overlay preview-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="preview-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <header className="export-dialog__head">
          <strong>{title}</strong>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>
        </header>
        {image ? (
          <div className="preview-dialog__frame preview-dialog__frame--image">
            {state === 'loading' ? <p className="preview-dialog__wait muted">正在生成长图，长笔记要十几秒…</p> : null}
            {state === 'error' ? <p className="preview-dialog__wait">长图生成失败，请稍后再试。</p> : null}
            <img src={src} alt={title} hidden={state !== 'ready'} onLoad={() => setState('ready')} onError={() => setState('error')} />
          </div>
        ) : <iframe className="preview-dialog__frame" src={src} title={title} />}
        {image && state === 'ready' ? <p className="preview-dialog__tip muted">手机上长按图片「保存到相册」；电脑上点下面的按钮下载。</p> : null}
        {children ? <footer className="export-dialog__actions">{children}</footer> : null}
      </div>
    </div>,
    document.body,
  )
}
