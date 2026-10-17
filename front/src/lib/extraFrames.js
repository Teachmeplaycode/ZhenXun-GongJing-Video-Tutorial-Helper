import { apiUrl } from '../api/client'

// Frames the agent read on demand during the conversation, for the timeline: each slow-motion replay
// (frames.replay) and each closer look (frames.view) is a group with its time range and frames.
// The same stretch read twice shows once (frames are keyed by their address).
export function collectExtras(messages) {
  const groups = []
  const seen = new Set()
  for (const m of messages) {
    for (const part of m.parts || []) {
      if (part.kind !== 'steps') continue
      for (const call of part.calls) {
        const d = call.data
        const kind = call.tool === 'frames.replay' ? 'replay' : call.tool === 'frames.view' ? 'view' : null
        if (!kind || !d?.frames?.length) continue
        const times = kind === 'replay' ? d.times : d.secs
        const frames = d.frames
          .map((path, i) => ({ src: apiUrl(path), time: Number(times?.[i]), kind }))
          .filter((f) => Number.isFinite(f.time) && !seen.has(f.src))
        if (!frames.length) continue
        frames.forEach((f) => seen.add(f.src))
        groups.push({ id: call.id, kind, start: frames[0].time, end: frames[frames.length - 1].time, frames })
      }
    }
  }
  return groups
}

// Times the answers point at ([01:55], 02:10 …, as the answer text turns them into buttons), for marks
// on the timeline: one per second, each with how many answers cited it. Manual replays have no text.
const CITED = /(?<![\d:])\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?(?![\d:])/g
export function collectCited(messages, duration = null) {
  const counts = new Map()
  for (const m of messages) {
    if (m.role !== 'assistant' || m.status === 'running' || !m.text) continue
    const seen = new Set()
    for (const [, stamp] of m.text.matchAll(CITED)) {
      const t = stamp.split(':').reduce((acc, n) => acc * 60 + Number(n), 0)
      if (duration != null && t > duration + 1) continue  // a clock-like number, not a moment of the video
      if (seen.has(t)) continue
      seen.add(t)
      counts.set(t, (counts.get(t) || 0) + 1)
    }
  }
  return [...counts].map(([time, n]) => ({ time, n })).sort((a, b) => a.time - b.time)
}
