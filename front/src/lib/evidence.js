import { createContext, useContext } from 'react'

// How a cited moment can be looked at again (backend modules/playback.py), so every time link says
// what clicking it does instead of looking the same in all three cases:
//   original  plays the original video at that moment
//   cache     shows the sampled frames around it (the original is gone or not playable)
//   none      nothing to show: times stay plain text, never a link that leads nowhere
export const EvidenceContext = createContext({ state: 'cache' })
export const useEvidence = () => useContext(EvidenceContext)

export const SEEK_TITLE = {
  original: '在原片里播放这一刻',
  cache: '查看这一刻的缓存画面（原视频不可用）',
  none: '',
}
