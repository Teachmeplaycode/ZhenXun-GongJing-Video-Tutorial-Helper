import React, { useMemo, useState } from 'react'
import MathText, { MathFormula } from '../components/MathText'
import { apiUrl } from '../api/client'
import { layoutMindmap, outlineToTree, treeToOutline } from './layout'

const clock = (s) => {
  const t = Math.max(0, Math.round(Number(s) || 0))
  const h = Math.floor(t / 3600)
  const mm = String(Math.floor((t % 3600) / 60)).padStart(2, '0')
  const ss = String(t % 60).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}
const lines = (text) => (text || '').split('\n').map((l) => l.trim()).filter(Boolean)
const BRANCH = ['var(--mark-replay)', 'var(--mark-view)', 'var(--mark-cite)', 'var(--mark-chapter)', 'var(--accent-success)', 'var(--accent-processing)']

function Formula({ tex }) {
  return <div className="nb-formula"><MathFormula text={tex} display /></div>
}

export function MindMap({ tree }) {
  const m = useMemo(() => layoutMindmap(tree), [tree])
  const pad = 8
  return (
    <svg className="nb-mindmap" viewBox={`${-pad} ${-pad} ${m.width + pad * 2} ${m.height + pad * 2}`} role="img" aria-label={`思维导图：${tree?.label || ''}`}>
      {m.links.map(({ from, to }, i) => {
        const x1 = from.x + from.w
        const y1 = from.y
        const x2 = to.x
        const y2 = to.y
        const mid = (x1 + x2) / 2
        return <path key={i} d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`} fill="none" stroke={BRANCH[to.branch % BRANCH.length]} strokeWidth={2} opacity={0.7} />
      })}
      {m.nodes.map((n, i) => (
        <g key={i} transform={`translate(${n.x},${n.y - m.nodeH / 2})`}>
          <rect width={n.w} height={m.nodeH} rx={n.depth === 0 ? 8 : 6} className={`nb-mm-node nb-mm-node--d${Math.min(n.depth, 2)}`}
            style={n.depth ? { stroke: BRANCH[n.branch % BRANCH.length] } : undefined} />
          <text x={n.w / 2} y={m.nodeH / 2} dominantBaseline="central" textAnchor="middle" className={`nb-mm-text nb-mm-text--d${Math.min(n.depth, 2)}`}>{n.label}</text>
        </g>
      ))}
    </svg>
  )
}

// Read view of a block.
export function BlockView({ block: b }) {
  if (b.type === 'title') {
    return (
      <div className="nb-title">
        <h1><MathText text={b.text || '笔记'} /></h1>
        {b.summary ? <p><MathText text={b.summary} /></p> : null}
      </div>
    )
  }
  if (b.type === 'section') {
    return (
      <div className="nb-section">
        <header>
          <h2><MathText text={b.title} /></h2>
          {b.start != null ? <span className="mono-sm">{clock(b.start)}–{clock(b.end)}</span> : null}
        </header>
        {b.points?.length ? <ul>{b.points.map((p, i) => <li key={i}><MathText text={p} /></li>)}</ul> : null}
        {b.formulas?.length ? <div className="nb-formulas">{b.formulas.map((f, i) => <Formula key={i} tex={f} />)}</div> : null}
        {b.examples?.length ? (
          <div className="nb-examples">
            <span className="eyebrow">例题</span>
            <ol>{b.examples.map((e, i) => <li key={i}><MathText text={e} /></li>)}</ol>
          </div>
        ) : null}
        {b.keywords?.length ? <div className="nb-keywords">{b.keywords.map((k) => <span key={k}>{k}</span>)}</div> : null}
      </div>
    )
  }
  if (b.type === 'figure') {
    return (
      <figure className="nb-figure">
        <img src={apiUrl(b.src)} alt={b.caption || '画面'} draggable="false" />
        <figcaption><MathText text={b.caption} />{b.time != null ? <span className="mono-sm"> · {clock(b.time)}</span> : null}</figcaption>
      </figure>
    )
  }
  if (b.type === 'mindmap') return <MindMap tree={b.tree} />
  return <div className="nb-text"><MathText text={b.text || ' '} /></div>
}

// Edit form of a block: fields as text, one item per line. onDone(patch) commits, onCancel drops.
export function BlockEdit({ block: b, onDone, onCancel }) {
  const [draft, setDraft] = useState(() => ({
    text: b.text || '', summary: b.summary || '', title: b.title || '', caption: b.caption || '',
    points: (b.points || []).join('\n'), formulas: (b.formulas || []).join('\n'), examples: (b.examples || []).join('\n'),
    outline: b.type === 'mindmap' ? treeToOutline(b.tree) : '',
  }))
  const set = (k) => (e) => setDraft((d) => ({ ...d, [k]: e.target.value }))
  const done = () => {
    if (b.type === 'title') onDone({ text: draft.text.trim(), summary: draft.summary.trim() })
    else if (b.type === 'section') onDone({ title: draft.title.trim(), points: lines(draft.points), formulas: lines(draft.formulas), examples: lines(draft.examples) })
    else if (b.type === 'figure') onDone({ caption: draft.caption.trim() })
    else if (b.type === 'mindmap') onDone({ tree: outlineToTree(draft.outline) })
    else onDone({ text: draft.text })
  }
  const onKeyDown = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); onCancel() }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); done() }
    e.stopPropagation() // typing must not reach the canvas shortcuts
  }
  return (
    <div className="nb-edit" onKeyDown={onKeyDown} onPointerDown={(e) => e.stopPropagation()}>
      {b.type === 'title' ? (
        <>
          <label>标题<input autoFocus value={draft.text} onChange={set('text')} /></label>
          <label>摘要<textarea rows={3} value={draft.summary} onChange={set('summary')} /></label>
        </>
      ) : b.type === 'section' ? (
        <>
          <label>小节标题<input autoFocus value={draft.title} onChange={set('title')} /></label>
          <label>要点（一行一条）<textarea rows={Math.max(3, b.points?.length || 0) + 1} value={draft.points} onChange={set('points')} /></label>
          <label>公式（LaTeX，一行一条）<textarea className="mono-sm" rows={Math.max(2, b.formulas?.length || 0) + 1} value={draft.formulas} onChange={set('formulas')} /></label>
          <label>例题（一行一条）<textarea rows={Math.max(2, b.examples?.length || 0) + 1} value={draft.examples} onChange={set('examples')} /></label>
        </>
      ) : b.type === 'figure' ? (
        <label>图片说明<input autoFocus value={draft.caption} onChange={set('caption')} /></label>
      ) : b.type === 'mindmap' ? (
        <label>思维导图（每行一个节点，缩进两个空格表示下一级）
          <textarea autoFocus className="mono-sm" rows={14} value={draft.outline} onChange={set('outline')} />
        </label>
      ) : (
        <label>文字<textarea autoFocus rows={5} value={draft.text} onChange={set('text')} /></label>
      )}
      <div className="nb-edit__actions">
        <span className="caption muted">⌘/Ctrl + Enter 完成 · Esc 取消</span>
        <button type="button" className="btn btn--ghost" onClick={onCancel}>取消</button>
        <button type="button" className="btn btn--dark" onClick={done}>完成</button>
      </div>
    </div>
  )
}
