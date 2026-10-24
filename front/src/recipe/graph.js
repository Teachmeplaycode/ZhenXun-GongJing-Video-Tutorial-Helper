// Node cards drawn the way Blender draws them (backend modules/recipe.py + modules/knowledge): a title bar
// coloured by the node's kind, every output socket on the right, every input on the left with its value
// when nothing is linked to it, the settings the tutorial changed marked. Geometry only: the canvas
// (RecipeCanvas.jsx) places cards and draws the curves from these numbers.
export const W = 240
export const HEAD = 30
export const ROW = 22
export const PAD = 8
export const GAP_X = 90
export const GAP_Y = 36

// Blender's socket colours by data type.
export const SOCKET = {
  Geometry: '#00D6A3', Float: '#A1A1A1', Int: '#598C5C', Vector: '#6363C7', Color: '#C7C729', Shader: '#63C763',
  Bool: '#CCA6D6', Rotation: '#A663C7', String: '#70B2FF', Object: '#ED9E5C', Material: '#EB7582', Matrix: '#4A4A8A',
  Menu: '#4D4D4D', Image: '#633863', Collection: '#F5F5F5', Texture: '#9E4FA3',
}
export const socketColor = (type = '') => {
  const key = Object.keys(SOCKET).find((k) => type.startsWith(k) || type.includes(k))
  return SOCKET[key] || '#A1A1A1'
}

// Title bar colour by what the node is, close to Blender's default theme.
export function headerColor(node) {
  const id = node.ref || ''
  const en = node.en || node.name || ''
  if (/Output|Viewer/.test(id + en)) return '#6E1F32'
  if (/Input|GroupInput|Value$|Position|Index|Normal|ObjectInfo|CollectionInfo|SceneTime|LightPath|TexCoord/.test(id + en)) return '#83314A'
  if (/ShaderNodeTex|Texture/.test(id + en)) return '#8A5A27'
  // converters before shaders: ShaderNodeMath is a converter, though its id says Shader
  if (/Math|MapRange|Clamp|Compare|Boolean|Switch|ColorRamp|ValToRGB|Separate|Combine|Mix(?!Shader)|FloatCurve|Accumulate|Random/.test(id + en)) return '#2D5F8F'
  if (/Bsdf|MixShader|AddShader|Emission|Background|Volume(Principled|Absorption|Scatter)|Holdout/.test(id)) return '#2C7A3C'
  if (/Vector|Mapping|Bump|Displacement|Normal/.test(id)) return '#3F3F9E'
  if (/RGB|Hue|Gamma|Bright|Invert|Color/.test(id)) return '#6D6A1F'
  if (/Simulation|Repeat|ForEach|Group|Frame/.test(id + en)) return '#3B5B2C'
  if (id.startsWith('GeometryNode') || id.startsWith('FunctionNode')) return '#1C7062'
  return '#4A4A4A'
}

const same = (a, b) => (a || '').replace(/\s/g, '').toLowerCase() === (b || '').replace(/\s/g, '').toLowerCase()
const findSocket = (list, name) => list.findIndex((s) => same(s.name, name) || same(s.en, name))

export function formatValue(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'boolean') return v ? '✓' : '✗'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
  if (Array.isArray(v)) return v.map(formatValue).join(', ')
  return String(v)
}

// A vector setting as Blender lists it, X / Y / Z: "0, 0, 0.005 m", "X:0 Y:0 Z:0.1°" or a default [0, 0, 0].
export function axes(value) {
  if (Array.isArray(value)) return value.length >= 3 ? value.slice(0, 3).map(formatValue) : null
  const text = String(value ?? '')
  const named = ['X', 'Y', 'Z'].map((a) => new RegExp(`${a}\\s*[:：=]\\s*([^,，;；\\s]+(?:\\s?(?:m|°|cm|mm))?)`, 'i').exec(text)?.[1])
  if (named.every(Boolean)) return named
  const parts = text.split(/[,，;；]/).map((x) => x.trim()).filter(Boolean)
  return parts.length === 3 ? parts : null
}

// One node as rows: options (settings that aren't sockets), outputs, inputs; a vector input that isn't
// linked gets its X / Y / Z under it, as in Blender. index.out/in: row index of a socket by name.
export function card(node, links) {
  const outputs = (node.outputs || []).map((s) => ({ ...s }))
  const inputs = (node.inputs || []).map((s) => ({ ...s }))
  for (const l of links) {
    if (l.from === node.id && findSocket(outputs, l.out) < 0) outputs.push({ name: l.out, type: '' })
    if (l.to === node.id && findSocket(inputs, l.in) < 0) inputs.push({ name: l.in, type: '' })
  }
  const options = []
  for (const p of node.params || []) {
    const i = findSocket(inputs, p.name)
    if (i >= 0) inputs[i] = { ...inputs[i], value: p.value, changed: true, time: p.time }
    else options.push({ name: p.name, value: p.value, time: p.time })
  }
  const linkedIn = new Set(links.filter((l) => l.to === node.id).map((l) => findSocket(inputs, l.in)))
  const rows = [
    ...options.map((o) => ({ kind: 'opt', ...o, changed: true })),
    ...outputs.map((s) => ({ kind: 'out', ...s })),
  ]
  inputs.forEach((s, i) => {
    const linked = linkedIn.has(i)
    const xyz = !linked && Array.isArray(s.default) && s.default.length === 3 ? axes(s.changed ? s.value : s.default) : null
    if (xyz) {
      rows.push({ kind: 'in', ...s, linked, value: '' })
      xyz.forEach((v, k) => rows.push({ kind: 'axis', name: 'XYZ'[k], value: v, changed: s.changed }))
    } else rows.push({ kind: 'in', ...s, linked, value: s.changed ? s.value : formatValue(s.default) })
  })
  const index = { out: {}, in: {} }
  rows.forEach((r, i) => {
    if (r.kind === 'out') index.out[r.name] = i
    if (r.kind === 'in') index.in[r.name] = i
  })
  return { node, rows, h: HEAD + rows.length * ROW + PAD * 2, index, outputs, inputs }
}

export const rowY = (i) => HEAD + PAD + i * ROW + ROW / 2

// Where a link's ends are, given the cards and their positions.
export function socketPoint(cards, pos, id, name, side) {
  const c = cards[id]
  const p = pos[id]
  if (!c || !p) return null
  const list = side === 'out' ? c.outputs : c.inputs
  const k = findSocket(list, name)
  const i = k < 0 ? undefined : c.index[side][list[k].name]
  const y = i === undefined ? HEAD / 2 : rowY(i)
  return { x: p[0] + (side === 'out' ? W : 0), y: p[1] + y, type: k < 0 ? '' : list[k].type }
}

// Columns by the longest chain of links into each node, then each node pulled right to sit just before
// the first node it feeds (sources don't all pile up in column 0); within a column, nodes follow the
// average height of what feeds them (fewer crossings). Nodes with no links at all sit apart, below.
export function autoLayout(tree, cards) {
  const ids = tree.nodes.map((n) => n.id)
  const into = Object.fromEntries(ids.map((id) => [id, []]))
  const from = Object.fromEntries(ids.map((id) => [id, []]))
  for (const l of tree.links) {
    if (into[l.to] && from[l.from]) { into[l.to].push(l.from); from[l.from].push(l.to) }
  }
  const layer = {}
  const visit = (id, seen = new Set()) => {
    if (layer[id] != null) return layer[id]
    if (seen.has(id)) return 0
    seen.add(id)
    layer[id] = into[id].length ? Math.max(...into[id].map((f) => visit(f, seen) + 1)) : 0
    return layer[id]
  }
  ids.forEach((id) => visit(id))
  for (let pass = 0; pass < 3; pass += 1) {
    for (const id of [...ids].sort((a, b) => layer[b] - layer[a])) {
      if (from[id].length) layer[id] = Math.max(layer[id], Math.min(...from[id].map((t) => layer[t])) - 1)
    }
  }
  const linked = ids.filter((id) => into[id].length || from[id].length)
  const alone = ids.filter((id) => !into[id].length && !from[id].length)
  const columns = []
  linked.forEach((id) => { (columns[layer[id]] ||= []).push(id) })
  const order = {}
  const pos = {}
  columns.forEach((col, c) => {
    if (!col) return
    const centre = (id) => {
      const ys = into[id].filter((f) => order[f] != null).map((f) => order[f])
      return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : Infinity
    }
    col.sort((a, b) => centre(a) - centre(b))
    let y = 0
    for (const id of col) {
      pos[id] = [c * (W + GAP_X), y]
      order[id] = y + cards[id].h / 2
      y += cards[id].h + GAP_Y
    }
  })
  // second sweep, right to left: a source sits level with what it feeds
  for (let c = columns.length - 1; c >= 0; c -= 1) {
    for (const id of columns[c] || []) {
      if (into[id].length || !from[id].length) continue
      const ys = from[id].filter((t) => pos[t]).map((t) => pos[t][1])
      if (ys.length) pos[id][1] = Math.min(...ys)
    }
    const col = (columns[c] || []).slice().sort((a, b) => pos[a][1] - pos[b][1])
    let floor = -Infinity
    for (const id of col) {
      pos[id][1] = Math.max(pos[id][1], floor)
      floor = pos[id][1] + cards[id].h + GAP_Y
    }
  }
  const bottom = Math.max(0, ...linked.map((id) => pos[id][1] + cards[id].h)) + GAP_Y * 3
  alone.forEach((id, i) => { pos[id] = [(i % 6) * (W + GAP_X / 2), bottom + Math.floor(i / 6) * 260] })
  return pos
}

export function bounds(cards, pos) {
  const ids = Object.keys(pos).filter((id) => cards[id])
  if (!ids.length) return { x: 0, y: 0, w: 400, h: 300 }
  const xs = ids.map((id) => pos[id][0])
  const ys = ids.map((id) => pos[id][1])
  const x = Math.min(...xs) - 40
  const y = Math.min(...ys) - 40
  return { x, y, w: Math.max(...ids.map((id) => pos[id][0] + W)) + 40 - x, h: Math.max(...ids.map((id) => pos[id][1] + cards[id].h)) + 40 - y }
}

export function asText(r) {
  const lines = [`抄作业：${r.goal || ''}${r.software ? `（${r.software}${r.version ? ` ${r.version}` : ''}）` : ''}`]
  for (const t of r.trees) {
    const names = Object.fromEntries(t.nodes.map((n) => [n.id, n.name]))
    lines.push('', `【${t.name}】`)
    for (const n of t.nodes) {
      lines.push(`- ${n.name}${n.en ? `（${n.en}）` : ''}${n.params.length ? '：' + n.params.map((p) => `${p.name}=${p.value}`).join('，') : ''}`)
    }
    if (t.links.length) lines.push('连线：', ...t.links.map((l) => `  ${names[l.from]}.${l.out} → ${names[l.to]}.${l.in}`))
  }
  if (r.version_notes?.length) lines.push('', '版本差异：', ...r.version_notes.map((v) => `- （${v.source}）${v.text}`))
  if (r.unsure?.length) lines.push('', '需要回看确认：', ...r.unsure.map((u) => `- ${u.text}`))
  return lines.join('\n')
}
