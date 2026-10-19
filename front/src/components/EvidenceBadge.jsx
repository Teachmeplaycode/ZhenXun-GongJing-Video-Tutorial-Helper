import React, { useState } from 'react'

const TEXT = { original: '原片可回看', cache: '仅缓存证据', none: '无可回看证据' }

// Which kind of looking back this video offers, shown once above the chat so a time link never
// promises more than it does. For an upload whose original is kept, it can be deleted from here.
export default function EvidenceBadge({ source, upload = false, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const state = source?.state || 'cache'
  return (
    <div className="evidence-badge" data-state={state} title={source?.message || ''}>
      <span className="evidence-badge__dot" aria-hidden="true" />
      <span>{TEXT[state]}</span>
      {upload && state === 'original' && onDelete ? (
        confirming ? (
          <span className="evidence-badge__confirm">
            删除后只能看缓存画面
            <button type="button" onClick={() => { setConfirming(false); onDelete() }}>确认删除</button>
            <button type="button" onClick={() => setConfirming(false)}>取消</button>
          </span>
        ) : (
          <button type="button" className="evidence-badge__action" onClick={() => setConfirming(true)}>删除原视频</button>
        )
      ) : null}
    </div>
  )
}
