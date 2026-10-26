import React, { useEffect, useState } from 'react'
import { buildStepComments, buildSteps, getStepComments, getSteps, stepShotUrl } from '../../api/client'
import { fmtClock } from '../../lib/format'
import { IconFilm } from '../Icons'
import Working from '../Working'

// Step cards (backend modules/steps.py): for a tutorial what it has you do, for any other video how its
// content moves on (kind 'content'), in order, each at its second with the frame from that moment. A
// card's time jumps the timeline there; 「卡在这步」 (「问这一步」) starts a question about that step;
// 导入笔记 hands the cards to the notes tab as material for a note. 读评论区 matches the comments and danmaku to
// the steps (backend modules/stuck.py): a card then says how many viewers got stuck there and what fixed it.
const KIND = { stuck: '卡住', fix: '办法', version: '版本' }

function Viewers({ group, onSeek }) {
  return (
    <ul className="step-voices">
      {group.items.map((x) => (
        <li key={x.id} data-kind={x.kind}>
          <span className="step-voices__kind mono-sm">{KIND[x.kind]}</span>
          <span className="step-voices__body">
            <strong>{x.summary}</strong>
            <q>{x.text}</q>
            <span className="caption muted">
              {x.source === 'danmaku'
                ? <button type="button" className="link-btn" onClick={() => onSeek?.(x.time)}>弹幕 · {fmtClock(x.time)}</button>
                : `${x.source === 'reply' ? '回复' : '评论'} · ${x.author || '观众'}${x.likes ? ` · 赞 ${x.likes}` : ''}`}
            </span>
          </span>
        </li>
      ))}
    </ul>
  )
}
export default function StepsTab({ video, onSeek = null, onStuck = null, onBusy = null, onToNotes = null }) {
  const jobId = video?.jobId
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [voices, setVoices] = useState(null) // getStepComments() answer
  const [reading, setReading] = useState(false)
  const [open, setOpen] = useState(null) // the step whose viewers' words are unfolded

  useEffect(() => {
    if (!jobId) return undefined
    const ctrl = new AbortController()
    const fail = (err) => { if (err.name !== 'AbortError') setError(err.message) }
    getSteps(jobId, { signal: ctrl.signal }).then(setState).catch(fail)
    getStepComments(jobId, { signal: ctrl.signal }).then(setVoices).catch(() => {})
    return () => ctrl.abort()
  }, [jobId])

  const readComments = async () => {
    setReading(true)
    setError('')
    try {
      setVoices(await buildStepComments(jobId))
    } catch (err) {
      setError(err.message)
    } finally {
      setReading(false)
    }
  }
  const working = busy || state?.status === 'running' || reading
  useEffect(() => { onBusy?.(working) }, [working]) // eslint-disable-line react-hooks/exhaustive-deps
  const groups = voices?.status === 'done' ? voices.groups || [] : []
  const groupOf = (n) => groups.find((g) => g.step === n)
  const general = groupOf(0)

  const start = async () => {
    setBusy(true)
    setError('')
    try {
      setState(await buildSteps(jobId))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!jobId) return <p className="bench__note muted">导入视频后可以整理操作步骤。</p>
  const list = state?.status === 'done' ? state.steps || [] : []
  const content = state?.kind === 'content'
  const running = busy || state?.status === 'running'
  return (
    <div className="steps-tab">
      {list.length ? (
        <>
          <header className="steps-tab__head">
            <span className="eyebrow">{content ? '内容步骤' : '操作步骤'}</span>
            <span className="mono-sm muted">{list.length} 步 · 点时间回到那一秒</span>
            {onToNotes ? <button type="button" className="btn btn--ghost btn--sm steps-tab__to-notes" onClick={onToNotes} disabled={running}>导入笔记</button> : null}
          </header>
          {reading ? <div className="steps-tab__working"><Working label="正在读评论区和弹幕" hint="读热门评论和弹幕，对到每一步上，一般 20–40 秒。" /></div> : null}
          {busy ? <div className="steps-tab__working"><Working label="正在重新整理步骤" hint="读整段语音和画面文字，一直整理到视频结尾，长视频要一两分钟。" /></div> : null}
          {content ? null : <div className="steps-tab__voices">
            {voices?.status === 'done' || voices?.status === 'empty' || voices?.status === 'unavailable'
              ? <span className="caption muted">{voices.message}</span>
              : <span className="caption muted">看看评论区和弹幕里，别人卡在哪一步、怎么解决的。</span>}
            {voices?.status !== 'unavailable' ? (
              <button type="button" className="btn btn--ghost btn--sm" onClick={readComments} disabled={reading}>
                {reading ? '正在读评论区…' : voices?.status === 'done' || voices?.status === 'empty' ? '重新读' : '读评论区'}
              </button>
            ) : null}
          </div>}
          <ol className="steps-tab__list">
            {list.map((s) => (
              <li key={`${s.n}-${s.time}`} className="step-card">
                <button type="button" className="step-card__shot" onClick={() => onSeek?.(s.time)} aria-label={`回到 ${fmtClock(s.time)}`}>
                  {s.frame != null || s.shot ? <img src={stepShotUrl(jobId, s)} alt="" loading="lazy" /> : <span />}
                  <span className="step-card__no mono-sm">{String(s.n).padStart(2, '0')}</span>
                </button>
                <div className="step-card__body">
                  <strong>{s.action}</strong>
                  {s.detail ? <span className="caption muted">{s.detail}</span> : null}
                  <span className="step-card__actions">
                    <button type="button" className="step-card__time mono-sm" onClick={() => onSeek?.(s.time)}>{fmtClock(s.time)}</button>
                    {onStuck ? <button type="button" className="link-btn" onClick={() => onStuck(s, state.kind)}>{content ? '问这一步' : '卡在这步'}</button> : null}
                    {groupOf(s.n) ? (
                      <button type="button" className="step-card__voices" aria-expanded={open === s.n} onClick={() => setOpen((v) => (v === s.n ? null : s.n))}>
                        {[groupOf(s.n).stuck ? `${groupOf(s.n).stuck} 人卡在这` : '', groupOf(s.n).fixes ? `${groupOf(s.n).fixes} 个办法` : ''].filter(Boolean).join(' · ') || '评论区提到'}
                      </button>
                    ) : null}
                  </span>
                </div>
                {open === s.n && groupOf(s.n) ? <Viewers group={groupOf(s.n)} onSeek={onSeek} /> : null}
              </li>
            ))}
          </ol>
          {general ? (
            <details className="steps-tab__general">
              <summary>和整个教程有关的 {general.items.length} 条</summary>
              <Viewers group={general} onSeek={onSeek} />
            </details>
          ) : null}
          <button type="button" className="link-btn steps-tab__redo" onClick={start} disabled={running}>{running ? '整理中…' : '重新整理'}</button>
        </>
      ) : (
        running ? (
          <div className="steps-tab__working">
            <Working label="正在整理步骤" hint="读整段语音和画面文字，从开头到结尾按顺序列出每一步。一般 10–60 秒，视频越长越久；切到别的页也会继续。" />
          </div>
        ) : <div className="bench__idle">
          <IconFilm size={28} />
          <h3>整理步骤</h3>
          <p className="body-sm muted">把视频按顺序列成步骤卡：教程写清每一步点哪里、填什么，其他视频写清每一段讲了什么、发生了什么。每张卡配上那一刻的画面，点时间就回到原视频那一秒，也可以导入笔记。</p>
          {state?.status === 'empty' ? <p className="caption muted">{state.message}</p> : null}
          <button type="button" className="btn btn--dark" onClick={start} disabled={running}>{running ? '整理中…' : state?.status === 'empty' ? '再试一次' : '整理步骤'}</button>
          <p className="caption muted">算一次提问，大约十几秒。</p>
        </div>
      )}
      {error ? <p className="bench__error">{error}</p> : null}
    </div>
  )
}
