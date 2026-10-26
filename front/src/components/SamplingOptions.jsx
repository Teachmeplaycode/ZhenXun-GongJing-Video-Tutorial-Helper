import React from 'react'
import { OCR_MODES, normalizeOcrMode } from '../lib/ocrMode'

// How densely an import samples the video (backend modules/frames/sampling.py): four presets as one
// segmented control with the chosen one explained, and, folded away, the numbers behind them. value: { preset, frames, shots, ocr_fps } — empty fields
// follow the preset. Remembered in the browser by the import screen.
export const PRESETS = [
  { key: 'auto', label: '自动', hint: '按视频时长安排画面和文字采样，长视频优先减少全片扫描，提问时按需补看', use: '按时长调整 · 推荐' },
  { key: 'quick', label: '快速', hint: '更快完成导入，适合短视频和快速浏览', use: '快速了解内容' },
  { key: 'standard', label: '标准', hint: '兼顾速度与细节，适合大多数视频', use: '固定采样密度' },
  { key: 'fine', label: '精细', hint: '保留更多画面和文字细节，导入时间更长', use: '密集操作、细节核对' },
]
const OCR = [
  { value: '', label: '跟随预设' }, { value: '0', label: '不识别' }, { value: '0.5', label: '每 2 秒' },
  { value: '1', label: '每秒' }, { value: '2', label: '每秒 2 次' },
]
export const DEFAULT_SAMPLING = { preset: 'auto', frames: '', shots: null, ocr_fps: '', ocr_mode: 'hybrid' }

export const presetLabel = (v) => PRESETS.find((p) => p.key === v.preset)?.label || '自动'
export const customized = (v) => v.frames !== '' || v.shots !== null || v.ocr_fps !== ''

// What the backend gets: the preset plus only the overrides actually set.
export function samplingSpec(v) {
  const spec = { preset: v.preset, ocr_mode: normalizeOcrMode(v.ocr_mode) }
  if (v.frames !== '' && Number.isFinite(Number(v.frames))) spec.frames = Number(v.frames)
  if (v.shots !== null) spec.shots = v.shots
  if (v.ocr_fps !== '') spec.ocr_fps = Number(v.ocr_fps)
  return spec
}

export default function SamplingOptions({ value, onChange, onClose }) {
  const set = (patch) => onChange({ ...value, ...patch })
  const automaticShots = value.preset === 'auto' && value.shots === null
  const mode = normalizeOcrMode(value.ocr_mode)
  return (
    <div id="import-sampling" className="import-options sampling" data-exit>
      <div className="sampling__head"><div><h3>视频解析设置</h3><p>不确定怎么选？使用自动；已有的预设和自定义选择会保留。</p></div>{onClose ? <button type="button" className="import-settings__done" onClick={onClose}>完成</button> : null}</div>
      <div className="sampling__presets" role="radiogroup" aria-label="视频解析精细度">
        {PRESETS.map((p) => (
          <label key={p.key} className="sampling__preset" data-on={value.preset === p.key || undefined} title={p.hint}>
            <input type="radio" name="sampling-preset" value={p.key} checked={value.preset === p.key} onChange={() => set({ preset: p.key })} />
            <strong>{p.label}</strong><small>{p.use}</small>
          </label>
        ))}
      </div>
      <p className="sampling__hint">{PRESETS.find((p) => p.key === value.preset)?.hint}</p>
      <div className="sampling__processing">
        <h4>画面文字处理位置</h4>
        <div className="sampling__modes" role="radiogroup" aria-label="画面文字处理位置" aria-describedby="sampling-mode-hint">
          {OCR_MODES.map((item) => (
            <label key={item.key} className="sampling__mode" data-on={mode === item.key || undefined}>
              <input type="radio" name="ocr-mode" value={item.key} checked={mode === item.key} onChange={() => set({ ocr_mode: item.key })} />
              <strong>{item.label}</strong><small>{item.use}</small>
            </label>
          ))}
        </div>
        <p id="sampling-mode-hint" className="sampling__hint">{OCR_MODES.find((item) => item.key === mode)?.hint}</p>
        <p className="sampling__scope">仅决定画面文字在哪里识别；上传、语音转写和 AI 回答仍使用服务器。</p>
      </div>
      <details className="sampling__advanced" open={customized(value) || undefined}>
        <summary>自定义参数{customized(value) ? '（已修改）' : ''}</summary>
        <div className="sampling__fields">
          <label>
            关键帧数量
            <input type="number" min={8} max={256} step={1} inputMode="numeric" placeholder="跟随预设"
              value={value.frames} onChange={(e) => set({ frames: e.target.value })} />
          </label>
          <label>
            画面文字识别
            <select value={value.ocr_fps} onChange={(e) => set({ ocr_fps: e.target.value })}>
              {OCR.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <label className="sampling__check">
            <input type="checkbox" ref={(el) => { if (el) el.indeterminate = automaticShots }}
              checked={value.shots ?? (value.preset !== 'quick' && value.preset !== 'auto')}
              onChange={(e) => set({ shots: e.target.checked })} />
            按镜头补帧{automaticShots ? '：跟随时长，长视频关闭' : '：每个镜头至少一张'}
          </label>
          {customized(value) ? <button type="button" className="link-btn" onClick={() => onChange({ ...DEFAULT_SAMPLING, preset: value.preset, ocr_mode: mode })}>恢复预设</button> : null}
        </div>
        <p className="caption muted">关键帧越多，时间轴越细，导入也会更久。提问时仍可按需查看细节。</p>
      </details>
    </div>
  )
}
