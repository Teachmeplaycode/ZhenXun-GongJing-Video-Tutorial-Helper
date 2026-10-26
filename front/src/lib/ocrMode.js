// Where on-screen text is recognised. Sampling density is an independent choice.
export const OCR_MODES = [
  { key: 'hybrid', label: '混合加速', use: '本机与服务器分担 · 推荐', hint: '本机与服务器分担画面文字识别；本机不可用时由服务器接续。首次使用会下载并缓存本机模型。' },
  { key: 'local', label: '本机处理', use: '使用这台设备识别', hint: '画面文字在本机识别；请保持页面打开。首次使用会下载并缓存识别模型。' },
  { key: 'server', label: '服务器处理', use: '适合手机或后台处理', hint: '画面文字由服务器识别，不占用本机识别算力。' },
]

export const normalizeOcrMode = (value) => OCR_MODES.some((mode) => mode.key === value) ? value : 'hybrid'
export const ocrModeLabel = (value) => OCR_MODES.find((mode) => mode.key === normalizeOcrMode(value)).label
