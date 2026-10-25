import React from 'react'
import { createPortal } from 'react-dom'
import ContourLoader from '../components/ContourLoader'
import FlatSculpture from '../components/FlatSculpture'
import BackButton from '../components/BackButton'
import { fmtBytes } from '../lib/format'

// Full-screen contour terrain during upload; it opens out of the import slide (see App).
// link: resolving a video link instead of uploading a file (no byte progress, just the stage).
export default function UploadMask({ maskRef, contourRef, progress, name, size, link = false, onBack }) {
  return createPortal(
    <div ref={maskRef} className="upload-mask">
      <div ref={contourRef} className="upload-mask__contour">
        {/* Phones: the sculpture drawn flat; the terrain would be stretched on a tall screen. */}
        {window.matchMedia?.('(max-width: 760px)').matches ? <FlatSculpture /> : <ContourLoader />}
      </div>
      {/* Outline of the window that opens out of the import slide; App drives its geometry. */}
      <div className="upload-mask__frame" aria-hidden="true">
        <i /><i /><i /><i />
        <span className="upload-mask__frame-label"><b>{link ? '02 / LINK' : '02 / UPLOAD'}</b>{name}</span>
      </div>
      <header className="upload-mask__header" data-enter>
        <BackButton onClick={onBack} destination="导入视频" />
        <h1>{link ? '正在解析链接' : '正在上传视频'}</h1>
        <span className="caption muted">{link ? '识别平台并获取播放地址，不下载视频' : '完成后自动提取关键帧'}</span>
      </header>
      <div className="upload-mask__status" data-enter>
        <div className="upload-mask__status-head"><span className="upload-mask__name">{name}</span><strong className="mono-sm">{link ? (progress < 1 ? '解析中' : '完成') : `${(progress * 100).toFixed(0)}%`}</strong></div>
        <div className="bar" role="progressbar" aria-label={link ? '链接解析进度' : '上传进度'} aria-valuemin={0} aria-valuemax={100} aria-valuenow={link ? undefined : Math.round(progress * 100)} data-indeterminate={link && progress < 1 || undefined}><div className="bar__fill" style={link ? undefined : { transform: `scaleX(${progress})` }} /></div>
        <div className="upload-mask__row mono-sm">
          <span>{link
            ? (progress < 1 ? '获取视频信息与播放地址…' : '已获取播放地址，准备抓取画面')
            : size ? `${fmtBytes(size * progress)} / ${fmtBytes(size)}` : progress < 1 ? '读取素材中' : '上传完成'}</span>
        </div>
      </div>
    </div>, document.body
  )
}
