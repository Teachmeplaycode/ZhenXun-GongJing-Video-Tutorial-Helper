export const fmtTime = (s) => {
  if (s == null || Number.isNaN(s)) return '--:--.-'
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${(s - m * 60).toFixed(1).padStart(4, '0')}`
}
export const fmtClock = (s) => {
  const t = Math.max(0, Math.floor(s || 0))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}
export const fmtBytes = (n) => {
  if (!n && n !== 0) return '—'
  if (n >= 1 << 30) return `${(n / (1 << 30)).toFixed(2)} GB`
  if (n >= 1 << 20) return `${(n / (1 << 20)).toFixed(1)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}
export const fmtElapsed = (ms) => (ms >= 60000 ? `${(ms / 60000).toFixed(1)} min` : `${(ms / 1000).toFixed(1)} s`)
export const frameNo = (i) => `F${String(i + 1).padStart(3, '0')}`
export const makeRunId = (d = new Date()) => {
  const p = (n) => String(n).padStart(2, '0')
  return `RUN-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}
/** Unix seconds → 刚刚 / 5 分钟前 / 3 小时前 / 昨天 / 10-12 */
export const fmtAgo = (seconds, now = Date.now()) => {
  const diff = Math.max(0, now / 1000 - seconds)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 2 * 86400) return '昨天'
  const d = new Date(seconds * 1000)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
