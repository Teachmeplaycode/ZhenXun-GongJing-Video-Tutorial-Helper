// One-line descriptions of tool calls for the step list: what was done, to what, and the outcome.
const clock = (s) => {
  const t = Math.max(0, Math.round(Number(s) || 0))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}
// "114" / 114.5 → "01:54"; "01:54" stays. Prefers the range the tool actually used (data) over what was asked.
const at = (v) => (v == null || v === '' ? '' : /^\d+(\.\d+)?$/.test(String(v).trim()) ? clock(v) : String(v))
const span = (p, d) => (typeof d.start === 'number' && typeof d.end === 'number'
  ? `${clock(d.start)}–${clock(d.end)}` : `${at(p.start)}–${at(p.end)}`)
const firstLine = (s) => (s || '').split('\n')[0]
const host = (url) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url || ''
  }
}

// Model rounds are the thinking between steps, not steps (as in Claude / Codex): kept out of the list.
export const isVisibleStep = (call) => !call.tool?.startsWith('vision.')

const RISK = { high: '高', medium: '中', low: '低' }

/** { verb, target, meta } for a call; `meta` is the outcome once known. */
export function describeStep(call) {
  const p = call.input?.params || {}
  const d = call.data || {}
  const n = call.resultCount
  const done = call.status === 'done'
  switch (call.tool) {
    case 'frames.select':
      return { verb: '选取画面', target: p.scope || '', meta: done ? `${n} 帧` : '' }
    case 'transcript.read':
      return { verb: '读取语音转写', target: p.scope || '', meta: done ? (n ? `${n} 行` : '没有转写') : '' }
    case 'decision.intent': // backend modules/agent/intent.py
      return {
        verb: '识别问题类型', target: '',
        meta: done ? `${d.name || ''}${d.p != null ? ` · ${d.p.toFixed(2)}` : d.how ? ` · ${d.how}` : ''}${d.skill ? ' · 先运行技能' : ''}` : '',
      }
    case 'decision.research_intent': {
      const needed = d.needed ?? /^需要/.test(call.stdout || '')
      return {
        verb: '判断是否需要查资料', target: '',
        meta: done ? `${needed ? '需要' : '不需要'}${d.p != null ? ` · ${d.p.toFixed(2)}` : ''}` : '',
      }
    }
    case 'screentext.read':
      return { verb: '读取画面文字', target: p.scope || '', meta: done ? (n ? `${n} 段` : '没有文字') : '' }
    case 'transcript.search':
      return { verb: '搜索转写', target: `「${p.query || ''}」`, meta: done ? `${n} 处` : '' }
    case 'transcript.read_range':
      return { verb: '读取转写', target: span(p, d), meta: done ? `${n} 句` : '' }
    case 'experience.recall':
      return { verb: '调取经验', target: (d.kinds || []).join('、'), meta: done ? `${n} 条` : '' }
    case 'frames.motion':
      return { verb: '测量运动', target: span(p, d), meta: done ? (d.camera ? d.camera.split(/[；（]/)[0] : '') : '' }
    case 'frames.replay': {
      const fps = d.fps ?? p.fps
      return { verb: '慢放复看', target: span(p, d), meta: done ? `${n} 帧${fps ? ` · 每秒 ${fps} 帧` : ''}` : '' }
    }
    case 'frames.view':
      return { verb: '细看画面', target: span(p, d), meta: done ? `${n} 张` : '' }
    case 'web.search': {
      const dropped = (d.results || []).filter((r) => r.verdict === 'irrelevant').length
      return {
        verb: '联网搜索', target: `「${p.query || ''}」`,
        meta: done ? `${n} 条${dropped ? ` · 去掉 ${dropped} 条无关` : ''}` : call.status === 'error' ? firstLine(call.stdout) : '',
      }
    }
    case 'web.fetch':
      return {
        verb: '阅读网页', target: d.host || host(p.url),
        meta: d.blocked ? '疑似注入，已拦截' : done ? `${(d.to ?? 0) - (d.from ?? 0)} 字` : call.status === 'error' ? firstLine(call.stdout).replace(/^失败：/, '') : '',
      }
    case 'audience.comments':
      return {
        verb: '读取评论区', target: (d.sort || p.sort) === 'time' ? '最新' : '热门',
        meta: done ? `${n} 条${d.total ? ` / 共 ${d.total}` : ''}` : call.status === 'error' ? firstLine(call.stdout).replace(/^失败：/, '') : '',
      }
    case 'audience.danmaku':
      return {
        verb: '读取弹幕',
        target: [p.start != null || p.end != null ? `${p.start ?? ''}–${p.end ?? ''}` : '', p.query ? `「${p.query}」` : ''].filter(Boolean).join(' ') || '整段视频',
        meta: done ? `${n} 条` : call.status === 'error' ? firstLine(call.stdout).replace(/^失败：/, '') : '',
      }
    case 'browser.use':
      return {
        verb: '操作浏览器', target: d.host || host(p.url) || `「${(p.task || '').slice(0, 24)}」`,
        meta: done ? `${n} 步` : call.status === 'error' ? firstLine(d.answer || call.stdout).slice(0, 40) : '',
      }
    case 'papers.search':
      return { verb: '检索论文', target: `「${p.query || ''}」`, meta: done ? `${d.source || p.source || 'openalex'} · ${n} 篇` : '' }
    case 'skill.factcheck': // backend modules/agent/skills.py
      return { verb: '科普核查', target: '逐条查证视频里的说法',
        meta: done ? (d.report ? `${d.report.summary?.total ?? n} 条说法 · 错误 ${d.report.summary?.wrong ?? 0} · 部分正确 ${d.report.summary?.partial ?? 0}` : '未完成') : '' }
    case 'skill.antifraud':
      return { verb: '反诈识别', target: '话术、引流、二维码与机构登记',
        meta: done ? (d.report ? `风险${RISK[d.report.assessment?.risk || d.report.score?.level] || '未知'}` : '未完成') : '' }
    default:
      return { verb: call.tool, target: '', meta: done && n != null ? `${n} 项` : '' }
  }
}

export { clock, host }
