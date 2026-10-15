// Helpers for the "示例素材" demo. Real videos (links and uploads) are sampled by the backend.

export function pickFrameCount(duration) {
  if (!duration || !Number.isFinite(duration)) return 56
  return Math.min(64, Math.max(48, Math.round(duration / 2)))
}

// Placeholder frames for the "示例素材" path (no file chosen): flat tonal plates with the timestamp.
export function syntheticFrames(count, duration, colors) {
  const canvas = document.createElement('canvas')
  canvas.width = 320
  canvas.height = 180
  const ctx = canvas.getContext('2d')
  const frames = []
  for (let i = 0; i < count; i += 1) {
    const u = i / count
    ctx.fillStyle = colors.surface
    ctx.fillRect(0, 0, 320, 180)
    ctx.strokeStyle = colors.line
    ctx.lineWidth = 1
    for (let k = 0; k < 9; k += 1) {
      ctx.beginPath()
      for (let x = 0; x <= 320; x += 8) {
        const y = 30 + k * 16 + 10 * Math.sin(x / 40 + u * 9 + k * 0.6)
        if (x === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()
    }
    ctx.fillStyle = colors.ink
    ctx.font = '500 14px "JetBrains Mono", monospace'
    const time = ((i + 0.5) / count) * duration
    ctx.fillText(`SAMPLE · ${String(Math.floor(time / 60)).padStart(2, '0')}:${String(Math.floor(time % 60)).padStart(2, '0')}`, 14, 164)
    frames.push({ index: i, time, src: canvas.toDataURL('image/jpeg', 0.8) })
  }
  return frames
}
