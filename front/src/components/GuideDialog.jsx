import React, { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconArrowLeft, IconArrowRight, IconClose } from './Icons'
import '../styles/guide.css'

// First-visit walkthrough with the mascot as the teacher: at each step the snake crawls along the
// track to a new spot (crawl-left / crawl-right), then settles into that step's mood (idle, think,
// verify, done) and explains one thing beside it. Reduced motion: it just appears at each spot.

const ART = (name) => `${import.meta.env.BASE_URL}brand/guide/${name}.webp`
const CRAWL_MS = 1100

const STEPS = [
  {
    at: 14, mood: 'idle', title: '你好，我是帧寻的小蛇',
    body: '我陪你看视频：把视频拆成关键帧，听清每一句话，读出画面上的字，然后回答你的问题。',
  },
  {
    at: 36, mood: 'think', title: '第一步：导入视频',
    body: '粘贴 B 站链接，或者上传本地视频、图片，点「开始解析」。一两分钟后，时间轴就准备好了。',
    demo: 'import',
  },
  {
    at: 60, mood: 'think', title: '第二步：像问老师一样提问',
    body: '软件教程、知识讲解、生活视频都可以问。卡在哪一步、为什么这么做、某个按钮在哪，都能问我。',
    demo: 'ask',
  },
  {
    at: 84, mood: 'verify', title: '第三步：每个结论都有证据',
    body: '回答里的每个结论后面都标着证据和时间。点一下，就跳到原片的那一刻回看，自己核对。',
    demo: 'evidence',
  },
  {
    at: 50, mood: 'done', title: '准备好了！',
    body: '免费账号每天可以导入 3 个视频、提问 10 次。登录后，换电脑或手机，历史都在。',
  },
]

function Demo({ kind }) {
  if (kind === 'import') {
    return (
      <div className="guide-demo guide-demo--import" aria-hidden="true">
        <span className="guide-demo__field">https://www.bilibili.com/video/BV1gD421u75J</span>
        <span className="guide-demo__button">开始解析 →</span>
      </div>
    )
  }
  if (kind === 'ask') {
    return <div className="guide-demo guide-demo--ask" aria-hidden="true">第二种加字幕的方法，是在哪一步点了什么按钮？</div>
  }
  return (
    <div className="guide-demo guide-demo--evidence" aria-hidden="true">
      <span>在音频片段上点右键，选「识别字幕」</span>
      <span className="ev-chip ev-chip--frame">画面 00:56</span>
      <span className="ev-chip ev-chip--speech">原声 00:54</span>
      <span className="ev-chip ev-chip--screentext">画面文字 00:55</span>
    </div>
  )
}

export default function GuideDialog({ onClose, onStart, signedIn = true }) {
  const [step, setStep] = useState(0)
  const [x, setX] = useState(STEPS[0].at)
  const [crawl, setCrawl] = useState(null) // 'left' | 'right' while moving
  const timer = useRef(null)
  const still = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const current = STEPS[step]
  const last = step === STEPS.length - 1

  useEffect(() => {
    clearTimeout(timer.current)
    const target = STEPS[step].at
    if (still || target === x) { setX(target); setCrawl(null); return undefined }
    setCrawl(target > x ? 'right' : 'left')
    setX(target)
    timer.current = setTimeout(() => setCrawl(null), CRAWL_MS)
    return () => clearTimeout(timer.current)
  }, [step]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const key = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight' && !last) setStep((s) => s + 1)
      if (e.key === 'ArrowLeft' && step > 0) setStep((s) => s - 1)
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [last, step, onClose])

  const moving = Boolean(crawl)
  return createPortal(
    <div className="overlay guide-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <section className="guide" role="dialog" aria-modal="true" aria-label="新手引导">
        <header className="guide__head">
          <span className="guide__count">新手引导 · {step + 1}/{STEPS.length}</span>
          <button type="button" className="guide__skip" onClick={onClose}>跳过 <IconClose size={12} /></button>
        </header>
        <div className="guide__stage">
          <div className="guide__track" aria-hidden="true">
            {STEPS.map((s, i) => <span key={i} className={`guide__stop${i <= step ? ' is-reached' : ''}`} style={{ left: `${s.at}%` }} />)}
          </div>
          <div className={`guide__snake${moving ? ' is-moving' : ''}`} style={{ left: `${x}%`, transitionDuration: still ? '0ms' : `${CRAWL_MS}ms` }}>
            <img src={moving ? ART(`crawl-${crawl}`) : ART(current.mood)} alt="" draggable="false"
              className={moving ? 'guide__img guide__img--crawl' : 'guide__img'} />
          </div>
        </div>
        <div className={`guide__bubble${moving ? ' is-waiting' : ''}`} aria-live="polite"
          style={{ '--x': `${x}%`, '--crawl': still ? '0ms' : `${CRAWL_MS}ms` }}>
          <h2>{current.title}</h2>
          <p>{current.body}</p>
          {current.demo ? <Demo kind={current.demo} /> : null}
        </div>
        <footer className="guide__foot">
          <div className="guide__dots" role="tablist" aria-label="步骤">
            {STEPS.map((s, i) => (
              <button key={i} type="button" role="tab" aria-selected={i === step} aria-label={`第 ${i + 1} 步：${s.title}`}
                className={`guide__dot${i === step ? ' is-on' : ''}`} onClick={() => setStep(i)} />
            ))}
          </div>
          <div className="guide__nav">
            {step > 0 ? <button type="button" className="btn btn--ghost" onClick={() => setStep(step - 1)}><IconArrowLeft size={12} /> 上一步</button> : null}
            {last ? (
              <button type="button" className="btn btn--dark" onClick={onStart}>{signedIn ? '开始使用' : '注册并开始'}</button>
            ) : (
              <button type="button" className="btn btn--dark" onClick={() => setStep(step + 1)}>下一步 <IconArrowRight size={12} /></button>
            )}
          </div>
        </footer>
      </section>
    </div>,
    document.body,
  )
}
