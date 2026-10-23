// "我要这段的 GIF", "把 2:03 到 2:08 做成表情包", "截一段视频下来": the person wants a piece of the
// video as a file, not an answer. Such a message opens the clip studio (components/ClipStudio.jsx)
// instead of going to the model.

const WANTS = /(gif|动图|表情包|截(个|一段|一下|成|取|下来|出来)|片段.{0,4}(下载|导出|保存)|(下载|导出|保存).{0,6}(片段|这段|这一段)|做成.{0,4}(视频|mp4))/i
// …and it is asked of us ("我要", "帮我", "把 … 做成", "截一段"), not a question about the video —
// a software tutorial is full of those ("剪映里怎么导出这一段片段？", "PS 怎么做 GIF？").
const ASKS = /(我要|我想要|帮我|给我|请|麻烦|来(个|张|一张|段|一段)|^\s*把|(^|[，,\s])截(一段|个|成|下来)|做(个|一个|一张|成))/
const HOW = /怎么|怎样|如何|为什么|为啥|哪个|哪些|什么|是否|能不能|可以吗|吗[？?]?$|[？?]\s*$|快捷键|步骤|第几/
const SOUND = /mp4|视频片段|带声音|有声|做成.{0,4}视频/i
const PICTURE = /gif|动图|表情包/i

/** { format: 'gif' | 'mp4' } when the text asks for a piece of the video, else null. */
export function clipIntent(text) {
  if (!text || !WANTS.test(text) || !ASKS.test(text) || HOW.test(text)) return null
  return { format: SOUND.test(text) && !PICTURE.test(text) ? 'mp4' : 'gif' }
}

// 02:03 · 1:02:03 · 2:03.5 · 2分03秒 · 2分3 · 123秒 · 12.5 秒
const TIME = /(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.(\d+))?|(\d+)\s*分\s*(\d+(?:\.\d+)?)?\s*秒?|(\d+(?:\.\d+)?)\s*秒/g

/** The times written in the text, in seconds, in order. */
export function timesIn(text) {
  const out = []
  for (const m of text.matchAll(TIME)) {
    if (m[1] !== undefined) {
      const [a, b, c] = [Number(m[1]), Number(m[2]), m[3] !== undefined ? Number(m[3]) : null]
      const frac = m[4] ? Number(`0.${m[4]}`) : 0
      out.push((c === null ? a * 60 + b : a * 3600 + b * 60 + c) + frac)
    } else if (m[5] !== undefined) {
      out.push(Number(m[5]) * 60 + (m[6] ? Number(m[6]) : 0))
    } else {
      out.push(Number(m[7]))
    }
  }
  return out
}

/** [start, end] from the text (two times: between them; one: the few seconds around it), or null. */
export function rangeIn(text, duration = Infinity) {
  const t = timesIn(text).filter((x) => x <= duration + 1)
  if (t.length >= 2) return [Math.min(t[0], t[1]), Math.max(t[0], t[1])]
  if (t.length === 1) return [Math.max(0, t[0] - 1), Math.min(duration, t[0] + 2)]
  return null
}
