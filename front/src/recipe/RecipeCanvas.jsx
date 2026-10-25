import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { renderMarkdown } from '../lib/markdown'
import { applyRecipe, blenderAddonUrl, blenderStatus, checkRecipe, fetchRecipeScript, getRecipe, recipeScriptUrl, reviseRecipe, saveRecipeLayout, undoRecipe } from '../api/client'
import { fmtClock } from '../lib/format'
import { HEAD, PAD, ROW, W, asText, autoLayout, bounds, card, headerColor, rowY, socketColor, socketPoint } from './graph'
import './recipe.css'

const MIN_ZOOM = 0.2
const MAX_ZOOM = 2.5
const SAVE_DELAY = 700
const clamp = (v, a, b) => Math.min(b, Math.max(a, v))
const localKey = (jobId) => `recipe.layout.${jobId}`
const short = (s, n) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || '')

function NodeCard({ c, x, y, onGrab, missing = false }) {
  const { node, rows, h } = c
  return (
    <g transform={`translate(${x},${y})`} className="rc-node">
      <rect width={W} height={h} rx="7" fill="#303030" stroke={missing ? '#FF5A4E' : node.ref ? '#151515' : '#B4531F'}
        strokeWidth={missing ? 3 : 1} strokeDasharray={missing || !node.ref ? '5 4' : ''} />
      <g onPointerDown={onGrab} style={{ cursor: 'grab' }}>
        <path d={`M0,7 a7,7 0 0 1 7,-7 h${W - 14} a7,7 0 0 1 7,7 v${HEAD - 7} h-${W} z`} fill={headerColor(node)} />
        <text x="10" y="19" fontSize="13" fontWeight="600" fill="#F4F4F4">{short(node.title || node.name, 15)}</text>
        {node.legacy ? <text x={W - 9} y="19" fontSize="10" fill="#FFD27A" textAnchor="end">{node.legacy} 旧节点</text>
          : node.en && node.name.length < 11 ? <text x={W - 9} y="19" fontSize="10" fill="#EDEDED" opacity="0.7" textAnchor="end">{short(node.en, 18)}</text> : null}
        <title>{`${node.title ? `${node.title}（${node.name}）` : node.name}${node.en ? `（${node.en}）` : ''}${node.ref ? '' : '：不在 Blender 节点目录里，按视频里的叫法画出'}${node.legacy ? `：Blender ${node.legacy} 的旧节点，新版本用 ${node.replaced_by}` : ''}${node.time != null ? ` · 视频 ${fmtClock(node.time)}` : ''}`}</title>
      </g>
      {rows.map((r, i) => {
        const cy = rowY(i)
        if (r.kind === 'opt') {
          return (
            <g key={`o${i}`}>
              <rect x={PAD} y={cy - ROW / 2 + 2} width={W - PAD * 2} height={ROW - 4} rx="4" fill="#3E3E3E" stroke="#C8F04A" strokeOpacity="0.55" />
              <text x={PAD + 7} y={cy + 4} fontSize="11" fill="#CFCFCF">{short(r.name, 10)}</text>
              <text x={W - PAD - 7} y={cy + 4} fontSize="11" fill="#FFFFFF" textAnchor="end">{short(String(r.value), 14)}</text>
            </g>
          )
        }
        if (r.kind === 'axis') {
          return (
            <g key={`ax${i}`}>
              <rect x={PAD + 14} y={cy - ROW / 2 + 2} width={W - PAD * 2 - 14} height={ROW - 4} rx="3" fill={r.changed ? '#4D5A2A' : '#545454'} />
              <text x={PAD + 22} y={cy + 4} fontSize="11" fill="#E6E6E6">{r.name}</text>
              <text x={W - PAD - 7} y={cy + 4} fontSize="11" fill={r.changed ? '#E7FF9E' : '#FFFFFF'} textAnchor="end">{short(String(r.value), 14)}</text>
            </g>
          )
        }
        if (r.kind === 'out') {
          return (
            <g key={`out${i}`}>
              <text x={W - 14} y={cy + 4} fontSize="11.5" fill="#DCDCDC" textAnchor="end">{short(r.name, 22)}</text>
              <circle cx={W} cy={cy} r="5" fill={socketColor(r.type)} stroke="#151515" strokeWidth="1.2" />
            </g>
          )
        }
        const field = !r.linked && r.value !== '' && r.value !== undefined
        const doubt = String(r.value ?? '').includes('待确认') // the tutorial changed it but the value couldn't be read
        return (
          <g key={`in${i}`}>
            <circle cx="0" cy={cy} r="5" fill={socketColor(r.type)} stroke="#151515" strokeWidth="1.2" />
            {field ? (
              <>
                <rect x={PAD + 4} y={cy - ROW / 2 + 2} width={W - PAD * 2 - 4} height={ROW - 4} rx="4" fill={doubt ? '#5A3E1F' : r.changed ? '#4D5A2A' : '#545454'} />
                <text x={PAD + 11} y={cy + 4} fontSize="11" fill="#E6E6E6">{short(r.name, 12)}</text>
                <text x={W - PAD - 7} y={cy + 4} fontSize="11" fill={doubt ? '#FFB454' : r.changed ? '#E7FF9E' : '#FFFFFF'} textAnchor="end">{short(String(r.value), 16)}</text>
              </>
            ) : <text x="14" y={cy + 4} fontSize="11.5" fill="#DCDCDC">{short(r.name, 24)}</text>}
          </g>
        )
      })}
    </g>
  )
}

// #/recipe/<jobId>: the 抄作业 graph on its own page, one node tree at a time. Drag the background to
// move around, ⌘/Ctrl + scroll or the buttons to zoom, drag a node by its title to move it; positions
// save by themselves (a sample's stay in this browser). It copies as text and saves as a picture.
export default function RecipeCanvas({ jobId }) {
  const [state, setState] = useState({ loading: true, error: '', recipe: null })
  const [tab, setTab] = useState(0)
  const [layout, setLayout] = useState({}) // tree index → node id → [x, y]
  const [view, setView] = useState({ x: 40, y: 80, k: 0.9 })
  const [saveState, setSaveState] = useState('saved')
  const [copied, setCopied] = useState(false)
  const [scripted, setScripted] = useState('') // '' | 'copied' | 'failed'
  const [panel, setPanel] = useState(true)
  const [bridge, setBridge] = useState(null) // /api/blender/status: the person's own Blender (local app only)
  const [checked, setChecked] = useState(null) // 对答案 result for the shown tree: { tab, done, summary, findings }
  const [blenderBusy, setBlenderBusy] = useState('')
  const [blenderNote, setBlenderNote] = useState('')
  const [connectHelp, setConnectHelp] = useState(false)
  const [revising, setRevising] = useState(false) // the AI 修改 section is open
  const [instruction, setInstruction] = useState('')
  const [revision, setRevision] = useState(null) // { tab, summary, changes, problems, checks, preview } or { tab, busy } / { tab, error }
  const svgRef = useRef(null)
  const drag = useRef(null)
  const timer = useRef(0)

  const load = useCallback(() => getRecipe(jobId).then((r) => {
    setState((s) => ({ ...s, recipe: { ...s.recipe, ...r } }))
  }), [jobId])

  useEffect(() => {
    getRecipe(jobId).then((r) => {
      if (r.status !== 'done') {
        setState({ loading: false, error: r.message || '还没有抄作业', recipe: null })
        return
      }
      let saved = r.layout || {}
      if (!r.editable) {
        try {
          saved = JSON.parse(localStorage.getItem(localKey(jobId)) || 'null') || saved
        } catch {
          // a private window: the default layout
        }
      }
      setLayout(saved)
      setState({ loading: false, error: '', recipe: r })
      document.title = `抄作业 · ${r.title || ''}`
    }).catch((err) => setState({ loading: false, error: err.message, recipe: null }))
  }, [jobId])

  const refreshBridge = useCallback(() => { blenderStatus().then(setBridge).catch(() => setBridge(null)) }, [])
  useEffect(() => {
    refreshBridge()
    window.addEventListener('focus', refreshBridge) // came back from Blender: it may be connected now
    return () => window.removeEventListener('focus', refreshBridge)
  }, [refreshBridge])
  const recipe = state.recipe
  const tree = recipe?.trees[Math.min(tab, recipe.trees.length - 1)]
  const cards = useMemo(() => (tree ? Object.fromEntries(tree.nodes.map((n) => [n.id, card(n, tree.links)])) : {}), [tree])
  const pos = useMemo(() => {
    if (!tree) return {}
    const auto = autoLayout(tree, cards)
    return { ...auto, ...(layout[tab] || {}) }
  }, [tree, cards, layout, tab])

  const persist = useCallback((next) => {
    clearTimeout(timer.current)
    setSaveState('pending')
    timer.current = setTimeout(async () => {
      if (!recipe?.editable) {
        try {
          localStorage.setItem(localKey(jobId), JSON.stringify(next))
          setSaveState('local')
        } catch {
          setSaveState('error')
        }
        return
      }
      setSaveState('saving')
      try {
        await saveRecipeLayout(jobId, next)
        setSaveState('saved')
      } catch {
        setSaveState('error')
      }
    }, SAVE_DELAY)
  }, [jobId, recipe?.editable])

  const fit = useCallback(() => {
    const svg = svgRef.current
    if (!svg) return
    const b = bounds(cards, pos)
    const { width, height } = svg.getBoundingClientRect()
    const k = clamp(Math.min(width / b.w, height / b.h), MIN_ZOOM, 1.2)
    setView({ k, x: (width - b.w * k) / 2 - b.x * k, y: (height - b.h * k) / 2 - b.y * k })
  }, [cards, pos])
  useEffect(() => { if (tree) requestAnimationFrame(fit) }, [tab, tree]) // eslint-disable-line react-hooks/exhaustive-deps

  const toWorld = (e) => {
    const r = svgRef.current.getBoundingClientRect()
    return [(e.clientX - r.left - view.x) / view.k, (e.clientY - r.top - view.y) / view.k]
  }
  const onDown = (e) => {
    if (e.button !== 0) return
    drag.current = { kind: 'pan', sx: e.clientX, sy: e.clientY, ox: view.x, oy: view.y }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const grabNode = (id) => (e) => {
    e.stopPropagation()
    const [wx, wy] = toWorld(e)
    drag.current = { kind: 'node', id, dx: wx - pos[id][0], dy: wy - pos[id][1] }
    svgRef.current.setPointerCapture(e.pointerId)
  }
  const onMove = (e) => {
    const d = drag.current
    if (!d) return
    if (d.kind === 'pan') setView((v) => ({ ...v, x: d.ox + e.clientX - d.sx, y: d.oy + e.clientY - d.sy }))
    else {
      const [wx, wy] = toWorld(e)
      setLayout((l) => ({ ...l, [tab]: { ...pos, ...(l[tab] || {}), [d.id]: [Math.round(wx - d.dx), Math.round(wy - d.dy)] } }))
      d.moved = true
    }
  }
  const onUp = () => {
    if (drag.current?.kind === 'node' && drag.current.moved) setLayout((l) => { persist(l); return l })
    drag.current = null
  }
  const onWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      const r = svgRef.current.getBoundingClientRect()
      const px = e.clientX - r.left
      const py = e.clientY - r.top
      setView((v) => {
        const k = clamp(v.k * Math.exp(-e.deltaY * 0.0015), MIN_ZOOM, MAX_ZOOM)
        return { k, x: px - ((px - v.x) * k) / v.k, y: py - ((py - v.y) * k) / v.k }
      })
    } else setView((v) => ({ ...v, x: v.x - e.deltaX, y: v.y - e.deltaY }))
  }
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return undefined
    const stop = (e) => e.preventDefault()
    svg.addEventListener('wheel', stop, { passive: false })
    return () => svg.removeEventListener('wheel', stop)
  }, [recipe])
  const zoom = (f) => setView((v) => {
    const r = svgRef.current.getBoundingClientRect()
    const k = clamp(v.k * f, MIN_ZOOM, MAX_ZOOM)
    return { k, x: r.width / 2 - ((r.width / 2 - v.x) * k) / v.k, y: r.height / 2 - ((r.height / 2 - v.y) * k) / v.k }
  })
  const relayout = () => {
    setLayout((l) => {
      const next = { ...l, [tab]: autoLayout(tree, cards) }
      persist(next)
      return next
    })
    requestAnimationFrame(fit)
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asText(recipe))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }
  const copyScript = async () => {
    try {
      await navigator.clipboard.writeText(await fetchRecipeScript(jobId))
      setScripted('copied')
    } catch {
      setScripted('failed')
    }
    setTimeout(() => setScripted(''), 2400)
  }
  const toBlender = async () => {
    setBlenderBusy('apply')
    setBlenderNote('')
    try {
      await applyRecipe(jobId, tab)
      setBlenderNote(`已在 Blender 里建好「${tree.name}」：去 Blender 看看，再点「对答案」核对`)
    } catch (err) {
      setBlenderNote(err.message)
    } finally {
      setBlenderBusy('')
      refreshBridge()
    }
  }
  const checkAnswer = async () => {
    setBlenderBusy('check')
    setBlenderNote('')
    try {
      setChecked({ tab, ...(await checkRecipe(jobId, tab)) })
      setPanel(true)
    } catch (err) {
      setBlenderNote(err.message)
    } finally {
      setBlenderBusy('')
      refreshBridge()
    }
  }
  const revise = async (text) => {
    setRevision({ tab, busy: true })
    setPanel(true)
    try {
      const r = await reviseRecipe(jobId, tab, text)
      setState((s) => ({ ...s, recipe: { ...s.recipe, ...r.recipe } }))
      setChecked(null) // the graph changed: an old 对答案 no longer applies
      setRevision({ tab, ...r })
    } catch (err) {
      setRevision({ tab, error: err.message })
    } finally {
      refreshBridge()
    }
  }
  const undoRevision = async () => {
    try {
      await undoRecipe(jobId)
      await load()
      setRevision(null)
      setChecked(null)
    } catch (err) {
      setRevision((r) => ({ ...r, error: err.message }))
    }
  }
  const savePicture = async () => {
    const b = bounds(cards, pos)
    const clone = svgRef.current.cloneNode(true)
    clone.setAttribute('viewBox', `${b.x} ${b.y} ${b.w} ${b.h}`)
    clone.setAttribute('width', b.w)
    clone.setAttribute('height', b.h)
    clone.querySelector('.rc-world').setAttribute('transform', '')
    clone.querySelector('.rc-bg').setAttribute('x', b.x)
    clone.querySelector('.rc-bg').setAttribute('y', b.y)
    const img = new Image()
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(clone))}`
    await img.decode()
    const canvas = document.createElement('canvas')
    canvas.width = b.w * 2
    canvas.height = b.h * 2
    const ctx = canvas.getContext('2d')
    ctx.scale(2, 2)
    ctx.drawImage(img, 0, 0)
    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = `抄作业-${tree.name}.png`
    a.click()
  }

  if (state.loading) return <div className="rc-empty">正在读取节点图…</div>
  if (!recipe) return <div className="rc-empty">{state.error}<a href={window.location.pathname}>回到帧寻</a></div>
  const result = checked && checked.tab === tab ? checked : null
  const missingNodes = new Set((result?.findings || []).filter((f) => f.kind === 'missing_node').map((f) => f.node))
  const missingLinks = new Set((result?.findings || []).filter((f) => f.kind === 'missing_link').map((f) => `${f.from}>${f.to}`))
  const curves = tree.links.map((l, i) => {
    const a = socketPoint(cards, pos, l.from, l.out, 'out')
    const b = socketPoint(cards, pos, l.to, l.in, 'in')
    if (!a || !b) return null
    const dx = Math.max(50, Math.abs(b.x - a.x) / 2)
    const absent = missingLinks.has(`${l.from}>${l.to}`) // 对答案: this one isn't in their Blender
    return (
      <path key={i} d={`M${a.x},${a.y} C${a.x + dx},${a.y} ${b.x - dx},${b.y} ${b.x},${b.y}`} fill="none" stroke={absent ? '#FF5A4E' : socketColor(a.type)}
        strokeWidth={absent ? 3.2 : 2.2} opacity={l.inferred ? 0.75 : 0.95} strokeDasharray={absent ? '4 5' : l.inferred ? '7 6' : ''} className={absent ? 'rc-absent' : undefined}>
        {l.inferred ? <title>{`推断的连线：${l.why || '视频里没有直接看到'}`}</title> : null}
      </path>
    )
  })
  const unmatched = tree.nodes.filter((n) => !n.ref).length
  const inferred = tree.links.filter((l) => l.inferred).length
  return (
    <div className="rc">
      <header className="rc-bar">
        <a className="rc-back" href={window.location.pathname} title="回到帧寻">帧寻</a>
        <div className="rc-title">
          <strong>抄作业</strong>
          <span>{recipe.title}</span>
        </div>
        <nav className="rc-tabs" role="tablist" aria-label="节点树">
          {recipe.trees.map((t, i) => (
            <button key={t.name + i} type="button" role="tab" aria-selected={i === tab} onClick={() => setTab(i)}>
              {t.name}<span>{t.nodes.length}</span>
            </button>
          ))}
        </nav>
        <div className="rc-actions">
          <button type="button" onClick={() => zoom(1 / 1.2)} aria-label="缩小">−</button>
          <span className="rc-zoom">{Math.round(view.k * 100)}%</span>
          <button type="button" onClick={() => zoom(1.2)} aria-label="放大">＋</button>
          <button type="button" onClick={fit}>适应窗口</button>
          <button type="button" onClick={relayout}>自动排列</button>
          {bridge?.available ? (bridge.connected ? (
            <>
              <button type="button" className="rc-script" onClick={toBlender} disabled={Boolean(blenderBusy)} title={`当前物体：${bridge.object || '无'}（Blender ${bridge.blender}）`}>
                {blenderBusy === 'apply' ? '正在建…' : '应用到 Blender'}
              </button>
              <button type="button" className="rc-check" onClick={checkAnswer} disabled={Boolean(blenderBusy)}>{blenderBusy === 'check' ? '核对中…' : '对答案'}</button>
            </>
          ) : <button type="button" onClick={() => { setConnectHelp(true); setPanel(true) }}>连接 Blender</button>) : null}
          {recipe.editable ? (
            <button type="button" className="rc-ai" onClick={() => { setRevising(true); setPanel(true) }} aria-expanded={revising && panel}>AI 修改</button>
          ) : null}
          <button type="button" className="rc-script" onClick={copyScript} title="粘贴到 Blender → Scripting 运行，节点自动建好">
            {scripted === 'copied' ? '脚本已复制' : scripted === 'failed' ? '复制失败，用下载' : '复制 Blender 脚本'}
          </button>
          <a className="rc-link" href={recipeScriptUrl(jobId)} download={`抄作业-${jobId}.py`}>下载 .py</a>
          <button type="button" onClick={copy}>{copied ? '已复制' : '复制为文字'}</button>
          <button type="button" onClick={savePicture}>存为图片</button>
          <button type="button" onClick={() => setPanel((p) => !p)} aria-expanded={panel}>说明</button>
          <span className="rc-save">{{ saved: '位置已保存', pending: '…', saving: '保存中', local: '位置存在本机', error: '保存失败' }[saveState]}</span>
        </div>
      </header>
      <svg ref={svgRef} className="rc-canvas" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onWheel={onWheel}
        role="img" aria-label={`${tree.name}：${tree.nodes.length} 个节点、${tree.links.length} 条连线`}
        fontFamily="-apple-system, PingFang SC, Microsoft YaHei, sans-serif" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="rc-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#2E2E2E" /></pattern>
        </defs>
        <rect className="rc-bg" x="-100000" y="-100000" width="200000" height="200000" fill="#1D1D1D" />
        <g className="rc-world" transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
          <rect x="-100000" y="-100000" width="200000" height="200000" fill="url(#rc-grid)" />
          {curves}
          {tree.nodes.map((n) => <NodeCard key={n.id} c={cards[n.id]} x={pos[n.id][0]} y={pos[n.id][1]} onGrab={grabNode(n.id)} missing={missingNodes.has(n.id)} />)}
        </g>
      </svg>
      {panel ? (
        <aside className="rc-panel">
          {blenderNote ? <p className="rc-warn">{blenderNote}</p> : null}
          {revising || (revision && revision.tab === tab) ? (
            <section className="rc-revise" aria-label="AI 修改">
              <h4>AI 修改 · {tree.name}</h4>
              <p className="rc-hint">{bridge?.connected
                ? '会对照视频画面修改节点图，每改一版就在你的 Blender 里试建一次、看渲染效果，再接着改。'
                : '会对照视频画面修改节点图。连上 Blender 后还能每改一版就试建一次、看效果。'}</p>
              <div className="rc-quick">
                {['补全没连上的节点和线', '对照视频再检查一遍'].map((q) => (
                  <button key={q} type="button" onClick={() => revise(q)} disabled={Boolean(revision?.busy)}>{q}</button>
                ))}
              </div>
              <form onSubmit={(e) => { e.preventDefault(); if (instruction.trim()) revise(instruction.trim()) }}>
                <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} rows={2} maxLength={500}
                  placeholder="想怎么改，比如：等高线没出来，检查吸附和删除面那一段" aria-label="修改要求" />
                <button type="submit" disabled={Boolean(revision?.busy) || !instruction.trim()}>让 AI 改</button>
              </form>
              {revision && revision.tab === tab ? (
                revision.busy ? <p className="rc-busy" role="status">AI 正在修改：看画面、改图{bridge?.connected ? '、在 Blender 里试建' : ''}，大约 1–3 分钟…</p>
                  : revision.error ? <p className="rc-warn">{revision.error}</p> : (
                    <div className="rc-revised">
                      <div className="rc-summary">{renderMarkdown(revision.summary)}</div>
                      {revision.preview ? <img src={`data:image/png;base64,${revision.preview}`} alt="Blender 按改后的节点图做出的效果" /> : null}
                      {revision.checks?.length ? <pre className="rc-blender">{revision.checks[revision.checks.length - 1]}</pre> : null}
                      {revision.problems?.length ? (
                        <><h4>还有的问题</h4><ul>{revision.problems.map((p, i) => <li key={i}>{p}</li>)}</ul></>
                      ) : null}
                      {revision.changes?.length ? (
                        <details><summary>改了 {revision.changes.length} 处</summary><ul>{revision.changes.map((c, i) => <li key={i}>{c}</li>)}</ul></details>
                      ) : null}
                      <div className="rc-quick">
                        <button type="button" onClick={undoRevision}>撤销这次修改</button>
                        {bridge?.connected ? <button type="button" onClick={checkAnswer} disabled={Boolean(blenderBusy)}>对答案</button> : null}
                      </div>
                    </div>
                  )
              ) : null}
            </section>
          ) : null}
          {result ? (
            <section className="rc-result" data-done={result.done || undefined}>
              <h4>对答案 · {result.summary}</h4>
              <p className="rc-hint">核对的是 Blender 里「{result.theirs}」，对上 {result.matched}/{result.nodes} 个节点。{result.done ? '和教程一致，可以看效果了。' : '红色虚线是你那边还缺的，改完再点一次「对答案」。'}</p>
              {result.findings.length ? <ul>{result.findings.map((f, i) => <li key={i} data-kind={f.kind}>{f.text}{f.time != null ? <em> {fmtClock(f.time)}</em> : null}</li>)}</ul> : null}
            </section>
          ) : null}
          {connectHelp && bridge?.available && !bridge.connected ? (
            <section>
              <h4>连接你的 Blender</h4>
              <ol className="rc-steps">
                <li><a className="rc-link" href={blenderAddonUrl()} download="zhenxun_bridge.py">下载「帧寻 Bridge」插件</a></li>
                <li>Blender → 编辑 → 偏好设置 → 插件 → 右上角下拉「从磁盘安装」→ 选这个文件</li>
                <li>勾选启用「帧寻 Bridge」，侧栏（N）› 帧寻 显示「已连接」</li>
                <li>回到这里，按钮会变成「应用到 Blender」「对答案」</li>
              </ol>
              <p className="rc-hint">插件只在本机 127.0.0.1 上通信，不联网。{bridge.message ? ` 现在：${bridge.message}` : ''}</p>
            </section>
          ) : null}
          {recipe.goal ? <p className="rc-goal">{recipe.goal}{recipe.software ? <small>{recipe.software} {recipe.version}</small> : null}</p> : null}
          <p className="rc-hint">拖背景移动，⌘/Ctrl + 滚轮缩放，拖节点标题调整位置。绿色底的是教程改过的参数，橙色的「待确认」是改过但没看清的值，其余是 Blender 默认值。
            {unmatched ? ` 虚线框的 ${unmatched} 个节点不在 Blender ${recipe.catalog || ''} 节点目录里，按视频里的叫法画出。` : ''}
            {inferred ? ` ${inferred} 条虚线是视频里没直接看到、按常规用法推断的连线，鼠标停在线上看理由，照着连之前请核对。` : ''}</p>
          {recipe.source_height && recipe.source_height < 720 ? (
            <p className="rc-warn">这次只读到 {recipe.source_height}p 的画面，节点上的小字可能认错。登录 B 站（账号 → 扫码）或上传原视频后重新抄作业会更准。</p>
          ) : null}
          <section>
            <h4>导入 Blender</h4>
            <p className="rc-hint">点「复制 Blender 脚本」，在 Blender 里 Scripting → 新建 → 粘贴 → 运行脚本，节点会建在当前选中物体的几何节点修改器上（材质建成新材质）。
              适用于 4.x / 5.0；脚本里「# 手动」开头的是需要照视频手动补的地方。</p>
          </section>
          {recipe.plugins?.length ? (
            <section><h4>需要的插件</h4><ul>{recipe.plugins.map((p) => (
              <li key={p.term}><em>{p.plugin}</em>{p.term !== p.plugin ? `「${p.term}」来自它。` : ''}{p.provides}；{p.install}
                <a className="rc-link" href={p.url} target="_blank" rel="noopener noreferrer"> 出处</a></li>))}</ul></section>
          ) : null}
          {recipe.version_notes?.length ? (
            <section><h4>不同版本</h4><ul>{recipe.version_notes.map((v, i) => <li key={i}><em>{v.source}</em>{v.text}</li>)}</ul></section>
          ) : null}
          {recipe.unsure?.length ? (
            <section><h4>看不清，建议回看</h4><ul>{recipe.unsure.map((u, i) => <li key={i}>{u.text}{u.time != null ? <em> {fmtClock(u.time)}</em> : null}</li>)}</ul></section>
          ) : null}
          {recipe.tips?.length ? (
            <section><h4>照着连容易错的地方</h4><ul>{recipe.tips.map((t, i) => <li key={i}>{t}</li>)}</ul></section>
          ) : null}
        </aside>
      ) : null}
    </div>
  )
}
