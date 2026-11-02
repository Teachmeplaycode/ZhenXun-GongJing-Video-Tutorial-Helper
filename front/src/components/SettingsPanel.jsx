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

function FieldRow({ field, value, formValue, secretInput, cleared, onField, onSecret, onClearSecret, disabled }) {
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
          {!disabled && (configured || cleared) ? (
            <button type="button" className="account-card__link" onClick={() => onClearSecret(field.name)}>
              {cleared ? '撤销清除' : '清除'}
            </button>
          ) : null}
        </div>
      ) : field.type === 'select' ? (
        <select id={`set-${field.name}`} value={formValue} onChange={(e) => onField(field.name, e.target.value)} disabled={disabled}>
          {field.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input id={`set-${field.name}`} type={field.type === 'number' ? 'number' : 'text'} value={formValue}
          onChange={(e) => onField(field.name, e.target.value)} disabled={disabled}
          autoComplete="off" spellCheck={false} />
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

  useEffect(() => { if (open) setTab(initialTab) }, [open, initialTab])

  const load = useCallback(async () => {
    try {
      const data = await getSettings()
      setGroups(data.groups || [])
      setValues(data.values || {})
      setReadonly(Boolean(data.readonly))
      const initial = {}
      for (const g of data.groups || []) for (const f of g.fields) if (f.type !== 'secret') initial[f.name] = (data.values || {})[f.name]?.value || ''
      setForm(initial)
      setSecrets({})
      setClearSecrets({})
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => { if (open) load() }, [open, load])

  // Closing the panel drops unsaved secret inputs (memory only, never localStorage).
  useEffect(() => {
    if (!open) { setSecrets({}); setClearSecrets({}); setSaved(false); setError('') }
  }, [open])

  const onField = (name, v) => { setForm((f) => ({ ...f, [name]: v })); setSaved(false) }
  const onSecret = (name, v) => { setSecrets((s) => ({ ...s, [name]: v })); setClearSecrets((c) => ({ ...c, [name]: false })); setSaved(false) }
  const onClearSecret = (name) => { setClearSecrets((c) => ({ ...c, [name]: !c[name] })); setSaved(false) }

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
      setValues(data.values || {})
      setSecrets({})
      setClearSecrets({})
      setSaved(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const disabled = readonly || busy
  const activeGroup = groups.find((g) => g.id === tab)

  return (
    <div ref={rootRef} className="history" data-open={open || undefined} aria-hidden={!open} inert={open ? undefined : ''}>
      <div className="history__backdrop" onClick={onClose} />
      <span className="history__layer history__layer--accent" aria-hidden="true" />
      <span className="history__layer history__layer--ink" aria-hidden="true" />
      <aside className="history__panel settings-panel" role="dialog" aria-label="设置">
        <header className="history__head">
          <span className="eyebrow"><IconSettings size={14} /> 设置</span>
          <button type="button" className="icon-btn history__close" aria-label="关闭" onClick={onClose}><IconClose /></button>
        </header>
        <nav className="settings-tabs">
          {TABS.map((t) => (
            <button key={t.id} type="button" className={`settings-tab${tab === t.id ? ' is-active' : ''}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="settings-body">
          {error ? <p className="field-error" role="alert">{error}</p> : null}
          {saved ? <p className="settings-saved">已保存。模型配置的改动会在下一次提问时生效，不会中断正在回答的问题。</p> : null}
          {readonly ? <p className="mono-sm muted settings-readonly">公开演示模式，设置只读。</p> : null}
          {tab === 'accounts' ? (
            <AccountsList focus={accountFocus} mine={publicDemo} />
          ) : activeGroup ? (
            <ul className="settings-fields">
              {activeGroup.fields.map((f) => (
                <FieldRow key={f.name} field={f} value={values[f.name]} formValue={form[f.name] ?? ''}
                  secretInput={secrets[f.name] || ''} cleared={Boolean(clearSecrets[f.name])}
                  onField={onField} onSecret={onSecret} onClearSecret={onClearSecret} disabled={disabled} />
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
    </div>
  )
}
