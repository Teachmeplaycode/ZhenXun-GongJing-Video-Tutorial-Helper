import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import SculptureCanvas from './components/SculptureCanvas'
import TimelineSculpture from './components/TimelineSculpture'
import BackButton from './components/BackButton'
import { HistoryDrawer } from './components/SessionList'
import AccountsDrawer from './components/AccountsDrawer'
import { IconHistory, IconUser } from './components/Icons'
import HeroOrnaments from './components/HeroOrnaments'
import Wordmark from './components/Wordmark'
import ImportPanel from './stages/ImportPanel'
import UploadMask from './stages/UploadMask'
import AnalyzeHud from './stages/AnalyzeHud'
import ChatStage from './stages/ChatStage'
import { createLinkJob, deleteSession, getSession, linkFrameUrl, listSessions, retryLinkJob, streamLinkJob, uploadVideo } from './api/client'
import { mockUpload } from './api/mock'
import { restoreMessages } from './api/useAgentChat'
import { pickFrameCount, syntheticFrames } from './lib/video'
import { token } from './lib/tokens'
import { DUR, EASE, prefersReducedMotion } from './lib/motion'
import { fmtTime, makeRunId } from './lib/format'
import { BRAND } from './config/workspace'

// Forward flow: idle → uploading → analyzing → ready → chat; each step can return.
const STEPS = [
  { n: '01', label: '导入视频', stages: ['idle'] },
  { n: '02', label: '解析时间轴', stages: ['uploading', 'analyzing', 'ready'] },
  { n: '03', label: '对话分析', stages: ['chat'] },
]
const SAMPLE_META = { name: '示例素材.mp4', size: 0, type: 'video/mp4', duration: 192, width: 1920, height: 1080, sample: true }
const EMPTY_ANALYSIS = { meta: false, frames: 0, total: 0, missing: 0, index: false, transcript: null }
// Frames sampled before chat may start while the rest keep arriving in the background.
const EARLY_CHAT_FRAMES = 16

// Missing-frame reasons as sent in a job snapshot (live events carry the message themselves).
const MISSING_REASONS = {
  trial: '试看限制，无法读取',
  unreachable: '播放地址均无法读取',
  timeout: '读取超时',
  error: '解码失败',
  interrupted: '抓取被中断（后端重启）',
}

// Partial coverage is a normal outcome: say what is missing and keep going.
function coverageNotice(coverage) {
  if (!coverage || !coverage.total) return ''
  if (!coverage.ok) return '没有取到任何画面，仍可基于视频标题和简介对话，也可以稍后补抓'
  if (!coverage.missing) return ''
  const ranges = coverage.missing_ranges.slice(0, 3).map(([a, b]) => `${fmtTime(a)}–${fmtTime(b)}`).join('、')
  const more = coverage.missing_ranges.length > 3 ? ' 等' : ''
  return `已获取 ${coverage.ok}/${coverage.total} 帧，${ranges}${more} 未取得画面；可以直接对话，也可以补抓`
}

export default function App() {
  const [stage, setStage] = useState('idle')
  const [runId, setRunId] = useState(() => makeRunId())
  const [meta, setMeta] = useState(null)
  const [video, setVideo] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [maskMounted, setMaskMounted] = useState(false)
  const [analysis, setAnalysis] = useState(EMPTY_ANALYSIS)
  const [frames, setFrames] = useState([])
  const [notice, setNotice] = useState('')
  const [selected, setSelected] = useState([])
  const [importError, setImportError] = useState('')
  const [coverage, setCoverage] = useState(null)
  const [retrying, setRetrying] = useState(false)
  const [initialMessages, setInitialMessages] = useState([])
  const [sessions, setSessions] = useState([])
  const [sessionsError, setSessionsError] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [accountsOpen, setAccountsOpen] = useState(null) // null: closed; '' or a platform id to put first
  // A time clicked in an answer: the timeline points at the nearest frame. `key` re-triggers the same time.
  const [seek, setSeek] = useState(null)
  // The chat's timeline can fold away for a taller chat; remembered across visits.
  const [timelineOpen, setTimelineOpenState] = useState(() => {
    try {
      return localStorage.getItem('timeline.open') !== '0'
    } catch {
      return true
    }
  })
  const [timelinePulse, setTimelinePulse] = useState(0)
  const setTimelineOpen = (value) => {
    setTimelineOpenState(value)
    try {
      localStorage.setItem('timeline.open', value ? '1' : '0')
    } catch {
      // private mode: still toggles for this visit
    }
  }

  const sculptureLayerRef = useRef(null)
  const uiLayerRef = useRef(null)
  const slideRef = useRef(null)
  const maskEnterRef = useRef(null)
  const maskRef = useRef(null)
  const contourRef = useRef(null)
  const wipeRef = useRef(null)
  const abortRef = useRef(null)
  const navigationRef = useRef(null)

  useLayoutEffect(() => () => {
    abortRef.current?.abort()
    navigationRef.current?.kill()
  }, [])

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listSessions())
      setSessionsError('')
    } catch (err) {
      setSessionsError(err.message)
    }
  }, [])
  // The homepage list and the drawer show the latest state whenever they come into view.
  useEffect(() => {
    if (stage === 'idle' || historyOpen) refreshSessions()
  }, [stage, historyOpen, refreshSessions])

  // §7.1 idle_to_uploading: the import slide opens into a window that grows to the full screen,
  // revealing the contour terrain through it, while the headline lifts away and the model recedes.
  // Keyed on the mask only: a fast upload must not cut the opening short.
  useLayoutEffect(() => {
    if (!maskMounted || !maskRef.current) return undefined
    const mask = maskRef.current
    const frame = mask.querySelector('.upload-mask__frame')
    const vw = window.innerWidth
    const vh = window.innerHeight
    const r = slideRef.current?.getBoundingClientRect()
    const box = r && r.width
      ? { t: r.top, r: vw - r.right, b: vh - r.bottom, l: r.left, rad: 8 }
      : { t: vh / 2, r: vw / 2, b: vh / 2, l: vw / 2, rad: 8 }
    const apply = () => {
      mask.style.clipPath = `inset(${box.t}px ${box.r}px ${box.b}px ${box.l}px round ${box.rad}px)`
      Object.assign(frame.style, { top: `${box.t}px`, right: `${box.r}px`, bottom: `${box.b}px`, left: `${box.l}px`, borderRadius: `${box.rad}px` })
    }
    const heroParts = uiLayerRef.current?.querySelectorAll('[data-exit]') ?? []
    const slideBody = slideRef.current?.querySelector('.import-slide__body')
    const entering = mask.querySelectorAll('[data-enter]')
    const tl = gsap.timeline()
    maskEnterRef.current = tl
    if (prefersReducedMotion()) {
      tl.set(mask, { opacity: 1, clipPath: 'none' }).set(contourRef.current, { opacity: 1 }).set(sculptureLayerRef.current, { opacity: 0 })
      return () => tl.kill()
    }
    apply()
    tl.set(mask, { opacity: 1 })
      .set(frame, { opacity: 1 })
      .to(slideBody, { opacity: 0, duration: DUR.micro, ease: EASE.exit }, 0)
      .to(heroParts, { opacity: 0, y: -12, duration: DUR.short, ease: EASE.exit, stagger: 0.04 }, 0)
      .to(sculptureLayerRef.current, { opacity: 0, scale: 0.96, duration: DUR.medium, ease: EASE.move }, 0)
      .to(slideRef.current, { opacity: 0, duration: DUR.short, ease: EASE.move }, 0.1)
      .to(box, { t: 0, r: 0, b: 0, l: 0, rad: 0, duration: DUR.long, ease: EASE.expand, onUpdate: apply }, 0.12)
      .fromTo(contourRef.current, { opacity: 0 }, { opacity: 1, duration: DUR.medium, ease: EASE.enter }, 0.12)
      .to(frame, { opacity: 0, duration: DUR.short, ease: EASE.enter }, 1.15)
      .set(mask, { clipPath: 'none' })
      .fromTo(entering, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: DUR.short, ease: EASE.enter, stagger: 0.06 }, 1.0)
    return () => tl.kill()
  }, [maskMounted]) // eslint-disable-line react-hooks/exhaustive-deps

  // Leaving the upload screen: it wipes up like a curtain onto the analysis scene underneath.
  const exitMask = async (signal) => {
    const enter = maskEnterRef.current
    if (enter && enter.progress() < 1) await new Promise((r) => enter.eventCallback('onComplete', r))
    return new Promise((resolve, reject) => {
      signal.throwIfAborted()
      const onAbort = () => {
        tl.kill()
        reject(new DOMException('aborted', 'AbortError'))
      }
      const tl = gsap.timeline({ onComplete: () => {
        signal.removeEventListener('abort', onAbort)
        resolve()
      } })
      signal.addEventListener('abort', onAbort, { once: true })
      if (prefersReducedMotion()) {
        tl.set(maskRef.current, { opacity: 0 }).set(sculptureLayerRef.current, { opacity: 1, scale: 1 })
        return
      }
      const mask = maskRef.current
      const box = { b: 0 }
      tl.to(mask.querySelectorAll('[data-enter]'), { opacity: 0, y: -12, duration: DUR.short, ease: EASE.exit, stagger: 0.04 }, 0.1)
        .to(box, {
          b: 100,
          duration: DUR.long,
          ease: EASE.expand,
          onUpdate: () => { mask.style.clipPath = `inset(0 0 ${box.b}% 0)` },
        }, 0.2)
        .fromTo(sculptureLayerRef.current, { opacity: 0, scale: 1.04 }, { opacity: 1, scale: 1, duration: DUR.scene, ease: EASE.move }, 0.4)
    })
  }

  const waitMaskEnter = async () => {
    const enter = maskEnterRef.current
    if (enter && enter.progress() < 1) await new Promise((r) => enter.eventCallback('onComplete', r))
  }

  // Apply a link job's frame events to the timeline until the run reports `done`.
  const followLinkJob = async (jobId, since, signal, notes = []) => {
    await streamLinkJob(jobId, since, (ev) => {
      if (signal.aborted) return
      if (ev.type === 'frame' || ev.type === 'missing') {
        const ok = ev.type === 'frame'
        setFrames((list) => list.map((f) => (f.index === ev.index
          ? { ...f, src: ok ? linkFrameUrl(jobId, ev.index) : null, status: ok ? 'ok' : 'missing', reason: ok ? '' : ev.message, reasonCode: ok ? '' : ev.reason }
          : f)))
        setAnalysis((a) => ({ ...a, frames: a.frames + (ok ? 1 : 0), missing: a.missing + (ok ? 0 : 1) }))
      } else if (ev.type === 'status') {
        setAnalysis((a) => ({ ...a, status: ev.message }))
      } else if (ev.type === 'transcript') {
        setAnalysis((a) => ({ ...a, transcript: { status: ev.status, message: ev.message, count: ev.count } }))
      } else if (ev.type === 'done') {
        // Frames are finished: chat can start; the stream stays open while speech is still transcribing.
        setCoverage(ev.coverage)
        setNotice([...notes, coverageNotice(ev.coverage)].filter(Boolean).join('；'))
        setAnalysis((a) => ({ ...a, index: true, status: '' }))
        setStage((s) => (s === 'analyzing' ? 'ready' : s))
      }
    }, signal)
    signal.throwIfAborted()
    setAnalysis((a) => ({ ...a, index: true, status: '' }))
    setStage((s) => (s === 'analyzing' ? 'ready' : s))
  }

  // Backend job flow, for links and uploaded files alike: create the job under the upload screen
  // (resolving the link, or uploading with progress), then follow its frames and transcript.
  const runJob = async ({ link, file, task }, signal) => {
    const baseMeta = link
      ? { name: link, size: 0, type: 'link', duration: NaN, width: 0, height: 0, link: true, backend: true, sample: false }
      : { name: file.name, size: file.size, type: file.type, duration: NaN, width: 0, height: 0, link: false, backend: true, sample: false }
    setMeta(baseMeta)
    setMaskMounted(true)
    setStage('uploading')
    setUploadProgress(link ? 0.12 : 0)
    let job = null
    try {
      // Long enough for the window to open and the terrain to draw before switching scenes.
      const minimum = new Promise((r) => setTimeout(r, 2400))
      job = link
        ? await createLinkJob(link, { task, signal })
        : await uploadVideo(file, { task, signal, onProgress: (p) => { if (!signal.aborted) setUploadProgress(p) } })
      signal.throwIfAborted()
      setUploadProgress(1)
      await minimum
      signal.throwIfAborted()
      const v = job.video
      setMeta({ ...baseMeta, name: link ? v.title || v.video_id : file.name, duration: v.duration, platform: v.platform, videoId: v.video_id, author: v.author, part: v.part, partCount: v.parts.length })
      setVideo({ videoId: job.job_id, jobId: job.job_id, task, title: v.title, description: v.description })
      setFrames(job.slots.map((slot) => ({ index: slot.index, time: slot.time, src: null, status: 'pending' })))
      setAnalysis({ ...EMPTY_ANALYSIS, meta: true, total: job.slots.length, transcript: job.transcript })
      if (v.notes?.length) setNotice(v.notes.join('；'))
      await waitMaskEnter()
      signal.throwIfAborted()
      setStage('analyzing')
      await exitMask(signal)
      signal.throwIfAborted()
      setMaskMounted(false)
      await followLinkJob(job.job_id, 0, signal, v.notes || [])
    } catch (err) {
      if (signal.aborted || err.name === 'AbortError') return
      if (job) {
        setNotice(err.message)
        return
      }
      // Resolution or upload failed: close the upload screen and show why on the import slide.
      gsap.to(maskRef.current, {
        opacity: 0,
        duration: DUR.short,
        ease: EASE.exit,
        onComplete: () => {
          reset()
          setImportError(err.message)
        },
      })
    }
  }

  const retryMissing = async () => {
    if (!video?.jobId || retrying) return
    const signal = abortRef.current?.signal
    if (!signal || signal.aborted) return
    setRetrying(true)
    try {
      const { retrying: count, transcript, since } = await retryLinkJob(video.jobId, { signal })
      if (count) {
        setFrames((list) => list.map((f) => (f.status === 'missing' && f.reasonCode !== 'trial' ? { ...f, status: 'pending', reason: '' } : f)))
        setAnalysis((a) => ({ ...a, missing: a.missing - count }))
      }
      if (transcript) setAnalysis((a) => ({ ...a, transcript: { status: 'running', message: '正在重新转写', count: 0 } }))
      if (count || transcript) {
        setNotice([count ? `正在补抓 ${count} 帧` : '', transcript ? '正在重新转写语音' : ''].filter(Boolean).join('，') + '…')
        await followLinkJob(video.jobId, since, signal)
      }
    } catch (err) {
      if (err.name !== 'AbortError') setNotice(err.message)
    } finally {
      setRetrying(false)
    }
  }

  const start = useCallback(async ({ file, task, link }) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const { signal } = controller
    setRunId(makeRunId())
    setAnalysis(EMPTY_ANALYSIS)
    setFrames([])
    setNotice('')
    setSelected([])
    setUploadProgress(0)
    setVideo(null)
    setImportError('')
    setCoverage(null)
    setRetrying(false)
    setInitialMessages([])
    if (link || file) {
      await runJob({ link, file, task }, signal)
      return
    }

    // The sample: a scripted demo on placeholder frames, with mocked upload and answers.
    const nextMeta = SAMPLE_META
    setMeta(nextMeta)
    setMaskMounted(true)
    setStage('uploading')

    try {
      const uploaded = await mockUpload(null, {
        onProgress: (progress) => { if (!signal.aborted) setUploadProgress(progress) },
        signal,
      })
      signal.throwIfAborted()
      setVideo({ videoId: uploaded.video_id, task })
      // Switch to the analysis scene under the mask once it fully covers, then wipe it away.
      await waitMaskEnter()
      signal.throwIfAborted()
      setStage('analyzing')
      await exitMask(signal)
      signal.throwIfAborted()
      setMaskMounted(false)

      setAnalysis((a) => ({ ...a, meta: true }))
      const total = pickFrameCount(nextMeta.duration)
      setAnalysis((a) => ({ ...a, total }))
      const list = syntheticFrames(total, nextMeta.duration, {
        surface: token('--bg-surface-alt'),
        line: token('--border-strong'),
        ink: token('--text-secondary'),
      })
      for (let i = 0; i < list.length; i += 1) {
        await new Promise((r) => setTimeout(r, 45))
        if (signal.aborted) throw new DOMException('aborted', 'AbortError')
        setFrames(list.slice(0, i + 1))
        setAnalysis((a) => ({ ...a, frames: i + 1 }))
      }
      await new Promise((r) => setTimeout(r, 600))
      signal.throwIfAborted()
      setFrames(list)
      setAnalysis((a) => ({ ...a, index: true }))
      setStage('ready')
    } catch (err) {
      if (!signal.aborted && err.name !== 'AbortError') setNotice(err.message)
    }
  }, [])

  // Container refresh: an inverse panel wipes up, content swaps, then wipes away.
  const enterChat = () => {
    navigationRef.current?.kill()
    const wipe = wipeRef.current
    navigationRef.current = gsap.timeline()
      .set(wipe, { display: 'block', scaleY: 0, transformOrigin: '50% 100%' })
      .to(wipe, { scaleY: 1, duration: 0.6, ease: EASE.move })
      .add(() => {
        setAnalysis((a) => ({ ...a, index: true }))
        setStage('chat')
      })
      .set(wipe, { transformOrigin: '50% 0%' }, '+=0.1')
      .to(wipe, { scaleY: 0, duration: 0.6, ease: EASE.move })
      .set(wipe, { display: 'none' })
  }

  // Reopen a saved session straight into the conversation, behind the same container wipe.
  const openSession = async (id) => {
    setHistoryOpen(false)
    if (video?.jobId === id) {
      if (stage === 'ready') enterChat()
      if (stage === 'chat' || stage === 'ready') return
    }
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const { signal } = controller
    let saved
    try {
      saved = await getSession(id, { signal })
    } catch (err) {
      if (err.name === 'AbortError') return
      setSessionsError(err.message)
      setHistoryOpen(true)
      return
    }
    const v = saved.video
    const nextFrames = saved.slots.map((slot) => ({
      index: slot.index,
      time: slot.time,
      src: slot.status === 'ok' ? linkFrameUrl(id, slot.index) : null,
      status: slot.status,
      reason: slot.status === 'missing' ? MISSING_REASONS[slot.reason] || slot.reason : '',
      reasonCode: slot.reason,
    }))
    const apply = () => {
      setRunId(makeRunId())
      setMaskMounted(false)
      setMeta({ name: v.title || v.video_id, size: 0, type: 'link', duration: v.duration, width: 0, height: 0, link: v.platform !== 'local', backend: true, sample: false, platform: v.platform, videoId: v.video_id, author: v.author, part: v.part, partCount: v.parts.length })
      setVideo({ videoId: id, jobId: id, task: saved.task, title: v.title, description: v.description })
      setFrames(nextFrames)
      setCoverage(saved.coverage)
      setAnalysis({ ...EMPTY_ANALYSIS, meta: true, total: saved.slots.length, frames: saved.coverage.ok, missing: saved.coverage.missing, index: true, transcript: saved.transcript })
      setNotice(saved.running ? '' : [...(v.notes || []), coverageNotice(saved.coverage)].filter(Boolean).join('；'))
      setInitialMessages(restoreMessages(saved.messages, nextFrames))
      setSelected([])
      setImportError('')
      setRetrying(false)
      setStage('chat')
    }
    navigationRef.current?.kill()
    const wipe = wipeRef.current
    if (prefersReducedMotion()) apply()
    else {
      navigationRef.current = gsap.timeline()
        .set(wipe, { display: 'block', scaleY: 0, transformOrigin: '50% 100%' })
        .to(wipe, { scaleY: 1, duration: 0.6, ease: EASE.move })
        .add(apply)
        .set(wipe, { transformOrigin: '50% 0%' }, '+=0.1')
        .to(wipe, { scaleY: 0, duration: 0.6, ease: EASE.move })
        .set(wipe, { display: 'none' })
    }
    // Sampling still running (e.g. reopened right after parsing): keep the timeline filling in.
    if (saved.running || saved.transcript?.status === 'running') {
      followLinkJob(id, saved.seq, signal).catch((err) => {
        if (err.name !== 'AbortError') setNotice(err.message)
      })
    }
  }

  const removeSession = async (id) => {
    try {
      await deleteSession(id)
      if (video?.jobId === id) reset()
      await refreshSessions()
    } catch (err) {
      setSessionsError(err.message)
    }
  }

  // Undo the exit animation of the import column so returning shows it intact.
  const restoreImport = () => {
    const parts = uiLayerRef.current?.querySelectorAll('[data-exit], .import-slide, .import-slide__body')
    if (parts?.length) gsap.set(parts, { clearProps: 'opacity,transform' })
  }

  const reset = () => {
    abortRef.current?.abort()
    navigationRef.current?.kill()
    gsap.set(wipeRef.current, { display: 'none', scaleY: 0 })
    if (sculptureLayerRef.current) gsap.set(sculptureLayerRef.current, { opacity: 1, scale: 1 })
    restoreImport()
    setStage('idle')
    setMaskMounted(false)
    setFrames([])
    setSelected([])
    setMeta(null)
    setVideo(null)
    setAnalysis(EMPTY_ANALYSIS)
    setUploadProgress(0)
    setNotice('')
    setCoverage(null)
    setRetrying(false)
  }

  const goBack = () => {
    if (stage !== 'chat') {
      reset()
      return
    }
    navigationRef.current?.kill()
    gsap.set(wipeRef.current, { display: 'none', scaleY: 0 })
    setStage('ready')
  }

  const toggleFrame = (frame) =>
    setSelected((list) =>
      list.some((f) => f.index === frame.index)
        ? list.filter((f) => f.index !== frame.index)
        : [...list, frame].sort((a, b) => a.index - b.index),
    )

  // Uploads are deleted once processed, so only link jobs can re-sample.
  const canRetry = Boolean(video?.jobId) && meta?.platform !== 'local'
  const showSculpture = stage !== 'chat'
  const sculptureMode = stage === 'analyzing' || stage === 'ready' ? 'analyzing' : 'idle'

  return (
    // Uploading keeps the homepage layout underneath, so the slide opens from where it sits.
    <div className={`app app--${stage === 'uploading' ? 'idle app--uploading' : stage}`}>
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true" />
          {/* Once the timeline is built the question is answered: "?" becomes "!". */}
          <Wordmark className="brand__name" confirmed={stage === 'ready' || stage === 'chat'} />
          <span className="brand__sub">{BRAND.product}</span>
        </div>
        <ol className="stepper">
          {STEPS.map((s) => {
            const idx = STEPS.findIndex((x) => x.stages.includes(stage))
            const me = STEPS.indexOf(s)
            const state = me < idx ? 'done' : me === idx ? 'active' : 'pending'
            return (
              <li key={s.n} className="stepper__item" data-state={state}>
                <span className="stepper__n">{s.n}</span>
                {s.label}
              </li>
            )
          })}
        </ol>
        <div className="topbar__right">
          <span className="mono-sm muted">{runId}</span>
          <button type="button" className="btn btn--ghost btn--history" onClick={() => setHistoryOpen(true)} aria-haspopup="dialog">
            <IconHistory size={14} /> 历史
          </button>
          <button type="button" className="btn btn--ghost btn--accounts" onClick={() => setAccountsOpen('')} aria-haspopup="dialog">
            <IconUser size={14} /> 账号
          </button>
          {stage !== 'idle' && !maskMounted ? <BackButton onClick={goBack} destination={stage === 'chat' ? '解析时间轴' : '导入视频'} /> : null}
        </div>
      </header>

      <main className="wireframe">
        <span className="wireframe__tick wireframe__tick--tl" />
        <span className="wireframe__tick wireframe__tick--tr" />
        <span className="wireframe__tick wireframe__tick--bl" />
        <span className="wireframe__tick wireframe__tick--br" />

        {showSculpture ? (
          <div ref={sculptureLayerRef} className="layer layer--sculpture">
            {stage === 'idle' || stage === 'uploading' ? <HeroOrnaments /> : null}
            <SculptureCanvas mode={sculptureMode} align={stage === 'idle' || stage === 'uploading' ? 'side' : 'center'} glassRef={stage === 'idle' || stage === 'uploading' ? slideRef : null} />
          </div>
        ) : null}

        {/* Kept visible while uploading so the slide can open into the upload screen. */}
        <div ref={uiLayerRef} className="layer layer--ui" hidden={stage !== 'idle' && stage !== 'uploading'}>
          <ImportPanel
            onStart={start}
            slideRef={slideRef}
            externalError={importError}
            onClearError={() => setImportError('')}
            sessions={sessions}
            onOpenSession={openSession}
            onShowHistory={() => setHistoryOpen(true)}
            onShowAccounts={(platform) => setAccountsOpen(platform || '')}
          />
        </div>

        {maskMounted && meta ? (
          <UploadMask maskRef={maskRef} contourRef={contourRef} progress={uploadProgress} name={meta.name} size={meta.size} link={Boolean(meta.link)} onBack={goBack} />
        ) : null}

        {(stage === 'analyzing' || stage === 'ready') && meta ? (
          <div className="layer layer--ui">
            <AnalyzeHud
              meta={meta}
              analysis={analysis}
              frames={frames}
              ready={stage === 'ready'}
              notice={notice}
              onNext={enterChat}
              canEnterEarly={Boolean(meta.backend) && analysis.frames >= EARLY_CHAT_FRAMES}
              onRetry={canRetry ? retryMissing : null}
              retrying={retrying}
            />
          </div>
        ) : null}

        {video && analysis.index ? (
          <div className="layer layer--chat" hidden={stage !== 'chat'}>
            <ChatStage
              key={video.jobId || video.videoId}
              initialMessages={initialMessages}
              active={stage === 'chat'}
              video={video}
              frames={frames}
              coverage={coverage}
              transcript={analysis.transcript}
              duration={meta?.duration}
              onSeek={(time) => { setTimelineOpen(true); setSeek({ time, key: Date.now() }) }}
              onPickFrames={() => { setTimelineOpen(true); setTimelinePulse(Date.now()) }}
              selected={selected}
              onClearSelection={() => setSelected([])}
              onRemoveFrame={(index) => setSelected((l) => l.filter((f) => f.index !== index))}
            />
          </div>
        ) : null}

        <div ref={wipeRef} className="wipe" aria-hidden="true" />
      </main>

      <AccountsDrawer open={accountsOpen != null} focus={accountsOpen || null} onClose={() => setAccountsOpen(null)} />

      <HistoryDrawer
        open={historyOpen}
        sessions={sessions}
        error={sessionsError}
        currentId={video?.jobId}
        onOpen={openSession}
        onDelete={removeSession}
        onClose={() => setHistoryOpen(false)}
      />

      {stage === 'chat' ? (
        <TimelineSculpture
          frames={frames}
          duration={meta?.duration}
          selected={selected}
          onToggle={toggleFrame}
          onClear={() => setSelected([])}
          onRetry={canRetry ? retryMissing : null}
          retrying={retrying}
          seek={seek}
          open={timelineOpen}
          onOpenChange={setTimelineOpen}
          pulse={timelinePulse}
        />
      ) : null}
    </div>
  )
}
