import React, { useMemo, useRef, useState } from 'react'
import { fmtClock } from '../lib/format'

// 抄作业 (backend modules/recipe.py): a node tutorial's finished graph drawn the way node editors
// draw it — boxes with a title bar, output sockets on the right, inputs on the left, the settings
// that were changed, curves between sockets — then every setting in a table, other versions'
// differences, what to look at again (a time seeks the video) and tips. It copies as text and
// saves as a picture.
const W = 210
const HEAD = 26
const ROW = 19
const GAP_X = 90
const GAP_Y = 26
const PAD = 24
const TREE_COLORS = ['#3F8F7B', '#8A5A3C', '#5F6FA8', '#7A6A2E']

function layout(tree) {
  const byId = Object.fromEntries(tree.nodes.map((n) => [n.id, n]))
  const ins = {}
  const outs = {}
  for (const l of tree.links) {
    ;(outs[l.from] ||= []).includes(l.out) || outs[l.from].push(l.out)
    ;(ins[l.to] ||= []).includes(l.in) || ins[l.to].push(l.in)
  }
  // Column: the longest chain of links leading into the node (cycles are cut at the first repeat).
  const depth = {}
  const visit = (id, seen = new Set()) => {
    if (depth[id] != null) return depth[id]
    if (seen.has(id)) return 0
    seen.add(id)
    const from = tree.links.filter((l) => l.to === id).map((l) => l.from)
    depth[id] = from.length ? Math.max(...from.map((f) => visit(f, seen) + 1)) : 0
    return depth[id]
  }
  tree.nodes.forEach((n) => visit(n.id))
  const columns = []
  tree.nodes.forEach((n) => { (columns[depth[n.id]] ||= []).push(n) })
  const boxes = {}
  let height = 0
  columns.forEach((col, c) => {
    let y = PAD
    for (const n of col || []) {
      const o = outs[n.id] || []
      const i = ins[n.id] || []
      const h = HEAD + (o.length + i.length + n.params.length) * ROW + 10
      boxes[n.id] = { node: n, x: PAD + c * (W + GAP_X), y, h, outs: o, ins: i }
      y += h + GAP_Y
    }
    height = Math.max(height, y)
  })
  const width = PAD * 2 + columns.length * W + (columns.length - 1) * GAP_X
  const socket = (id, name, side) => {
    const b = boxes[id]
    const k = side === 'out' ? b.outs.indexOf(name) : b.outs.length + b.ins.indexOf(name)
    return { x: side === 'out' ? b.x + W : b.x, y: b.y + HEAD + k * ROW + ROW / 2 + 4 }
  }
  const curves = tree.links.filter((l) => byId[l.from] && byId[l.to]).map((l) => ({ ...l, a: socket(l.from, l.out, 'out'), b: socket(l.to, l.in, 'in') }))
  return { boxes: Object.values(boxes), curves, width: Math.max(width, 320), height: height + PAD - GAP_Y }
}

function Graph({ tree, color, svgRef }) {
  const g = useMemo(() => layout(tree), [tree])
  return (
    <div className="recipe-graph">
      <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" width={g.width} height={g.height} viewBox={`0 0 ${g.width} ${g.height}`}
        role="img" aria-label={`${tree.name}：${tree.nodes.length} 个节点`} fontFamily="-apple-system, PingFang SC, Microsoft YaHei, sans-serif">
        <rect width={g.width} height={g.height} fill="#232323" />
        {g.curves.map((c, i) => {
          const dx = Math.max(40, (c.b.x - c.a.x) / 2)
          return <path key={i} d={`M${c.a.x},${c.a.y} C${c.a.x + dx},${c.a.y} ${c.b.x - dx},${c.b.y} ${c.b.x},${c.b.y}`} fill="none" stroke="#B9B9B9" strokeWidth="1.6" opacity="0.85" />
        })}
        {g.boxes.map((b) => (
          <g key={b.node.id} transform={`translate(${b.x},${b.y})`}>
            <rect width={W} height={b.h} rx="6" fill="#303030" stroke="#141414" />
            <path d={`M0,6 a6,6 0 0 1 6,-6 h${W - 12} a6,6 0 0 1 6,6 v${HEAD - 6} h-${W} z`} fill={color} />
            <text x="9" y="17" fontSize="12.5" fontWeight="600" fill="#F2F2F2">{b.node.name.length > 14 ? `${b.node.name.slice(0, 13)}…` : b.node.name}</text>
            {b.node.en && b.node.name.length * 13 + b.node.en.length * 6 < W - 24  // both fit on the title bar
              ? <text x={W - 8} y="17" fontSize="10" fill="#E6E6E6" opacity="0.75" textAnchor="end">{b.node.en}</text> : null}
            {b.outs.map((o, k) => (
              <g key={`o${o}`}>
                <text x={W - 12} y={HEAD + k * ROW + 14} fontSize="11" fill="#D8D8D8" textAnchor="end">{o}</text>
                <circle cx={W} cy={HEAD + k * ROW + ROW / 2 + 4} r="4.5" fill="#C8F04A" stroke="#141414" />
              </g>
            ))}
            {b.ins.map((n, k) => (
              <g key={`i${n}`}>
                <circle cx="0" cy={HEAD + (b.outs.length + k) * ROW + ROW / 2 + 4} r="4.5" fill="#7FA7E8" stroke="#141414" />
                <text x="12" y={HEAD + (b.outs.length + k) * ROW + 14} fontSize="11" fill="#D8D8D8">{n}</text>
              </g>
            ))}
            {b.node.params.map((p, k) => {
              const y = HEAD + (b.outs.length + b.ins.length + k) * ROW + 2
              return (
                <g key={`p${p.name}`}>
                  <rect x="8" y={y} width={W - 16} height={ROW - 3} rx="3" fill="#545454" />
                  <text x="14" y={y + 12} fontSize="10.5" fill="#E8E8E8">{p.name}</text>
                  <text x={W - 14} y={y + 12} fontSize="10.5" fill="#FFFFFF" textAnchor="end">{p.value.slice(0, 16)}</text>
                </g>
              )
            })}
          </g>
        ))}
      </svg>
    </div>
  )
}

function asText(r) {
  const lines = [`抄作业：${r.goal}${r.software ? `（${r.software}${r.version ? ` ${r.version}` : ''}）` : ''}`]
  for (const t of r.trees) {
    const names = Object.fromEntries(t.nodes.map((n) => [n.id, n.name]))
    lines.push('', `【${t.name}】`)
    for (const n of t.nodes) {
      lines.push(`- ${n.name}${n.en ? `（${n.en}）` : ''}${n.params.length ? '：' + n.params.map((p) => `${p.name}=${p.value}`).join('，') : ''}`)
    }
    lines.push('连线：')
    for (const l of t.links) lines.push(`  ${names[l.from]}.${l.out} → ${names[l.to]}.${l.in}`)
  }
  if (r.version_notes.length) lines.push('', '版本差异：', ...r.version_notes.map((v) => `- （${v.source}）${v.text}`))
  if (r.unsure.length) lines.push('', '需要回看确认：', ...r.unsure.map((u) => `- ${u.text}（${fmtClock(u.time || 0)}）`))
  return lines.join('\n')
}

async function savePicture(svg, name) {
  const data = new XMLSerializer().serializeToString(svg)
  const img = new Image()
  img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(data)}`
  await img.decode()
  const scale = 2
  const canvas = document.createElement('canvas')
  canvas.width = svg.width.baseVal.value * scale
  canvas.height = svg.height.baseVal.value * scale
  const ctx = canvas.getContext('2d')
  ctx.scale(scale, scale)
  ctx.drawImage(img, 0, 0)
  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = `${name}.png`
  a.click()
}

export default function RecipeReport({ report, onSeek = null }) {
  const [tab, setTab] = useState(0)
  const [copied, setCopied] = useState(false)
  const svgRef = useRef(null)
  const trees = report.trees || []
  const tree = trees[Math.min(tab, trees.length - 1)]
  if (!tree) return null
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asText(report))
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }
  const at = (t) => (t != null && onSeek ? <button type="button" className="link-btn mono-sm" onClick={() => onSeek(t)}>{fmtClock(t)}</button> : null)
  return (
    <div className="recipe">
      <p className="recipe__goal"><strong>{report.goal}</strong>{report.software ? <span className="muted"> · {report.software}{report.version ? ` ${report.version}` : ''}</span> : null}</p>
      {trees.length > 1 ? (
        <div className="recipe__tabs" role="tablist" aria-label="节点树">
          {trees.map((t, i) => (
            <button key={t.name + i} type="button" role="tab" aria-selected={i === tab} onClick={() => setTab(i)}>
              {t.name}<span className="mono-sm muted"> {t.nodes.length}</span>
            </button>
          ))}
        </div>
      ) : null}
      <Graph tree={tree} color={TREE_COLORS[tab % TREE_COLORS.length]} svgRef={svgRef} />
      <div className="recipe__actions">
        <button type="button" className="btn btn--ghost btn--sm" onClick={copy}>{copied ? '已复制' : '复制为文字'}</button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => svgRef.current && savePicture(svgRef.current, `抄作业-${tree.name}`)}>存为图片</button>
      </div>
      <details className="recipe__table">
        <summary>参数表（{tree.nodes.reduce((n, x) => n + x.params.length, 0)} 项）</summary>
        <table>
          <thead><tr><th>节点</th><th>参数</th><th>值</th><th>出处</th></tr></thead>
          <tbody>
            {tree.nodes.flatMap((n) => (n.params.length ? n.params : [{ name: '—', value: '默认', time: n.time }]).map((p, k) => (
              <tr key={`${n.id}-${k}`}><td>{k ? '' : n.name}</td><td>{p.name}</td><td>{p.value}</td><td>{at(p.time ?? n.time)}</td></tr>
            )))}
          </tbody>
        </table>
      </details>
      {report.version_notes?.length ? (
        <section className="recipe__notes">
          <h4>不同版本</h4>
          <ul>{report.version_notes.map((v, i) => <li key={i}><span className="mono-sm muted">{v.source}</span> {v.text}</li>)}</ul>
        </section>
      ) : null}
      {report.unsure?.length ? (
        <section className="recipe__notes">
          <h4>看不清，建议回看</h4>
          <ul>{report.unsure.map((u, i) => <li key={i}>{u.text} {at(u.time)}</li>)}</ul>
        </section>
      ) : null}
      {report.tips?.length ? (
        <section className="recipe__notes">
          <h4>照着连容易错的地方</h4>
          <ul>{report.tips.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </section>
      ) : null}
    </div>
  )
}
