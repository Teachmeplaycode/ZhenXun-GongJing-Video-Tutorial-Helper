import React, { useState } from 'react'
import { createPortal } from 'react-dom'
import { enterAccessCode, signIn, signUp } from '../api/client'
import { IconClose } from './Icons'
import '../styles/members.css'

// The web demo's door: an access code before anything else, then optional accounts so the same
// history shows on any browser. `mode` is 'code' | 'login' | 'register'; `gate` means the page
// can't be used until it's done (no close button, no clicking outside).

const TITLE = { code: '输入访问码', login: '登录', register: '注册账号' }

export default function MemberDialog({ mode: initial = 'code', gate = false, onDone, onClose }) {
  const [mode, setMode] = useState(initial)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'code') await enterAccessCode(code.trim())
      else if (mode === 'login') await signIn(name.trim(), password)
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
    <div className="overlay member-overlay" onClick={(e) => !gate && e.target === e.currentTarget && onClose?.()}>
      <form className="member-dialog" role="dialog" aria-modal="true" aria-label={TITLE[mode]} onSubmit={submit}>
        <header className="member-dialog__head">
          <strong>{TITLE[mode]}</strong>
          {gate ? null : <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>}
        </header>
        {mode === 'code' ? (
          <>
            <p className="member-dialog__hint">帧寻网页版目前邀请使用。输入拿到的访问码即可开始，不用注册。</p>
            <label className="field">
              <span className="field__label">访问码</span>
              <input className="field__input" value={code} onChange={(e) => setCode(e.target.value)} autoFocus autoComplete="off" />
            </label>
          </>
        ) : (
          <>
            <p className="member-dialog__hint">
              {mode === 'register' ? '注册后，这个浏览器里导入过的视频会归到账号下，换电脑或手机登录也能看到。' : '登录后可以看到这个账号导入过的全部视频。'}
            </p>
            <label className="field">
              <span className="field__label">用户名</span>
              <input className="field__input" value={name} onChange={(e) => setName(e.target.value)} autoFocus autoComplete="username" />
            </label>
            <label className="field">
              <span className="field__label">密码{mode === 'register' ? '（至少 6 位）' : ''}</span>
              <input className="field__input" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
            </label>
          </>
        )}
        {error ? <p className="field-error" role="alert">{error}</p> : null}
        <div className="member-dialog__actions">
          <span className="member-dialog__switch">
            {mode === 'code' ? <button type="button" onClick={() => switchTo('login')}>已有账号？登录</button> : null}
            {mode === 'login' ? <button type="button" onClick={() => switchTo('register')}>没有账号？注册</button> : null}
            {mode === 'register' ? <button type="button" onClick={() => switchTo('login')}>已有账号？登录</button> : null}
            {mode !== 'code' && gate ? <button type="button" onClick={() => switchTo('code')}>用访问码进入</button> : null}
          </span>
          <button type="submit" className="btn btn--dark" disabled={busy || (mode === 'code' ? !code.trim() : !name.trim() || !password)}>
            {busy ? '请稍候…' : mode === 'code' ? '进入' : mode === 'login' ? '登录' : '注册'}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  )
}
