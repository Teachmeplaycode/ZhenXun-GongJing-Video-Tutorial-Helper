// The note board: blocks with a place on an endless canvas. A block is
//   { id, type: 'title' | 'section' | 'figure' | 'mindmap' | 'text', x, y, w, ...content }
// (heights come from the content, except the mind map, which scales with its width).
// The default arrangement reads like a page: the title on top, each section with its pictures
// to its right, the mind map beside the whole column.

export const COL_SECTION = { x: 0, w: 580 }
export const COL_FIGURES = { x: 620, w: 380 }
export const MINDMAP_X = 1060
const GAP = 20 // between a section's pictures
const ROW_GAP = 56 // between sections

// Before anything is measured: rough heights so the first frame isn't a pile.
export function estimateHeight(b) {
  if (b.type === 'title') return 96 + (b.summary ? 60 : 0)
  if (b.type === 'figure') return Math.round((b.w * 9) / 16) + 44
  if (b.type === 'section') return 64 + 28 * (b.points?.length || 0) + 52 * (b.formulas?.length || 0) + 48 * (b.examples?.length || 0)
  if (b.type === 'text') return 80
  return 300
}

export function defaultBoard(note) {
  const blocks = [{ id: 'title', type: 'title', x: 0, y: 0, w: COL_FIGURES.x + COL_FIGURES.w, text: note.title, summary: note.summary || '' }]
  for (const s of note.sections || []) {
    blocks.push({ id: `sec-${s.id}`, type: 'section', x: COL_SECTION.x, y: 0, w: COL_SECTION.w, title: s.title, start: s.start, end: s.end,
      points: s.points || [], formulas: s.formulas || [], examples: s.examples || [], keywords: s.keywords || [] })
    ;(s.figures || []).forEach((f, k) => blocks.push({ id: `fig-${s.id}-${k}`, type: 'figure', section: `sec-${s.id}`,
      x: COL_FIGURES.x, y: 0, w: COL_FIGURES.w, src: f.src, caption: f.caption, time: f.time }))
  }
  if (note.mindmap) blocks.push({ id: 'mindmap', type: 'mindmap', x: MINDMAP_X, y: 0, w: 640, tree: note.mindmap })
  return { version: 1, viewport: { x: 40, y: 40, zoom: 0.8 }, blocks: flow(blocks, {}) }
}

// Re-place the page-like blocks top to bottom with real heights (`heights`: id → px, else estimated).
// Free text blocks keep their place; the mind map moves beside the column.
export function flow(blocks, heights) {
  const h = (b) => heights[b.id] ?? estimateHeight(b)
  const byId = new Map(blocks.map((b) => [b.id, { ...b }]))
  const out = [...byId.values()]
  let y = 0
  const title = byId.get('title')
  if (title) {
    Object.assign(title, { x: 0, y: 0 })
    y = h(title) + ROW_GAP
  }
  for (const sec of out.filter((b) => b.type === 'section')) {
    Object.assign(sec, { x: COL_SECTION.x, y })
    let fy = y
    for (const fig of out.filter((b) => b.type === 'figure' && b.section === sec.id)) {
      Object.assign(fig, { x: COL_FIGURES.x, y: fy })
      fy += h(fig) + GAP
    }
    y = Math.max(y + h(sec), fy - GAP) + ROW_GAP
  }
  const map = byId.get('mindmap')
  if (map) Object.assign(map, { x: MINDMAP_X, y: title ? h(title) + ROW_GAP : 0 })
  return out
}

// After an AI revision, keep the person's columns and spacing. Only push blocks obstructed by
// expanded/new content, carrying a moved section's pictures with it. Existing overlaps unrelated
// to this revision are left alone; the editor's measured heights determine the actual clearance.
export function settleRevision(blocks, heights, changedIds) {
  const changed = new Set(changedIds || [])
  const original = new Map(blocks.map((block) => [block.id, block]))
  const moved = new Set()
  const placed = []
  const byId = new Map()
  const height = (block) => heights[block.id] ?? estimateHeight(block)
  const affected = (block) => changed.has(block.id) || changed.has(block.section) || moved.has(block.id)
  for (const source of [...blocks].sort((a, b) => a.y - b.y || a.x - b.x)) {
    const block = { ...source }
    const parent = block.section && byId.get(block.section)
    if (parent) block.y += parent.y - original.get(parent.id).y
    for (const previous of placed) {
      if (original.get(previous.id).y >= source.y) continue
      if (!affected(block) && !affected(previous)) continue
      if (block.x >= previous.x + previous.w || previous.x >= block.x + block.w) continue
      const end = previous.y + height(previous)
      if (block.y < end + GAP) block.y = end + GAP
    }
    if (block.y !== source.y) moved.add(block.id)
    byId.set(block.id, block)
    placed.push(block)
  }
  return blocks.map((block) => byId.get(block.id))
}

// Top to bottom; blocks whose tops are within 40 px form a row, read left to right (as the export).
export function readingOrder(blocks) {
  const rows = []
  for (const b of [...blocks].sort((a, c) => a.y - c.y || a.x - c.x)) {
    const row = rows[rows.length - 1]
    if (row && Math.abs(b.y - row[0].y) < 40) row.push(b)
    else rows.push([b])
  }
  return rows.flatMap((row) => row.sort((a, c) => a.x - c.x))
}

export function bounds(blocks, heights) {
  if (!blocks.length) return { x: 0, y: 0, w: 1, h: 1 }
  const xs = blocks.map((b) => b.x)
  const ys = blocks.map((b) => b.y)
  const right = blocks.map((b) => b.x + b.w)
  const bottom = blocks.map((b) => b.y + (heights[b.id] ?? estimateHeight(b)))
  const x = Math.min(...xs)
  const y = Math.min(...ys)
  return { x, y, w: Math.max(...right) - x, h: Math.max(...bottom) - y }
}

// ---- mind map: a tidy tree, root on the left, branches fanning right -----------------------------
const NODE_H = 34
const LEVEL_GAP = 56
const SIBLING_GAP = 10
const textWidth = (s) => [...(s || '')].reduce((w, ch) => w + (ch.charCodeAt(0) > 255 ? 15 : 8.4), 0)

export function layoutMindmap(tree) {
  const nodes = []
  const links = []
  const widths = []
  const walk = (node, depth) => {
    const w = Math.min(260, Math.max(48, textWidth(node.label) + 28))
    widths[depth] = Math.max(widths[depth] || 0, w)
    return { label: node.label, w, depth, kids: (node.children || []).map((c) => walk(c, depth + 1)) }
  }
  const root = walk(tree || { label: '' }, 0)
  const colX = []
  widths.forEach((w, d) => { colX[d] = d === 0 ? 0 : colX[d - 1] + widths[d - 1] + LEVEL_GAP })
  let cursor = 0
  const place = (n, branch) => {
    if (!n.kids.length) {
      n.y = cursor + NODE_H / 2
      cursor += NODE_H + SIBLING_GAP
    } else {
      n.kids.forEach((k, i) => place(k, n.depth === 0 ? i : branch))
      n.y = (n.kids[0].y + n.kids[n.kids.length - 1].y) / 2
    }
    n.x = colX[n.depth]
    n.branch = branch
    nodes.push(n)
    for (const k of n.kids) links.push({ from: n, to: k })
  }
  place(root, 0)
  const width = colX[widths.length - 1] + widths[widths.length - 1]
  return { nodes, links, width: Math.max(width, 1), height: Math.max(cursor - SIBLING_GAP, NODE_H), nodeH: NODE_H }
}

// The mind map as an indented outline (two spaces a level) and back, for editing it as text.
export function treeToOutline(node, depth = 0) {
  if (!node?.label) return ''
  return [`${'  '.repeat(depth)}${node.label}`, ...(node.children || []).map((c) => treeToOutline(c, depth + 1))].filter(Boolean).join('\n')
}

export function outlineToTree(text) {
  const root = { label: '', children: [] }
  const stack = [{ depth: -1, node: root }]
  for (const raw of (text || '').split('\n')) {
    if (!raw.trim()) continue
    const depth = Math.floor((raw.match(/^\s*/)[0].replace(/\t/g, '  ').length) / 2)
    const node = { label: raw.trim().replace(/^[-*•]\s*/, '') }
    while (stack.length > 1 && stack[stack.length - 1].depth >= depth) stack.pop()
    const parent = stack[stack.length - 1].node
    ;(parent.children ||= []).push(node)
    stack.push({ depth, node })
  }
  const top = root.children
  if (top.length === 1) return top[0]
  return { label: '思维导图', children: top }
}
