import React, { useRef } from 'react'
import { useEscape } from '../lib/useEscape'
import { IconClose, IconHistory, IconLink } from './Icons'
import { useStaggeredDrawer } from './SessionList'

// The web demo's 我的: who is signed in, what today's allowance has left, and the ways out — the
// person's own platform logins, their history, signing out. A guest is offered an account that keeps
// what they imported (signing out a guest loses it).

const KINDS = [
  ['questions', '提问'],
  ['imports', '解析链接'],
  ['uploads', '上传文件'],
]

// Owners only: what the whole site has spent on model calls and transcription today, against the
// daily cap that pauses new imports and questions for everyone else (backend modules/spend.py).
function Spend({ spend }) {
  const capped = spend.limit > 0
  const kinds = [['llm', '模型'], ['asr', '语音识别']].filter(([k]) => spend.kinds?.[k])
  return (
    <section className="profile__section">
      <h3>网站今日花费 <span className="mono-sm muted">仅管理员可见</span></h3>
      <div className="profile__meter">
        <div className="profile__meter-head">
          <span>{kinds.map(([k, l]) => `${l} ¥${spend.kinds[k].yuan.toFixed(2)}`).join(' · ') || '还没有花费'}</span>
          <span className="mono-sm">¥{spend.yuan.toFixed(2)}{capped ? ` / ¥${spend.limit}` : ' · 不设上限'}</span>
        </div>
        {capped ? (
          <span className="profile__bar" aria-hidden="true"><span style={{ transform: `scaleX(${Math.min(1, spend.yuan / spend.limit)})` }} /></span>
        ) : null}
      </div>
      {capped && spend.yuan >= spend.limit ? <p className="caption">已到上限：其他人今天不能再导入和提问，你不受影响。</p> : null}
    </section>
  )
}

function Meter({ label, quota }) {
  if (!quota) return null
  const unlimited = quota.limit == null
  const left = unlimited ? null : Math.max(0, quota.limit - quota.used)
  return (
    <div className="profile__meter">
      <div className="profile__meter-head">
        <span>{label}</span>
        <span className="mono-sm">{unlimited ? `今天 ${quota.used} 次 · 不限` : `剩 ${left} / ${quota.limit}`}</span>
      </div>
      {unlimited ? null : (
        <span className="profile__bar" aria-hidden="true"><span style={{ transform: `scaleX(${Math.min(1, quota.used / quota.limit)})` }} /></span>
      )}
    </div>
  )
}

export default function ProfileDrawer({ open, user, onClose, onAccounts, onHistory, onRegister, onSignOut }) {
  useEscape(onClose, open)
  const rootRef = useRef(null)
  useStaggeredDrawer(rootRef, open)
  const guest = user?.plan === 'guest'
  return (
    <div ref={rootRef} className="history" data-open={open || undefined} aria-hidden={!open} inert={open ? undefined : ''}>
      <div className="history__backdrop" onClick={onClose} />
      <span className="history__layer history__layer--accent" aria-hidden="true" />
      <span className="history__layer history__layer--ink" aria-hidden="true" />
      <aside className="history__panel profile" role="dialog" aria-label="我的">
        <header className="history__head">
          <span className="eyebrow">我的</span>
          <button type="button" className="icon-btn history__close" aria-label="关闭" onClick={onClose}><IconClose /></button>
        </header>
        {open && user ? (
          <div className="profile__body">
            <div className="profile__who">
              <span className="profile__avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span>
              <span className="profile__name">
                <strong>{user.name}</strong>
                <span className={`profile__plan profile__plan--${user.plan}`}>{user.label || user.plan}</span>
              </span>
            </div>
            <section className="profile__section">
              <h3>今天的额度 <span className="mono-sm muted">北京时间 0 点重置</span></h3>
              {KINDS.map(([kind, label]) => <Meter key={kind} label={label} quota={user[kind]} />)}
            </section>
            {user.spend ? <Spend spend={user.spend} /> : null}
            {guest ? (
              <section className="profile__section profile__guest">
                <p>游客记录只保存在这个浏览器里，退出或换设备就找不回了。注册一个账号，刚才导入的视频会一起保留。</p>
                <button type="button" className="btn btn--dark" onClick={onRegister}>注册账号，保留记录</button>
              </section>
            ) : null}
            <nav className="profile__links">
              <button type="button" className="profile__link" onClick={onAccounts}><IconLink size={14} /> 平台账号（B 站、腾讯元宝）</button>
              <button type="button" className="profile__link" onClick={onHistory}><IconHistory size={14} /> 历史会话</button>
            </nav>
            <button type="button" className="btn btn--ghost profile__out" onClick={onSignOut}>
              {guest ? '退出游客（记录会丢失）' : '退出登录'}
            </button>
          </div>
        ) : null}
      </aside>
    </div>
  )
}
