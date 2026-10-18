import React, { useState } from 'react'
import AntifraudPanel from '../AntifraudPanel'
import { IconShield } from '../antifraud-icons'

// Anti-fraud in the workbench: nothing runs until asked (it may query institutions and the model).
export default function AntifraudTab({ video, transcript, screentext, frameRevision }) {
  const [started, setStarted] = useState(false)
  if (!video?.jobId) return <p className="bench__note muted">导入视频后可以识别。</p>
  if (!started) {
    return (
      <div className="bench__idle">
        <IconShield size={28} />
        <h3>反诈识别</h3>
        <p className="body-sm muted">从语音、画面文字和关键帧里找诈骗话术、引流方式（微信号、电话、二维码、网址），查询出现的机构有没有公开登记，给出风险等级和带时间点的依据。</p>
        <p className="caption muted">会联网查询机构并调用模型，需要十几秒到一分钟。结果只作参考，需要人工核实。</p>
        <button type="button" className="btn btn--dark" onClick={() => setStarted(true)}>开始识别</button>
      </div>
    )
  }
  return (
    <AntifraudPanel jobId={video.jobId} videoTitle={video.title} transcript={transcript} screentext={screentext}
      frameRevision={frameRevision} onClose={() => setStarted(false)} />
  )
}
