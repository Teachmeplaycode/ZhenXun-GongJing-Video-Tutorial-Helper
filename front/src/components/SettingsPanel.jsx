import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useEscape } from '../lib/useEscape'
import { getSettings, saveSettings } from '../api/client'
import { AccountsList } from './AccountsDrawer'
import { IconClose, IconSettings } from './Icons'
import { useStaggeredDrawer } from './SessionList'

const SOURCE_LABEL = { local: '设置面板', environment: '环境变量', env: 'backend/.env', accounts: '扫码登录', overlay: '本次请求' }
const TABS = [
  { id: 'model', label: '模型与 API' },
  { id: 'accounts', label: '平台账号' },
  { id: 'runtime', label: '本地运行' },
]

function FieldRow({ field, value, formValue, secretInput, cleared, onField, onSecret, onClearSecret, disabled, provider }) {
  const isSecret = field.type === 'secret'
  const source = value?.source
  const overridden = value?.overridden_by_env
  const configured = isSecret ? (value?.configured && !cleared) : Boolean(formValue)
  return (
    <li className="settings-field">
      <div className="settings-field__head">
        <label className="settings-field__label" htmlFor={`set-${field.name}`}>{field.label}</label>
        <span className="settings-field__code">{field.name}</span>
      </div>
      {isSecret ? (
        <div className="settings-field__control">
          <input id={`set-${field.name}`} type="password" value={secretInput}
            onChange={(e) => onSecret(field.name, e.target.value)} disabled={disabled}
            placeholder={cleared ? '将清除' : configured ? '已配置（留空保留）' : '未配置'}
            autoComplete="off" spellCheck={false} />
          {!disabled && (value?.local_configured || source === 'local' || cleared) ? (
            <button type="button" className="account-card__link" onClick={() => onClearSecret(field.name)}>
              {cleared ? '撤销清除' : '清除本地值'}
            </button>
          ) : null}
        </div>
      ) : field.type === 'select' ? (
        <select id={`set-${field.name}`} value={formValue || field.default || field.options[0]?.value || ''} onChange={(e) => onField(field.name, e.target.value)} disabled={disabled}>
          {field.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input id={`set-${field.name}`} type={field.type === 'number' ? 'number' : 'text'} min={field.min} max={field.max} step={field.name === 'LLM_TEMPERATURE' ? 'any' : undefined} value={formValue}
          onChange={(e) => onField(field.name, e.target.value)} disabled={disabled}
          autoComplete="off" spellCheck={false} placeholder={field.name === 'LLM_BASE_URL' ? (provider === 'ollama' ? 'http://localhost:11434' : 'https://api.deepseek.com') : field.name === 'LLM_MODEL' ? (provider === 'ollama' ? 'qwen3.5:9b' : 'deepseek-flash') : undefined} />
      )}
      {field.hint ? <p className="mono-sm muted settings-field__hint">{field.hint}</p> : null}
      <p className="mono-sm muted settings-field__source">
        {configured ? `来自 ${SOURCE_LABEL[source] || source || '默认值'}` : cleared ? '将清除' : '未配置'}
        {overridden ? ' · 被环境变量覆盖，改这里不生效' : ''}
      </p>
    </li>
  )
}

export default function SettingsPanel({ open, initialTab = 'model', accountFocus = null, onClose, publicDemo = false }) {
  useEscape(onClose, open)
  const rootRef = useRef(null)
  useStaggeredDrawer(rootRef, open)
  return (
    <div ref={rootRef} className="history" data-open={open || undefined} aria-hidden={!open} inert={open ? undefined : ''}>
      <div className="history__backdrop" onClick={onClose} />
      <span className="history__layer history__layer--accent" aria-hidden="true" />
      <span className="history__layer history__layer--ink" aria-hidden="true" />
      {open ? <SettingsContent key={`${initialTab}-${accountFocus}`} initialTab={initialTab} accountFocus={accountFocus} onClose={onClose} publicDemo={publicDemo} /> : null}
    </div>
  )
}

function SettingsContent({ initialTab, accountFocus, onClose, publicDemo }) {
  const [tab, setTab] = useState(initialTab)
  const [groups, setGroups] = useState([])
  const [values, setValues] = useState({})
  const [readonly, setReadonly] = useState(false)
  const [form, setForm] = useState({})
  const [secrets, setSecrets] = useState({})
  const [clearSecrets, setClearSecrets] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  const alive = useRef(true)
  const dialog = useRef(null)
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    alive.current = true
    const previous = document.activeElement
    dialog.current?.querySelector('.history__close')?.focus()
    return () => { alive.current = false; previous?.focus?.() }
  }, [])
  const apply = useCallback((data) => {
    if (data.groups) setGroups(data.groups)
    setValues(data.values || {})
    const initial = {}
    for (const [name, meta] of Object.entries(data.values || {})) if ('value' in meta) initial[name] = meta.value ?? ''
    setForm(initial)
    setSecrets({}); setClearSecrets({})
  }, [])

  useEffect(() => {
    const abort = new AbortController()
    setLoading(true); setError('')
    getSettings(abort.signal).then((data) => {
      if (abort.signal.aborted) return
      apply(data); setReadonly(Boolean(data.readonly)); setLoading(false)
    }).catch((err) => {
      if (!abort.signal.aborted) { setError(err.message); setLoading(false) }
    })
    return () => abort.abort()
  }, [apply, retry])

  const onField = (name, v) => { setForm((f) => ({ ...f, [name]: v })); setSaved(false) }
  const onSecret = (name, v) => { setSecrets((s) => ({ ...s, [name]: v })); setClearSecrets((c) => ({ ...c, [name]: false })); setSaved(false) }
  const onClearSecret = (name) => { setSecrets((s) => ({ ...s, [name]: '' })); setClearSecrets((c) => ({ ...c, [name]: !c[name] })); setSaved(false) }

  const save = async () => {
    setBusy(true); setError(''); setSaved(false)
    try {
      const vals = {}
      for (const g of groups) for (const f of g.fields) {
        if (f.type === 'secret') {
          if (secrets[f.name]) vals[f.name] = secrets[f.name]
        } else {
          const orig = values[f.name]?.value || ''
          if ((form[f.name] ?? '') !== orig) vals[f.name] = form[f.name] ?? ''
        }
      }
      const clear = []
      for (const g of groups) for (const f of g.fields) if (f.type === 'secret' && clearSecrets[f.name]) clear.push(f.name)
      const data = await saveSettings(vals, clear)
      if (!alive.current) return
      apply(data)
      setSaved(true)
    } catch (err) {
      if (alive.current) setError(err.message)
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  const disabled = readonly || busy || loading
  const activeGroup = groups.find((g) => g.id === tab)

  return (
      <aside ref={dialog} className="history__panel settings-panel" role="dialog" aria-modal="true" aria-label="设置" onKeyDown={(e) => {
        if (e.key !== 'Tab') return
        const controls = [...dialog.current.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')].filter((el) => el.getClientRects().length)
        const first = controls[0], last = controls.at(-1)
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
      }}>
        <header className="history__head">
          <span className="eyebrow"><IconSettings size={14} /> 设置</span>
          <button type="button" className="icon-btn history__close" aria-label="关闭" onClick={onClose}><IconClose /></button>
        </header>
        <nav className="settings-tabs" role="tablist" aria-label="设置分类" onKeyDown={(e) => {
          const delta = { ArrowRight: 1, ArrowLeft: -1 }[e.key]
          if (!delta && !['Home', 'End'].includes(e.key)) return
          e.preventDefault()
          const index = e.key === 'Home' ? 0 : e.key === 'End' ? TABS.length - 1 : (TABS.findIndex((t) => t.id === tab) + delta + TABS.length) % TABS.length
          setTab(TABS[index].id)
          e.currentTarget.children[index].focus()
        }}>
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" id={`settings-tab-${t.id}`} aria-selected={tab === t.id} aria-controls="settings-content" tabIndex={tab === t.id ? 0 : -1} className={`settings-tab${tab === t.id ? ' is-active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="settings-body" role="tabpanel" id="settings-content" aria-labelledby={`settings-tab-${tab}`} aria-busy={loading}>
          {loading ? <p role="status">正在读取设置…</p> : null}
          {error && !groups.length ? <button type="button" onClick={() => setRetry((n) => n + 1)}>重试</button> : null}
          {error ? <p className="field-error" role="alert">{error}</p> : null}
          {saved ? <p className="settings-saved" role="status">已保存。模型配置的改动会在下一次提问时生效，不会中断正在回答的问题。</p> : null}
          {readonly ? <p className="mono-sm muted settings-readonly">模型由站点管理，本地启动后可以配置自己的 API</p> : null}
          {tab === 'accounts' ? (
            <>
              {publicDemo ? <p className="mono-sm muted">绑定你自己的平台账号后，登录凭证加密保存，只用于你自己导入的视频，随时可以解除绑定</p> : null}
              <AccountsList focus={accountFocus} mine={publicDemo} />
            </>
          ) : activeGroup ? (
            <ul className="settings-fields">
              {activeGroup.fields.map((f) => (
                <FieldRow key={f.name} field={f} value={values[f.name]} formValue={form[f.name] ?? ''}
                  secretInput={secrets[f.name] || ''} cleared={Boolean(clearSecrets[f.name])}
                  provider={form.LLM_PROVIDER} onField={onField} onSecret={onSecret} onClearSecret={onClearSecret} disabled={disabled} />
              ))}
            </ul>
          ) : null}
          {tab !== 'accounts' && activeGroup ? (
            <div className="settings-actions">
              <button type="button" className="btn btn--dark" onClick={save} disabled={disabled}>
                {busy ? '保存中…' : '保存'}
              </button>
            </div>
          ) : null}
        </div>
      </aside>
  )
}
