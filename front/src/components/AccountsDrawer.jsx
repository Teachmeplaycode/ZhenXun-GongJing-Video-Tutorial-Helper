import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useEscape } from '../lib/useEscape'
import { cancelLogin, listAccounts, logoutAccount, pasteCookie, pollLogin, startLogin } from '../api/client'
import { IconClose, IconRefresh } from './Icons'
import { useStaggeredDrawer } from './SessionList'

// Platform logins: scan a QR code with the platform's app and the backend keeps the cookie.
// Cookie values never reach the page; it only sees whether one is set, whose it is and when it expires.

const POLL_MS = 2000
const SOURCE = { ui: '扫码登录', env: 'backend/.env', environment: '环境变量' }
const MINE = { ui: '你的扫码绑定' } // the web demo: each person's own login
const day = (seconds) => new Date(seconds * 1000).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })

function statusOf(a) {
  if (!a.configured) return { tone: 'off', text: '未登录' }
  if (a.valid === false) return { tone: 'warn', text: '已失效，请重新登录' }
  const who = a.user ? ` · ${a.user}` : ''
  return { tone: 'ok', text: `已登录${who}` }
}

// On a phone the QR is on the very screen that would scan it: B 站 can open its own confirmation page
// in the B 站 App instead; for WeChat (元宝) the way is to save the QR and pick it in 扫一扫's album.
const onPhone = () => typeof window !== 'undefined' && Boolean(window.matchMedia?.('(hover: none) and (max-width: 900px)').matches)

function QrLogin({ account, onDone, mine = false }) {
  const [login, setLogin] = useState(null)
  const [error, setError] = useState('')
  const [left, setLeft] = useState(0)
  const live = useRef(null)

  const begin = useCallback(async () => {
    setError('')
    setLogin(null)
    if (live.current) cancelLogin(live.current)
    try {
      const l = await startLogin(account.id)
      live.current = l.id
      setLogin(l)
      setLeft(l.expires_in)
    } catch (err) {
      setError(err.message)
    }
  }, [account.id])

  useEffect(() => {
    begin()
    return () => { if (live.current) cancelLogin(live.current) }
  }, [begin])

  const id = login?.id
  const state = login?.state
  useEffect(() => {
    if (!id || state === 'done' || state === 'expired' || state === 'error') return undefined
    const t = setInterval(async () => {
      try {
        const next = await pollLogin(id)
        setLogin((cur) => (cur && cur.id === id ? { ...cur, ...next } : cur))
        setLeft(next.expires_in)
        if (next.state === 'done') {
          live.current = null
          onDone(next.account)
        }
      } catch (err) {
        setLogin((cur) => (cur ? { ...cur, state: 'error', message: err.message } : cur))
      }
    }, POLL_MS)
    return () => clearInterval(t)
  }, [id, state, onDone])

  if (error) {
    return (
      <div className="qr-login">
        <p className="field-error" role="alert">{error}</p>
        <button type="button" className="btn btn--ghost" onClick={begin}><IconRefresh size={14} /> 重试</button>
      </div>
    )
  }
  if (!login) {
    return (
      <div className="qr-login">
        <div className="qr-login__code is-loading" aria-hidden="true" />
        <p className="mono-sm muted">{{ yuanbao: '正在打开腾讯元宝的登录页（约 15 秒）…', xiaohongshu: '正在打开小红书的登录页（约 30 秒）…' }[account.id] || '正在获取二维码…'}</p>
      </div>
    )
  }
  const over = state === 'expired' || state === 'error'
  return (
    <div className="qr-login" data-state={state}>
      <div className="qr-login__code">
        <img src={login.qr} alt={`${account.label}登录二维码`} />
        {over || state === 'scanned' ? <span className="qr-login__veil">{state === 'scanned' ? '已扫码' : '已过期'}</span> : null}
      </div>
      <div className="qr-login__side">
        <p className="qr-login__hint">
          {state === 'waiting' ? `用 ${account.app} 扫码登录` : login.message}
        </p>
        {!over && state !== 'done' ? <p className="mono-sm muted">{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')} 后过期</p> : null}
        {over ? <button type="button" className="btn btn--ghost" onClick={begin}><IconRefresh size={14} /> 换一个二维码</button> : null}
        {onPhone() && !over && state !== 'done' && account.id === 'bilibili' && login.link ? (
          <a className="btn btn--dark qr-login__app" href={`bilibili://browser?url=${encodeURIComponent(login.link)}`}>在 B 站 App 里确认</a>
        ) : null}
        {onPhone() && !over && state !== 'done' && account.id === 'yuanbao' ? (
          <p className="qr-login__phone">在这台手机上：长按二维码存到相册，打开微信「扫一扫」，点右上角的相册图标选中它，再确认登录。</p>
        ) : null}
        <p className="mono-sm muted">{mine ? '登录凭证加密保存在你的帧寻账号里，只用于你自己导入的视频。' : '只保存在本机的 backend/.env.accounts，不会显示或上传。'}</p>
      </div>
    </div>
  )
}

function Paste({ account, onDone }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      onDone(await pasteCookie(account.id, value))
      setValue('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  const example = { yuanbao: 'hy_user=…; hy_token=…', xiaohongshu: '在已登录的小红书网页按 F12 → 网络 → 任一请求的 Cookie 整行（含 a1=…; web_session=…）' }[account.id] || 'SESSDATA=…; bili_jct=…'
  return (
    <form className="paste-cookie" onSubmit={save}>
      <textarea value={value} onChange={(e) => setValue(e.target.value)} placeholder={example} rows={2} spellCheck={false} autoComplete="off" />
      {error ? <p className="field-error" role="alert">{error}</p> : null}
      <button type="submit" className="btn btn--ghost" disabled={busy || !value.trim()}>保存</button>
    </form>
  )
}

function AccountCard({ account, onChange, mine = false }) {
  const [mode, setMode] = useState(null) // null | 'qr' | 'paste'
  const [error, setError] = useState('')
  const status = statusOf(account)
  const done = useCallback((next) => {
    setMode(null)
    if (next) onChange(next)
  }, [onChange])
  const logout = async () => {
    try {
      onChange(await logoutAccount(account.id))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <li className="account-card">
      <div className="account-card__head">
        <span className="account-card__name">{account.label}</span>
        <span className={`viz-stamp viz-stamp--${status.tone}`}>{status.text}</span>
      </div>
      <p className="account-card__purpose">{account.purpose}</p>
      {account.configured ? (
        <p className="mono-sm muted">
          来自 {(mine && MINE[account.source]) || SOURCE[account.source] || account.source}
          {account.expires ? ` · ${day(account.expires)} 到期` : ''}
        </p>
      ) : null}
      {mode === 'qr' ? <QrLogin account={account} onDone={done} mine={mine} /> : null}
      {mode === 'paste' ? <Paste account={account} onDone={done} /> : null}
      {error ? <p className="field-error" role="alert">{error}</p> : null}
      <div className="account-card__actions">
        {account.qr === false ? null : mode === 'qr' ? (
          <button type="button" className="btn btn--ghost" onClick={() => setMode(null)}>取消</button>
        ) : (
          <button type="button" className="btn btn--dark account-card__go" onClick={() => setMode('qr')}>
            {account.configured ? (mine ? '重新扫码绑定' : '重新扫码登录') : (mine ? '扫码绑定' : '扫码登录')}
          </button>
        )}
        {mine ? null : (
          <button type="button" className="account-card__link" onClick={() => setMode(mode === 'paste' ? null : 'paste')}>
            {mode === 'paste' ? '收起' : '手动粘贴 Cookie'}
          </button>
        )}
        {account.configured && account.source === 'ui' ? (
          <button type="button" className="account-card__link" onClick={logout}>{mine ? '解除绑定' : '退出登录'}</button>
        ) : null}
      </div>
    </li>
  )
}

// `mine`: the web demo, where these are the signed-in person's own logins (scan only, kept encrypted,
// used only for their own imports).
export default function AccountsDrawer({ open, focus = null, onClose, mine = false }) {
  useEscape(onClose, open)
  const rootRef = useRef(null)
  const [accounts, setAccounts] = useState([])
  const [error, setError] = useState('')
  useStaggeredDrawer(rootRef, open)

  useEffect(() => {
    if (!open) return
    listAccounts().then((list) => { setAccounts(list); setError('') }).catch((err) => setError(err.message))
  }, [open])

  const replace = useCallback((next) => setAccounts((list) => list.map((a) => (a.id === next.id ? next : a))), [])
  const ordered = focus ? [...accounts].sort((a, b) => (b.id === focus) - (a.id === focus)) : accounts

  return (
    <div ref={rootRef} className="history" data-open={open || undefined} aria-hidden={!open} inert={open ? undefined : ''}>
      <div className="history__backdrop" onClick={onClose} />
      <span className="history__layer history__layer--accent" aria-hidden="true" />
      <span className="history__layer history__layer--ink" aria-hidden="true" />
      <aside className="history__panel" role="dialog" aria-label="平台账号">
        <header className="history__head">
          <span className="eyebrow">平台账号</span>
          <button type="button" className="icon-btn history__close" aria-label="关闭" onClick={onClose}><IconClose /></button>
        </header>
        {mine ? (
          <p className="history__empty account-list__note">
            绑定你自己的平台账号后，解析时会用你的登录（比如 B 站可以看 1080P 和需要登录的视频）。登录凭证加密保存，只用于你自己导入的视频，随时可以解除绑定。
          </p>
        ) : null}
        {error ? <p className="history__empty">{error}</p> : null}
        <ul className="account-list">
          {open ? ordered.map((a) => <AccountCard key={a.id} account={a} onChange={replace} mine={mine} />) : null}
        </ul>
      </aside>
    </div>
  )
}
