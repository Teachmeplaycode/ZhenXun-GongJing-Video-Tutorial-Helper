import React, { useState } from 'react'
import { createPortal } from 'react-dom'
import { oauthUrl, signIn, signUp } from '../api/client'
import { IconClose } from './Icons'
import '../styles/members.css'

// The web demo's sign-in: a name and password, or GitHub / Google when the server has them set up
// (`oauth`). `mode` is 'login' | 'register'; `reason` says why it opened (e.g. importing needs an account).

const TITLE = { login: '登录', register: '注册账号' }
const PROVIDER = { github: 'GitHub', google: 'Google' }

export default function MemberDialog({ mode: initial = 'login', reason = '', oauth = [], onDone, onClose }) {
  const [mode, setMode] = useState(initial)
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'login') await signIn(name.trim(), password)
      else await signUp(name.trim(), password)
      onDone(mode)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const switchTo = (next) => { setMode(next); setError('') }

  return createPortal(
    <div className="overlay member-overlay" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <form className="member-dialog" role="dialog" aria-modal="true" aria-label={TITLE[mode]} onSubmit={submit}>
        <header className="member-dialog__head">
          <strong>{TITLE[mode]}</strong>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>
        </header>
        <p className="member-dialog__hint">
          {reason || (mode === 'register' ? '注册后每天可免费导入和提问；换电脑或手机登录，历史都在。' : '登录后可以看到这个账号导入过的全部视频。')}
        </p>
        {oauth.length ? (
          <div className="member-dialog__oauth">
            {oauth.map((p) => <a key={p} className="btn btn--ghost member-dialog__provider" href={oauthUrl(p)}>用 {PROVIDER[p] || p} 登录</a>)}
            <span className="member-dialog__or">或用用户名{mode === 'register' ? '注册' : '登录'}</span>
          </div>
        ) : null}
        <label className="field">
          <span className="field__label">用户名</span>
          <input className="field__input" value={name} onChange={(e) => setName(e.target.value)} autoFocus autoComplete="username" />
        </label>
        <label className="field">
          <span className="field__label">密码{mode === 'register' ? '（至少 6 位）' : ''}</span>
          <input className="field__input" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
        </label>
        {error ? <p className="field-error" role="alert">{error}</p> : null}
        <div className="member-dialog__actions">
          <span className="member-dialog__switch">
            {mode === 'login'
              ? <button type="button" onClick={() => switchTo('register')}>没有账号？注册</button>
              : <button type="button" onClick={() => switchTo('login')}>已有账号？登录</button>}
          </span>
          <button type="submit" className="btn btn--dark" disabled={busy || !name.trim() || !password}>
            {busy ? '请稍候…' : mode === 'login' ? '登录' : '注册'}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  )
}
