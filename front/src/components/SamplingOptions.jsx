import React from 'react'

// How densely an import samples the video (backend modules/frames/sampling.py): three presets and,
// folded away, the numbers behind them. value: { preset, frames, shots, ocr_fps } — empty fields
// follow the preset. Remembered in the browser by the import screen.
export const PRESETS = [
  { key: 'quick', label: '快速', hint: '32 张关键帧，每 2 秒读一次画面文字。短视频、只想快速问几句' },
  { key: 'standard', label: '标准', hint: '每个镜头至少一张，长视频最多 128 张；每秒读一次画面文字。大多数视频' },
  { key: 'fine', label: '精细', hint: '约每秒一张、最多 256 张；每秒读两次画面文字。网课、板书、要做笔记' },
]
const OCR = [
  { value: '', label: '跟随预设' }, { value: '0', label: '不识别' }, { value: '0.5', label: '每 2 秒' },
  { value: '1', label: '每秒' }, { value: '2', label: '每秒 2 次' },
]
export const DEFAULT_SAMPLING = { preset: 'standard', frames: '', shots: null, ocr_fps: '' }

export const presetLabel = (v) => PRESETS.find((p) => p.key === v.preset)?.label || '标准'
export const customized = (v) => v.frames !== '' || v.shots !== null || v.ocr_fps !== ''

// What the backend gets: the preset plus only the overrides actually set.
export function samplingSpec(v) {
  const spec = { preset: v.preset }
  if (v.frames !== '' && Number.isFinite(Number(v.frames))) spec.frames = Number(v.frames)
  if (v.shots !== null) spec.shots = v.shots
  if (v.ocr_fps !== '') spec.ocr_fps = Number(v.ocr_fps)
  return spec
}

export default function SamplingOptions({ value, onChange }) {
  const set = (patch) => onChange({ ...value, ...patch })
  return (
    <div id="import-sampling" className="import-options sampling" data-exit>
      <div className="sampling__presets" role="radiogroup" aria-label="采样密度">
        {PRESETS.map((p) => (
          <label key={p.key} className="sampling__preset" data-on={value.preset === p.key || undefined}>
            <input type="radio" name="sampling-preset" value={p.key} checked={value.preset === p.key} onChange={() => set({ preset: p.key })} />
            <strong>{p.label}</strong>
            <span>{p.hint}</span>
          </label>
        ))}
      </div>
      <details className="sampling__advanced" open={customized(value) || undefined}>
        <summary>高级设置{customized(value) ? '（已修改）' : ''}</summary>
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
            <input type="checkbox" checked={value.shots ?? value.preset !== 'quick'}
              onChange={(e) => set({ shots: e.target.checked })} />
            按镜头补帧：每个镜头至少一张
          </label>
          {customized(value) ? <button type="button" className="link-btn" onClick={() => onChange({ ...DEFAULT_SAMPLING, preset: value.preset })}>恢复预设</button> : null}
        </div>
        <p className="caption muted">关键帧主要影响时间轴能看多细；回答时需要细看的地方，agent 会自己补看和慢放。更多关键帧会让导入更久。</p>
      </details>
    </div>
  )
}
