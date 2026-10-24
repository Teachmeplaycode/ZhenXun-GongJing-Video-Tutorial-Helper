import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getRecipe, saveRecipeLayout } from '../api/client'
import { fmtClock } from '../lib/format'
import { HEAD, PAD, ROW, W, asText, autoLayout, bounds, card, headerColor, rowY, socketColor, socketPoint } from './graph'
import './recipe.css'

const MIN_ZOOM = 0.2
const MAX_ZOOM = 2.5
const SAVE_DELAY = 700
const clamp = (v, a, b) => Math.min(b, Math.max(a, v))
const localKey = (jobId) => `recipe.layout.${jobId}`
const short = (s, n) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || '')

function NodeCard({ c, x, y, onGrab }) {
  const { node, rows, h } = c
  return (
    <g transform={`translate(${x},${y})`} className="rc-node">
      <rect width={W} height={h} rx="7" fill="#303030" stroke={node.ref ? '#151515' : '#B4531F'} strokeDasharray={node.ref ? '' : '5 4'} />
      <g onPointerDown={onGrab} style={{ cursor: 'grab' }}>
        <path d={`M0,7 a7,7 0 0 1 7,-7 h${W - 14} a7,7 0 0 1 7,7 v${HEAD - 7} h-${W} z`} fill={headerColor(node)} />
        <text x="10" y="19" fontSize="13" fontWeight="600" fill="#F4F4F4">{short(node.name, 15)}</text>
        {node.en && node.name.length < 11 ? <text x={W - 9} y="19" fontSize="10" fill="#EDEDED" opacity="0.7" textAnchor="end">{short(node.en, 18)}</text> : null}
        <title>{`${node.name}${node.en ? `（${node.en}）` : ''}${node.ref ? '' : '：不在 Blender 节点目录里，按视频里的叫法画出'}${node.time != null ? ` · 视频 ${fmtClock(node.time)}` : ''}`}</title>
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
  const [panel, setPanel] = useState(true)
  const svgRef = useRef(null)
  const drag = useRef(null)
  const timer = useRef(0)

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
  const curves = tree.links.map((l, i) => {
    const a = socketPoint(cards, pos, l.from, l.out, 'out')
    const b = socketPoint(cards, pos, l.to, l.in, 'in')
    if (!a || !b) return null
    const dx = Math.max(50, Math.abs(b.x - a.x) / 2)
    return (
      <path key={i} d={`M${a.x},${a.y} C${a.x + dx},${a.y} ${b.x - dx},${b.y} ${b.x},${b.y}`} fill="none" stroke={socketColor(a.type)}
        strokeWidth="2.2" opacity={l.inferred ? 0.75 : 0.95} strokeDasharray={l.inferred ? '7 6' : ''}>
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
          {tree.nodes.map((n) => <NodeCard key={n.id} c={cards[n.id]} x={pos[n.id][0]} y={pos[n.id][1]} onGrab={grabNode(n.id)} />)}
        </g>
      </svg>
      {panel ? (
        <aside className="rc-panel">
          {recipe.goal ? <p className="rc-goal">{recipe.goal}{recipe.software ? <small>{recipe.software} {recipe.version}</small> : null}</p> : null}
          <p className="rc-hint">拖背景移动，⌘/Ctrl + 滚轮缩放，拖节点标题调整位置。绿色底的是教程改过的参数，橙色的「待确认」是改过但没看清的值，其余是 Blender 默认值。
            {unmatched ? ` 虚线框的 ${unmatched} 个节点不在 Blender ${recipe.catalog || ''} 节点目录里，按视频里的叫法画出。` : ''}
            {inferred ? ` ${inferred} 条虚线是视频里没直接看到、按常规用法推断的连线，鼠标停在线上看理由，照着连之前请核对。` : ''}</p>
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
