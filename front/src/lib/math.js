// Recognize explicit TeX delimiters. Code and URLs stay literal; incomplete streaming formulas
// remain text until their closing delimiter arrives. Dollar amounts need no special escaping.
const escaped = (text, pos) => {
  let count = 0
  while (pos > 0 && text[--pos] === '\\') count += 1
  return count % 2 === 1
}
export function splitMath(text) {
  const source = String(text || '')
  const parts = []
  let start = 0
  let i = 0
  while (i < source.length) {
    if (source[i] === '`') {
      const ticks = source.slice(i).match(/^`+/)[0]
      const end = source.indexOf(ticks, i + ticks.length)
      i = end < 0 ? source.length : end + ticks.length
      continue
    }
    const url = source.slice(i).match(/^https?:\/\/[^\s<>]+/)
    if (url) { i += url[0].length; continue }
    if (source.startsWith('\\\\', i)) { i += 2; continue }
    if (escaped(source, i)) { i += 1; continue }
    const open = source.startsWith('$$', i) ? '$$' : source.startsWith('\\[', i) ? '\\['
      : source.startsWith('\\(', i) ? '\\(' : source[i] === '$' ? '$' : null
    if (!open) { i += 1; continue }
    const close = open === '\\[' ? '\\]' : open === '\\(' ? '\\)' : open
    const from = i + open.length
    if (open === '$' && (!source[from] || /\s/.test(source[from]))) { i += 1; continue }
    let end = source.indexOf(close, from)
    while (end >= 0 && escaped(source, end)) end = source.indexOf(close, end + close.length)
    if (end < 0 || (open === '$' && (source.slice(from, end).includes('\n') || source[end - 1] === '$' || source[end + 1] === '$' || /\s/.test(source[end - 1]) || /\d/.test(source[end + 1] || '')))) { i += open.length; continue }
    if (end === from) { i += open.length; continue }
    if (i > start) parts.push({ type: 'text', text: source.slice(start, i) })
    parts.push({ type: 'math', text: source.slice(from, end), display: open === '$$' || open === '\\[' })
    i = end + close.length
    start = i
  }
  if (start < source.length) parts.push({ type: 'text', text: source.slice(start) })
  return parts
}
export function formulaSource(value) {
  let text = String(value || '').trim()
  for (const [open, close] of [['$$', '$$'], ['\\[', '\\]'], ['\\(', '\\)'], ['$', '$']]) {
    if (text.startsWith(open) && text.endsWith(close)) return text.slice(open.length, -close.length).trim()
  }
  return text
}
