import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import SculptureCanvas from './components/SculptureCanvas'
import TimelineSculpture from './components/TimelineSculpture'
import BackButton from './components/BackButton'
import { HistoryDrawer } from './components/SessionList'
import AccountsDrawer from './components/AccountsDrawer'
import MemberDialog from './components/MemberDialog'
import GuideDialog from './components/GuideDialog'
import DocsDialog from './components/DocsDialog'
import ProfileDrawer from './components/ProfileDrawer'
import FramePicker from './components/FramePicker'
import { IconBook, IconHistory, IconTheme, IconUser } from './components/Icons'
import { THEME_LABEL, useTheme } from './lib/theme'
import HeroOrnaments from './components/HeroOrnaments'
import Wordmark from './components/Wordmark'
import SnakeMark from './components/SnakeMark'
import HomepageMascot from './components/HomepageMascot'
import useHomeVisual from './lib/useHomeVisual'
import ClickSpark from './components/ClickSpark'
import DockNav from './components/DockNav'
import ImportPanel from './stages/ImportPanel'
import CompareStage from './stages/CompareStage'
import UploadMask from './stages/UploadMask'
import AnalyzeHud from './stages/AnalyzeHud'
import MobileProcessing from './stages/MobileProcessing'
import ChatStage from './stages/ChatStage'
import PictureStage from './stages/PictureStage'
import { createLinkJob, deleteSession, deleteSource, downloadClip, listSamples, fetchChapters, fetchCuts, fetchSource, getHealth, getSession, signOut, linkFrameUrl, listSessions, retryLinkJob, streamLinkJob, uploadImages, uploadVideo } from './api/client'
import SourcePlayer from './components/SourcePlayer'
import EvidenceBadge from './components/EvidenceBadge'
import { EvidenceContext } from './lib/evidence'
import { mockUpload } from './api/mock'
import { restoreMessages } from './api/useAgentChat'
import { pickFrameCount, syntheticFrames } from './lib/video'
import { token } from './lib/tokens'
import { DUR, EASE, prefersReducedMotion } from './lib/motion'
import { fmtTime, makeRunId } from './lib/format'
import { BRAND } from './config/workspace'

// Forward flow: idle → uploading → analyzing → ready → chat; each step can return.
const STEPS = [
  { n: '01', label: '导入视频', picturesLabel: '导入图片', stages: ['idle'] },
  { n: '02', label: '解析时间轴', picturesLabel: '读取图片', stages: ['uploading', 'analyzing', 'ready'] },
  { n: '03', label: '对话分析', stages: ['chat', 'pictures'] }, // pictures: an image post's page, straight from import
]
const GUIDE_SEEN = 'zhenxun.guide.v1' // localStorage: the walkthrough has been shown once
const SAMPLE_META = { name: '示例素材.mp4', size: 0, type: 'video/mp4', duration: 192, width: 1920, height: 1080, sample: true }
const EMPTY_ANALYSIS = { meta: false, frames: 0, total: 0, missing: 0, index: false, transcript: null, screentext: null }
// Frames sampled before chat may start while the rest keep arriving in the background.
const EARLY_CHAT_FRAMES = 16
const WIPE_PIXEL_COUNT = 160
const WIPE_PIXELS = Array.from({ length: WIPE_PIXEL_COUNT }, (_, index) => index)

function pixelDelay(index, reverse = false) {
  const columns = window.innerWidth <= 860 ? 10 : 16
  const rows = Math.ceil(WIPE_PIXEL_COUNT / columns)
  const x = index % columns
  const y = Math.floor(index / columns)
  return (reverse ? (columns - 1 - x) + (rows - 1 - y) : x + y) * 0.009
}

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

// Frames in time order: shot-fill keyframes arrive later with higher indexes (backend modules/frames/job.py).
const byTime = (list) => [...list].sort((a, b) => a.time - b.time)

export default function App() {
  const { choice: homeVisual, select: selectHomeVisual, mobile, snakeOnly } = useHomeVisual()
  const [stage, setStage] = useState('idle')
  const [comparing, setComparing] = useState(null) // several links pasted on the homepage: { links, sampling, key }
  const [runId, setRunId] = useState(() => makeRunId())
  const [meta, setMeta] = useState(null)
  const [video, setVideo] = useState(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [maskMounted, setMaskMounted] = useState(false)
  const [analysis, setAnalysis] = useState(EMPTY_ANALYSIS)
  const [frames, setFrames] = useState([])
  const [notice, setNotice] = useState('')
  const [clipToast, setClipToast] = useState(null) // cutting a GIF / MP4: { text, error }
  const [selected, setSelected] = useState([])
  const [importError, setImportError] = useState('')
  const [coverage, setCoverage] = useState(null)
  const [retrying, setRetrying] = useState(false)
  const [initialMessages, setInitialMessages] = useState([])
  const [sessions, setSessions] = useState([])
  const [sessionsError, setSessionsError] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [accountsOpen, setAccountsOpen] = useState(null) // null: closed; '' or a platform id to put first
  const [publicDemo, setPublicDemo] = useState(false) // the web demo: no platform logins
  const [samples, setSamples] = useState([]) // finished tutorials to open at once (public site)
  // The web demo's account: { user, oauth }; the sign-in dialog when open: { mode, reason }.
  const [member, setMember] = useState(null)
  const [memberDialog, setMemberDialog] = useState(null)
  const [guideOpen, setGuideOpen] = useState(false) // the mascot's walkthrough; opens by itself on a first visit to the web demo
  const [docsOpen, setDocsOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false) // phones pick frames in a big grid (components/FramePicker.jsx)
  const [profileOpen, setProfileOpen] = useState(false) // 我的: the signed-in person's allowance, logins and sign-out
  const closeGuide = useCallback(() => {
    setGuideOpen(false)
    try { localStorage.setItem(GUIDE_SEEN, '1') } catch { /* private mode: it shows again next time */ }
  }, [])
  const [theme, themeChoice, cycleTheme] = useTheme()
  // A time clicked in an answer: the timeline points at the nearest frame. `key` re-triggers the same time.
  const [seek, setSeek] = useState(null)
  // How cited moments can be looked at again (original / cache / none), and the open player, if any.
  const [source, setSource] = useState({ state: 'cache' })
  const [player, setPlayer] = useState(null) // { time, key }
  useEffect(() => {
    getHealth().then((health) => {
      setPublicDemo(Boolean(health?.public))
      if (health?.public) listSamples().then(setSamples)
      if (health?.public) setMember({ user: health.user || null, oauth: health.oauth || [] })
      let seen = false
      try { seen = localStorage.getItem(GUIDE_SEEN) === '1' } catch { /* show it */ }
      if (health?.public && !seen && !new URLSearchParams(window.location.search).get('login')) setGuideOpen(true)
      if (health?.public && new URLSearchParams(window.location.search).get('login') === 'failed') {
        setMemberDialog({ mode: 'login', reason: '第三方登录没有成功，请再试一次或用用户名登录。' })
      }
    }).catch(() => {})
  }, [])
  const sourceJob = video?.jobId
  const analysisDone = analysis.index
  useEffect(() => {
    setPlayer(null)
    if (!sourceJob) return undefined
    const ctl = new AbortController()
    fetchSource(sourceJob, { signal: ctl.signal }).then(setSource).catch(() => setSource({ state: 'cache' }))
    return () => ctl.abort()
  }, [sourceJob, analysisDone])
  const [pictureFocus, setPictureFocus] = useState(null) // { index, key }: an answer's 「第 n 张」 shows that picture
  const [extraFrames, setExtraFrames] = useState([]) // replayed / closer-look frames from the chat, shown on the timeline
  const [hiddenExtras, setHiddenExtras] = useState(() => new Set()) // those groups cleared off the timeline
  const [cited, setCited] = useState([]) // times the answers point at, marked on the timeline
  const [cuts, setCuts] = useState([]) // the video's shot changes, marked on the timeline
  const [chapterRevision, setChapterRevision] = useState(0)
  const [chaptersData, setChaptersData] = useState(null) // the video's chapter list (modules/chapters)
  const [activeChapter, setActiveChapter] = useState(null) // index picked in the workbench, lit on the timeline
  const [hoverChapter, setHoverChapter] = useState(null) // index pointed at in the workbench
  const [chatBusy, setChatBusy] = useState(false) // an answer or a replay in progress: no new replay meanwhile
  const [clip, setClip] = useState(null) // { start, end } framed on the timeline to ask about
  const [replayRequest, setReplayRequest] = useState(null) // { start, end, key } framed to replay now
  // A stretch framed on the timeline (or the phone's picker): replay it, ask about it, or cut it out.
  const onRangeAction = (start, end, action) => {
    if (action === 'play') setReplayRequest({ start, end, key: Date.now() })
    else if (action === 'gif' || action === 'mp4') cutClip(start, end, action)
    else setClip({ start, end })
  }
  const cutClip = async (start, end, format) => {
    const jobId = video?.jobId
    if (!jobId) return
    const long = format === 'gif' ? end - start > 10 : end - start > 60
    setClipToast({ text: `正在截取 ${format.toUpperCase()}${long ? `（只取前 ${format === 'gif' ? 10 : 60} 秒）` : ''}…` })
    try {
      const name = await downloadClip(jobId, start, end, format)
      setClipToast({ text: `已保存 ${name}` })
    } catch (err) {
      setClipToast({ text: err.message, error: true })
    }
    setTimeout(() => setClipToast(null), 4000)
  }
  // Shot changes: detected in the background since the import; ask until they're ready (marks are optional).
  const inChat = stage === 'chat'
  useEffect(() => {
    setCuts([])
    const jobId = video?.jobId
    if (!jobId || !inChat) return undefined
    let stopped = false
    let timer = 0
    const poll = async (tries) => {
      try {
        const r = await fetchCuts(jobId)
        if (stopped) return
        if (r.status === 'done') setCuts(r.cuts)
        else if (r.status === 'running') timer = setTimeout(() => poll(tries + 1), 3000)
      } catch {
        // no marks: the timeline works without them
      }
    }
    poll(0)
    return () => { stopped = true; clearTimeout(timer) }
  }, [video?.jobId, inChat])
  // Chapters: built in the background after the transcript lands; poll until they settle.
  useEffect(() => {
    setChaptersData(null)
    const jobId = video?.jobId
    if (!jobId || !inChat) return undefined
    let stopped = false
    let timer = 0
    const poll = async (tries) => {
      try {
        const r = await fetchChapters(jobId)
        if (stopped) return
        setChaptersData(r)
        if (r.status === 'running') timer = setTimeout(() => poll(tries + 1), 3000)
      } catch {
        if (!stopped) timer = setTimeout(() => poll(tries + 1), 3000)
      }
    }
    poll(0)
    return () => { stopped = true; clearTimeout(timer) }
  }, [video?.jobId, inChat, chapterRevision])
  // The chat's timeline can fold away for a taller chat; remembered across visits.
  const [timelineOpen, setTimelineOpenState] = useState(() => {
    try {
      const saved = localStorage.getItem('timeline.open')
      if (saved == null) return !window.matchMedia?.('(max-width: 640px)').matches // phones start with it folded
      return saved !== '0'
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
    signal.throwIfAborted()
    if (!maskRef.current) return
    await waitMaskEnter(signal)
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

  const waitMaskEnter = async (signal) => {
    signal.throwIfAborted()
    const enter = maskEnterRef.current
    if (!maskRef.current || !enter || enter.progress() === 1) return
    await new Promise((resolve, reject) => {
      const onAbort = () => reject(new DOMException('aborted', 'AbortError'))
      signal.addEventListener('abort', onAbort, { once: true })
      enter.eventCallback('onComplete', () => {
        signal.removeEventListener('abort', onAbort)
        resolve()
      })
    })
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
      } else if (ev.type === 'slots') {
        // Keyframes for shots the first pass missed (backend shot fill): they arrive pending, in time order.
        setFrames((list) => byTime([...list, ...ev.slots.map((slot) => ({ index: slot.index, time: slot.time, src: null, status: 'pending' }))]))
      } else if (ev.type === 'status') {
        setAnalysis((a) => ({ ...a, status: ev.message }))
      } else if (ev.type === 'transcript') {
        setAnalysis((a) => ({ ...a, transcript: { status: ev.status, message: ev.message, count: ev.count } }))
      } else if (ev.type === 'screentext') {
        setAnalysis((a) => ({ ...a, screentext: { status: ev.status, message: ev.message, count: ev.count } }))
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
  const runJob = async ({ link, file, images = null, task, sampling }, signal) => {
    const baseMeta = link
      ? { name: link, size: 0, type: 'link', duration: NaN, width: 0, height: 0, link: true, backend: true, sample: false }
      : images
        ? { name: `${images.length} 张图片`, size: images.reduce((n, f) => n + f.size, 0), type: 'images', kind: 'images', duration: NaN, width: 0, height: 0, link: false, backend: true, sample: false }
        : { name: file.name, size: file.size, type: file.type, duration: NaN, width: 0, height: 0, link: false, backend: true, sample: false }
    const openProcessing = () => {
      setMeta(baseMeta)
      setMaskMounted(!mobile)
      setStage('uploading')
      setUploadProgress(link ? 0.12 : 0)
    }
    let job = null
    try {
      if (mobile) {
        if (!await wipeThrough(openProcessing)) return
        signal.throwIfAborted()
      } else openProcessing()
      // Long enough for the window to open and the terrain to draw before switching scenes.
      const minimum = new Promise((r) => setTimeout(r, mobile || prefersReducedMotion() ? 0 : 2400))
      const onProgress = (p) => { if (!signal.aborted) setUploadProgress(p) }
      job = link
        ? await createLinkJob(link, { task, sampling, signal })
        : images
          ? await uploadImages(images, { task, signal, onProgress })
          : await uploadVideo(file, { task, sampling, signal, onProgress })
      signal.throwIfAborted()
      setUploadProgress(1)
      await minimum
      signal.throwIfAborted()
      const v = job.video
      setMeta({ ...baseMeta, name: link || images ? v.title || v.video_id : file.name, duration: v.duration, platform: v.platform, videoId: v.video_id, author: v.author, part: v.part, partCount: v.parts.length, kind: v.kind || 'video', description: v.description || '', tags: v.tags || [], stats: v.stats || {} })
      setVideo({ videoId: job.job_id, jobId: job.job_id, task, title: v.title, description: v.description })
      setFrames(byTime(job.slots.map((slot) => ({ index: slot.index, time: slot.time, src: null, status: 'pending' }))))
      setAnalysis({ ...EMPTY_ANALYSIS, meta: true, total: job.slots.length, transcript: job.transcript, screentext: job.screentext || null })
      if (v.notes?.length) setNotice(v.notes.join('；'))
      if (mobile) {
        if (!await wipeThrough(() => {
          if (v.kind === 'images') setAnalysis((a) => ({ ...a, index: true }))
          setStage(v.kind === 'images' ? 'pictures' : 'analyzing')
        })) return
        signal.throwIfAborted()
        await followLinkJob(job.job_id, 0, signal, v.notes || [])
        return
      }
      if (v.kind === 'images') {
        // A picture set skips the analysis screen: its page shows the pictures as they arrive.
        setAnalysis((a) => ({ ...a, index: true }))
        await waitMaskEnter(signal)
        signal.throwIfAborted()
        setStage('pictures')
        // Follow the pictures while the curtain lifts: they show up as soon as they arrive.
        const following = followLinkJob(job.job_id, 0, signal, v.notes || [])
        await exitMask(signal)
        signal.throwIfAborted()
        setMaskMounted(false)
        await following
        return
      }
      await waitMaskEnter(signal)
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
      if (!maskRef.current) {
        reset()
        setImportError(err.message)
        return
      }
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
      const { retrying: count, transcript, screentext, since } = await retryLinkJob(video.jobId, { signal })
      if (count) {
        setFrames((list) => list.map((f) => (f.status === 'missing' && f.reasonCode !== 'trial' ? { ...f, status: 'pending', reason: '' } : f)))
        setAnalysis((a) => ({ ...a, missing: a.missing - count }))
      }
      if (transcript || screentext) setChapterRevision((n) => n + 1)
      if (transcript) setAnalysis((a) => ({ ...a, transcript: { status: 'running', message: '正在重新转写', count: 0 } }))
      if (screentext) setAnalysis((a) => ({ ...a, screentext: { status: 'running', message: '正在重新识别', count: 0 } }))
      if (count || transcript || screentext) {
        setNotice([count ? `正在补抓 ${count} 帧` : '', transcript ? '正在重新转写语音' : '', screentext ? '正在识别画面文字' : '']
          .filter(Boolean).join('，') + '…')
        await followLinkJob(video.jobId, since, signal)
      }
    } catch (err) {
      if (err.name !== 'AbortError') setNotice(err.message)
    } finally {
      setRetrying(false)
    }
  }

  const start = useCallback(async ({ file, task, link, links = null, images = null, sampling = null }) => {
    if (publicDemo && member && !member.user) { // the web demo: importing needs an account
      setMemberDialog({ mode: 'register', reason: '登录后才能导入视频和提问。可以直接点「游客体验」试用，或注册一个账号。' })
      return
    }
    if (links?.length) { // tutorials of the same task: each imported, then compared (stages/CompareStage.jsx)
      setImportError('')
      setComparing({ links, sampling, key: Date.now() })
      wipeThrough(() => setStage('compare'))
      return
    }
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const { signal } = controller
    setRunId(makeRunId())
    setAnalysis(EMPTY_ANALYSIS)
    setFrames([])
    setNotice('')
    setSelected([]); setExtraFrames([]); setHiddenExtras(new Set()); setCited([]); setClip(null); setActiveChapter(null); setHoverChapter(null); setPictureFocus(null)
    setUploadProgress(0)
    setVideo(null)
    setImportError('')
    setCoverage(null)
    setRetrying(false)
    setInitialMessages([])
    if (link || file || images?.length) {
      await runJob({ link, file, images, task, sampling }, signal)
      return
    }

    // The sample: a scripted demo on placeholder frames, with mocked upload and answers.
    const nextMeta = SAMPLE_META
    const openSample = () => {
      setMeta(nextMeta)
      setMaskMounted(!mobile)
      setStage('uploading')
    }
    try {
      if (mobile) {
        if (!await wipeThrough(openSample)) return
        signal.throwIfAborted()
      } else openSample()
      const uploaded = await mockUpload(null, {
        onProgress: (progress) => { if (!signal.aborted) setUploadProgress(progress) },
        signal,
      })
      signal.throwIfAborted()
      setVideo({ videoId: uploaded.video_id, task })
      if (mobile) {
        if (!await wipeThrough(() => setStage('analyzing'))) return
      } else {
        await waitMaskEnter(signal)
        signal.throwIfAborted()
        setStage('analyzing')
        await exitMask(signal)
        setMaskMounted(false)
      }
      signal.throwIfAborted()

      setAnalysis((a) => ({ ...a, meta: true }))
      const total = pickFrameCount(nextMeta.duration)
      setAnalysis((a) => ({ ...a, total }))
      const list = syntheticFrames(total, nextMeta.duration, {
        surface: token('--bg-surface-alt'),
        line: token('--border-strong'),
        ink: token('--text-secondary'),
      })
      for (let i = 0; i < list.length; i += 1) {
        // Keep the demo slow enough for the frame queue to read as real work,
        // rather than flashing past as a decorative transition.
        await new Promise((r) => setTimeout(r, 80))
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
  }, [publicDemo, member, mobile])

  // Container refresh: pixel cells cover the workspace, `apply` swaps the content behind them at the
  // peak, then the cells release diagonally like extracted video frames. The snake mark either flies
  // to `snakeTo` (an {x, y} offset from the centre) or fades where it is.
  const wipeThrough = (apply, snakeTo = null) => {
    navigationRef.current?.kill()
    const wipe = wipeRef.current
    if (prefersReducedMotion() || !wipe) {
      apply()
      return Promise.resolve(true)
    }
    const wipeSnake = wipe.querySelector('.wipe__snake')
    const pixels = [...wipe.querySelectorAll('.wipe__pixel')]
    return new Promise((resolve) => {
      navigationRef.current = gsap.timeline({ onComplete: () => resolve(true), onInterrupt: () => resolve(false) })
      .set(wipe, { display: 'block' })
      .set(pixels, { scale: 0, transformOrigin: '50% 50%' })
      .set(wipeSnake, { opacity: 0, scale: 0.72, x: 0, y: 10, rotation: -8 })
      .to(pixels, { scale: 1.035, duration: 0.2, ease: EASE.enter, stagger: (index) => pixelDelay(index) }, 0)
      .to(wipeSnake, { opacity: 1, scale: 1, y: 0, rotation: 0, duration: 0.3, ease: EASE.bounce }, 0.24)
      .add(apply, 0.44)
      .to(wipeSnake, snakeTo
        ? { ...snakeTo, scale: 0.32, opacity: 0, duration: 0.42, ease: EASE.enter }
        : { opacity: 0, scale: 0.7, duration: 0.24, ease: EASE.exit }, 0.56)
      .to(pixels, { scale: 0, duration: 0.2, ease: EASE.exit, stagger: (index) => pixelDelay(index, true) }, 0.58)
      .set(wipe, { display: 'none' })
      .set(pixels, { clearProps: 'transform' })
      .set(wipeSnake, { clearProps: 'all' })
    })
  }

  const enterChat = () => {
    // The snake lands on the brand mark: the conversation is "inside" the workbench.
    const brandBox = document.querySelector('.brand__mark')?.getBoundingClientRect()
    const target = brandBox
      ? {
          x: brandBox.left + brandBox.width / 2 - window.innerWidth / 2,
          y: brandBox.top + brandBox.height / 2 - window.innerHeight / 2,
        }
      : { x: -window.innerWidth * 0.44, y: -window.innerHeight * 0.46 }
    wipeThrough(() => {
      setAnalysis((a) => ({ ...a, index: true }))
      setStage('chat')
    }, target)
  }

  // Reopen a saved session straight into the conversation, behind the same container wipe.
  // at: a second to show once it is open (a step of another tutorial in the 对照 tab).
  const openSession = async (id, at = null) => {
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
    const nextFrames = byTime(saved.slots.map((slot) => ({
      index: slot.index,
      time: slot.time,
      src: slot.status === 'ok' ? linkFrameUrl(id, slot.index) : null,
      status: slot.status,
      reason: slot.status === 'missing' ? MISSING_REASONS[slot.reason] || slot.reason : '',
      reasonCode: slot.reason,
    })))
    const apply = () => {
      setRunId(makeRunId())
      setMaskMounted(false)
      setMeta({ name: v.title || v.video_id, size: 0, type: 'link', duration: v.duration, width: 0, height: 0, link: v.platform !== 'local', backend: true, sample: false, platform: v.platform, videoId: v.video_id, author: v.author, part: v.part, partCount: v.parts.length, kind: v.kind || 'video', description: v.description || '', tags: v.tags || [], stats: v.stats || {} })
      setVideo({ videoId: id, jobId: id, task: saved.task, title: v.title, description: v.description })
      setFrames(nextFrames)
      setCoverage(saved.coverage)
      setAnalysis({ ...EMPTY_ANALYSIS, meta: true, total: saved.slots.length, frames: saved.coverage.ok, missing: saved.coverage.missing, index: true, transcript: saved.transcript, screentext: saved.screentext || null })
      setNotice(saved.running ? '' : [...(v.notes || []), coverageNotice(saved.coverage)].filter(Boolean).join('；'))
      setInitialMessages(restoreMessages(saved.messages, nextFrames))
      setSelected([]); setExtraFrames([]); setHiddenExtras(new Set()); setCited([]); setClip(null); setActiveChapter(null); setHoverChapter(null); setPictureFocus(null)
      setImportError('')
      setRetrying(false)
      setStage(v.kind === 'images' ? 'pictures' : 'chat')
      if (at != null) { setTimelineOpen(true); setSeek({ time: at, key: Date.now() }) }
    }
    wipeThrough(apply)
    // Sampling still running (e.g. reopened right after parsing): keep the timeline filling in.
    if (saved.running || saved.transcript?.status === 'running' || saved.screentext?.status === 'running') {
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

  // Back to an empty import screen. Inside a wipe (`midWipe`) the running transition is left alone.
  const reset = ({ midWipe = false } = {}) => {
    abortRef.current?.abort()
    if (!midWipe) {
      navigationRef.current?.kill()
      gsap.set(wipeRef.current, { display: 'none', clearProps: 'transform' })
      gsap.set(wipeRef.current?.querySelectorAll('.wipe__pixel'), { clearProps: 'transform' })
    }
    if (sculptureLayerRef.current) gsap.set(sculptureLayerRef.current, { opacity: 1, scale: 1 })
    restoreImport()
    setStage('idle')
    setMaskMounted(false)
    setFrames([])
    setSelected([]); setExtraFrames([]); setHiddenExtras(new Set()); setCited([]); setClip(null); setActiveChapter(null); setHoverChapter(null); setPictureFocus(null)
    setMeta(null)
    setVideo(null)
    setAnalysis(EMPTY_ANALYSIS)
    setUploadProgress(0)
    setNotice('')
    setCoverage(null)
    setRetrying(false)
  }

  // Back one level behind the same pixel wipe as going forward: chat → timeline, anything else → import.
  const goBack = () => wipeThrough(() => reset({ midWipe: true })) // back to the homepage, from the chat too

  const toggleFrame = (frame) =>
    setSelected((list) =>
      list.some((f) => f.index === frame.index)
        ? list.filter((f) => f.index !== frame.index)
        : [...list, frame].sort((a, b) => a.index - b.index),
    )

  // Uploads are deleted once processed, so only link jobs can re-sample.
  const canRetry = Boolean(video?.jobId) && meta?.platform !== 'local'
  const showSculpture = stage !== 'chat' && stage !== 'pictures'
  const homeScene = stage === 'idle' || stage === 'uploading'
  const sculptureEnabled = !mobile && (!homeScene || !snakeOnly)
  const sculptureMode = stage === 'analyzing' || stage === 'ready' ? 'analyzing' : 'idle'
  const settledFrames = analysis.frames + (analysis.missing || 0)
  const isVerifying = stage === 'analyzing' && Boolean(analysis.total) && settledFrames >= analysis.total && !analysis.index
  const brandMarkState = importError
    ? 'error'
    : stage === 'uploading'
      ? 'uploading'
      : stage === 'analyzing'
        ? (isVerifying ? 'verifying' : 'analyzing')
        : stage === 'ready'
          ? 'confirmed'
          : stage === 'chat' || stage === 'pictures'
            ? 'chat'
            : 'idle'

  const pictures = meta?.kind === 'images' // an image post or uploaded pictures (stage 'pictures')
  const chatStage = video ? (
    <ChatStage
      key={video.jobId || video.videoId}
      pictures={pictures}
      initialMessages={initialMessages}
      active={stage === 'chat' || stage === 'pictures'}
      video={video}
      frames={frames}
      coverage={coverage}
      transcript={analysis.transcript}
      screentext={analysis.screentext}
      duration={meta?.duration}
      onSeek={pictures
        ? (time) => setPictureFocus({ index: Math.floor(time), key: Date.now() })
        : (time) => {
          if (source.state === 'original') setPlayer({ time, key: Date.now() }) // 回看原片
          else { setTimelineOpen(true); setSeek({ time, key: Date.now() }) } // 查看缓存证据
        }}
      onPickFrames={() => { setTimelineOpen(true); setTimelinePulse(Date.now()) }}
      framesPanel={mobile && meta?.kind !== 'images' ? (
        <FramePicker embedded frames={frames} duration={meta?.duration} busy={chatBusy} selected={selected} seek={seek}
          chapters={chaptersData?.status === 'done' ? chaptersData.chapters : []}
          onToggle={toggleFrame} onClear={() => setSelected([])}
          onRange={onRangeAction} />
      ) : null}
      selected={selected}
      onClearSelection={() => setSelected([])}
      onRemoveFrame={(index) => setSelected((l) => l.filter((f) => f.index !== index))}
      onExtras={setExtraFrames}
      onCited={setCited}
      onBusy={setChatBusy}
      chapters={chaptersData}
      activeChapter={activeChapter}
      onChapterSelect={setActiveChapter}
      onChapterHover={setHoverChapter}
      replayRequest={replayRequest}
      onOpenSession={(id, at) => openSession(id, at)}
      clip={clip}
      onClearClip={() => setClip(null)}
    />
  ) : null

  const mobileProcessing = mobile && meta && ['uploading', 'analyzing', 'ready'].includes(stage)

  return (
    // Uploading keeps the homepage layout underneath, so the slide opens from where it sits.
    <div className={`app app--${stage === 'uploading' ? 'idle app--uploading' : stage}${homeScene && snakeOnly ? ' app--snake-home' : ''}${mobileProcessing ? ' app--mobile-processing' : ''}`}>
      {mobileProcessing ? (
        <MobileProcessing
          stage={stage} meta={meta} analysis={analysis} frames={frames} uploadProgress={uploadProgress}
          notice={notice} onBack={goBack} onNext={enterChat}
          canEnterEarly={Boolean(meta.backend) && analysis.frames >= EARLY_CHAT_FRAMES}
          onRetry={canRetry ? retryMissing : null} retrying={retrying}
        />
      ) : null}
      <header className="topbar" hidden={Boolean(mobileProcessing)}>
        <div className="brand">
          <SnakeMark className="brand__mark" state={brandMarkState} />
          {/* Once the timeline is built the question is answered: "?" becomes "!". */}
          <Wordmark className="brand__name" confirmed={stage === 'ready' || stage === 'chat' || stage === 'pictures'} />
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
                {(pictures && s.picturesLabel) || s.label}
              </li>
            )
          })}
        </ol>
        <DockNav className="topbar__right">
          {stage === 'idle' && !mobile ? (
            <div className="home-visual-switch" role="group" aria-label="首页显示效果">
              <button type="button" aria-pressed={homeVisual === '3d'} onClick={() => selectHomeVisual('3d')}>ON</button>
              <button type="button" aria-pressed={homeVisual === 'snake'} onClick={() => selectHomeVisual('snake')}>OFF</button>
            </div>
          ) : null}
          <span className="mono-sm muted">{runId}</span>
          <button type="button" className="btn btn--ghost btn--accounts" onClick={() => setDocsOpen(true)} aria-haspopup="dialog">
            <IconBook size={14} /> 文档
          </button>
          <button type="button" className="btn btn--ghost btn--history" onClick={() => setHistoryOpen(true)} aria-haspopup="dialog">
            <IconHistory size={14} /> 历史
          </button>
          <button type="button" className="btn btn--ghost btn--accounts btn--theme" onClick={(e) => cycleTheme(e.currentTarget)}
            title={`主题：${THEME_LABEL[themeChoice]}（点击切换）`} aria-label={`主题：${THEME_LABEL[themeChoice]}`}>
            <IconTheme size={14} /><span className="btn--theme__label">{THEME_LABEL[themeChoice]}</span>
          </button>
          {publicDemo ? (member?.user ? (
            <button type="button" className="btn btn--ghost btn--accounts member-chip" title="我的：额度、平台账号、退出登录"
              onClick={() => setProfileOpen(true)} aria-haspopup="dialog">
              <IconUser size={14} /> {member.user.name}
              {member.user.questions?.limit != null ? (
                <span className="member-chip__left">今日提问 {Math.max(0, member.user.questions.limit - member.user.questions.used)}/{member.user.questions.limit}</span>
              ) : null}
            </button>
          ) : (
            <button type="button" className="btn btn--ghost btn--accounts" onClick={() => setMemberDialog({ mode: 'login' })} aria-haspopup="dialog">
              <IconUser size={14} /> 登录
            </button>
          )) : (
            <button type="button" className="btn btn--ghost btn--accounts" onClick={() => setAccountsOpen('')} aria-haspopup="dialog">
              <IconUser size={14} /> 账号
            </button>
          )}
          {stage !== 'idle' && !maskMounted ? <BackButton onClick={goBack} destination="首页" /> : null}
        </DockNav>
      </header>

      <main className="wireframe" hidden={Boolean(mobileProcessing)}>
        <span className="wireframe__tick wireframe__tick--tl" />
        <span className="wireframe__tick wireframe__tick--tr" />
        <span className="wireframe__tick wireframe__tick--bl" />
        <span className="wireframe__tick wireframe__tick--br" />

        {showSculpture ? (
          <div ref={sculptureLayerRef} className="layer layer--sculpture">
            {sculptureEnabled ? (
              <>
                {homeScene ? <HeroOrnaments /> : null}
                <SculptureCanvas key={theme} mode={sculptureMode} complete={stage === 'ready'} align={homeScene ? 'side' : 'center'} glassRef={homeScene ? slideRef : null} />
              </>
            ) : null}
          </div>
        ) : null}

        {/* Kept visible while uploading so the slide can open into the upload screen. */}
        <div ref={uiLayerRef} className="layer layer--ui" hidden={stage !== 'idle' && stage !== 'uploading'}>
          <ImportPanel
            showMascot={snakeOnly}
            active={stage === 'idle'}
            onStart={start}
            slideRef={slideRef}
            externalError={importError}
            onClearError={() => setImportError('')}
            onShowAccounts={publicDemo ? null : (platform) => setAccountsOpen(platform || '')}
            publicDemo={publicDemo}
            samples={samples}
            onOpenSample={openSession}
          />
        </div>

        {stage === 'idle' && !snakeOnly ? <HomepageMascot state={importError ? 'think' : 'idle'} /> : null}

        {maskMounted && meta && !mobile ? (
          <UploadMask maskRef={maskRef} contourRef={contourRef} progress={uploadProgress} name={meta.name} size={meta.size} link={Boolean(meta.link)} onBack={goBack} />
        ) : null}

        {stage === 'compare' && comparing ? (
          <div className="layer layer--ui layer--compare">
            <CompareStage key={comparing.key} links={comparing.links} sampling={comparing.sampling} onOpenSession={(id, at) => openSession(id, at)} />
          </div>
        ) : null}

        {(stage === 'analyzing' || stage === 'ready') && meta && !mobile ? (
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

        {video && analysis.index && !pictures ? (
          <div className="layer layer--chat" hidden={stage !== 'chat'} data-player={player ? '' : undefined}>
            <EvidenceContext.Provider value={source}>
              {chatStage}
              {video.jobId && stage === 'chat' ? (
                <>
                  {player ? null : <EvidenceBadge source={source} upload={meta?.platform === 'local'}
                    onDelete={async () => setSource(await deleteSource(video.jobId))} />}
                  <SourcePlayer jobId={video.jobId} request={player} label={source.label} onClose={() => setPlayer(null)}
                    onFallback={(time) => { setPlayer(null); setTimelineOpen(true); setSeek({ time, key: Date.now() }) }} />
                </>
              ) : null}
            </EvidenceContext.Provider>
          </div>
        ) : null}
        {video && pictures ? (
          <div className="layer layer--pictures" hidden={stage !== 'pictures'}>
            <PictureStage meta={meta} jobId={video.jobId} frames={frames} selected={selected} onToggle={toggleFrame}
              screentext={analysis.screentext} focus={pictureFocus}>
              {chatStage}
            </PictureStage>
          </div>
        ) : null}

      </main>

        <div ref={wipeRef} className="wipe" aria-hidden="true">
          <div className="wipe__pixels">
            {WIPE_PIXELS.map((index) => <i key={index} className="wipe__pixel" data-accent={index % 47 === 18 || undefined} />)}
          </div>
          <SnakeMark className="wipe__snake" state="confirmed" framed />
        </div>


      {pickerOpen && stage === 'chat' ? (
        <FramePicker frames={frames} duration={meta?.duration} busy={chatBusy} selected={selected}
          chapters={chaptersData?.status === 'done' ? chaptersData.chapters : []}
          onToggle={toggleFrame} onClear={() => setSelected([])} onClose={() => setPickerOpen(false)}
          onRange={meta?.kind === 'images' ? null : onRangeAction} />
      ) : null}
      {clipToast ? <div className="clip-toast" role="status" data-error={clipToast.error || undefined}>{clipToast.text}</div> : null}
      <ProfileDrawer open={profileOpen && Boolean(member?.user)} user={member?.user} onClose={() => setProfileOpen(false)}
        onAccounts={() => { setProfileOpen(false); setAccountsOpen('') }}
        onHistory={() => { setProfileOpen(false); setHistoryOpen(true) }}
        onRegister={() => { setProfileOpen(false); setMemberDialog({ mode: 'register', reason: '注册后，游客期间导入的视频会一起保留。' }) }}
        onSignOut={() => signOut().finally(() => window.location.reload())} />
      {guideOpen ? (
        <GuideDialog signedIn={!publicDemo || Boolean(member?.user)} onClose={closeGuide}
          onStart={() => {
            closeGuide()
            if (publicDemo && !member?.user) setMemberDialog({ mode: 'register', reason: '点「游客体验」马上试用，或注册一个账号。' })
          }} />
      ) : null}
      {docsOpen ? <DocsDialog onClose={() => setDocsOpen(false)} onGuide={() => { setDocsOpen(false); setGuideOpen(true) }} /> : null}
      {memberDialog ? (
        <MemberDialog mode={memberDialog.mode} reason={memberDialog.reason} oauth={member?.oauth || []}
          onDone={() => window.location.reload()} onClose={() => setMemberDialog(null)} />
      ) : null}
      <AccountsDrawer open={(!publicDemo || Boolean(member?.user)) && accountsOpen != null} focus={accountsOpen || null}
        mine={publicDemo} onClose={() => setAccountsOpen(null)} />

      <HistoryDrawer
        open={historyOpen}
        sessions={sessions}
        error={sessionsError}
        currentId={video?.jobId}
        onOpen={openSession}
        onDelete={removeSession}
        onClose={() => setHistoryOpen(false)}
      />

      {stage === 'chat' && !(mobile && meta?.kind !== 'images') ? ( // phones: the 画面 tab in the workbench instead
        <TimelineSculpture
          frames={frames}
          extras={extraFrames.filter((g) => !hiddenExtras.has(g.id))}
          onClearExtras={(kind) => setHiddenExtras((hidden) => new Set([...hidden, ...extraFrames.filter((g) => g.kind === kind).map((g) => g.id)]))}
          cuts={cuts}
          cited={cited}
          chapters={chaptersData?.status === 'done' ? chaptersData.chapters : []}
          activeChapter={hoverChapter ?? activeChapter}
          busy={chatBusy}
          pictures={meta?.kind === 'images'}
          onRange={meta?.kind === 'images' ? null : onRangeAction}
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
          onPick={meta?.kind === 'images' ? null : () => setPickerOpen(true)}
        />
      ) : null}
      <ClickSpark />
    </div>
  )
}
