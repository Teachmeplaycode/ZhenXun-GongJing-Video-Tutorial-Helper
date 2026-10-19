import React, { useEffect, useRef, useState } from 'react'
import FrameLightbox from '../components/FrameLightbox'
import { IconCheck, IconChevron, IconExpand } from '../components/Icons'
import { fetchPictureTexts } from '../api/client'

const PLATFORM_NAMES = {
  local: '上传', redbook: '小红书', xiaohongshu: '小红书', douyin: '抖音', weibo: '微博', twitter: 'X', x: 'X',
  instagram: 'Instagram', kuaishou: '快手', bilibili: 'B 站', threads: 'Threads', facebook: 'Facebook',
}

// The page for a picture set (an image post, or uploaded pictures): no analysis screen and no time
// axis. The post on the left — a large picture, a bar to pick it as an attachment or zoom, the
// thumbnails, and (folded) the text read on it — and the chat (children) on the right.
// focus: { index, key } from an answer's 「第 n 张」, shows that picture.
export default function PictureStage({ meta, jobId, frames, selected, onToggle, screentext, focus = null, children }) {
  const pictures = [...frames].sort((a, b) => a.index - b.index)
  const [at, setAt] = useState(0)
  const [zoom, setZoom] = useState(false)
  const [texts, setTexts] = useState({}) // index → lines
  const [fullBody, setFullBody] = useState(false)
  const stripRef = useRef(null)
  const total = pictures.length
  const current = pictures[Math.min(at, Math.max(0, total - 1))]
  const picked = new Set(selected.map((f) => f.index))
  const ready = pictures.filter((f) => f.src).length

  useEffect(() => {
    if (focus && focus.index >= 0 && focus.index < total) setAt(focus.index)
  }, [focus, total])

  // The text of each picture, read again whenever recognition reports in.
  const textStatus = screentext?.status
  useEffect(() => {
    if (!jobId) return undefined
    let stopped = false
    fetchPictureTexts(jobId).then((r) => {
      if (!stopped) setTexts(Object.fromEntries(r.items.map((it) => [it.index, it.lines])))
    }).catch(() => {})
    return () => { stopped = true }
  }, [jobId, textStatus])

  // Keep the current thumbnail in view (the strip scrolls, not the page).
  useEffect(() => {
    const strip = stripRef.current
    const el = strip?.children[at]
    if (!el) return
    const left = el.offsetLeft - strip.offsetLeft
    if (left < strip.scrollLeft) strip.scrollLeft = left
    else if (left + el.offsetWidth > strip.scrollLeft + strip.clientWidth) strip.scrollLeft = left + el.offsetWidth - strip.clientWidth
  }, [at])

  const step = (k) => setAt((i) => (i + k + total) % total)
  const lines = current ? texts[current.index] : null
  const platform = PLATFORM_NAMES[meta?.platform] || meta?.platform || ''
  const textNote = screentext?.status === 'running' || screentext?.status === 'pending' ? '正在识别…'
    : screentext?.status === 'unavailable' ? (screentext.message || '本机不支持文字识别') : '这张没有文字'

  const on = current ? picked.has(current.index) : false
  const body = (meta?.description || '').trim()
  const tags = meta?.tags || []
  const stats = meta?.stats || {}
  const counts = [['likes', '赞'], ['favorites', '收藏'], ['comments', '评论']]
    .filter(([k]) => stats[k] != null).map(([k, label]) => `${label} ${stats[k]}`)

  return (
    <div className="pics-stage">
      <section className="pics-post" aria-label="图文内容">
        <header className="pics-post__head">
          <h1 className="pics-post__title" title={meta?.name || ''}>{meta?.name || '图片'}</h1>
          <p className="pics-post__meta mono-sm muted">
            <span className="pics-post__tag">{platform ? `${platform} · ` : ''}图文</span>{' · '}
            {meta?.author ? `${meta.author} · ` : ''}{total} 张{ready < total ? ` · 已读取 ${ready} 张` : ''}
            {counts.length ? ` · ${counts.join(' · ')}` : ''}
            {screentext?.status === 'running' ? ' · 正在识别文字…' : ''}
          </p>
        </header>

        <div className="pics-view" tabIndex={0} aria-label={`第 ${at + 1} / ${total} 张，左右方向键切换`}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') { e.preventDefault(); step(1) }
            if (e.key === 'ArrowLeft') { e.preventDefault(); step(-1) }
          }}>
          {current?.src ? (
            <button type="button" className="pics-view__image" onClick={() => setZoom(true)} aria-label={`放大第 ${at + 1} 张`}>
              <img src={current.src} alt={`第 ${at + 1} 张`} />
            </button>
          ) : (
            <div className="pics-view__empty">{current?.status === 'missing' ? '这张图没有取到' : '正在读取图片…'}</div>
          )}
          {total > 1 ? (
            <>
              <button type="button" className="pics-view__nav pics-view__nav--prev" onClick={() => step(-1)} aria-label="上一张"><IconChevron size={16} /></button>
              <button type="button" className="pics-view__nav pics-view__nav--next" onClick={() => step(1)} aria-label="下一张"><IconChevron size={16} /></button>
            </>
          ) : null}
        </div>

        <div className="pics-bar">
          <span className="pics-view__count mono-sm">{at + 1} / {total}</span>
          <span className="pics-bar__gap" />
          {current?.src ? (
            <button type="button" className="pics-bar__btn" data-on={on || undefined} aria-pressed={on} onClick={() => onToggle(current)}
              aria-label={`${on ? '取消' : '选'}第 ${at + 1} 张作附件`} title="只针对选中的图片提问">
              <IconCheck size={12} /> {on ? '已选作附件' : '选作附件'}
            </button>
          ) : null}
          {current?.src ? (
            <button type="button" className="pics-bar__btn" onClick={() => setZoom(true)} aria-label="全屏查看"><IconExpand size={12} /> 放大</button>
          ) : null}
        </div>

        {total > 1 ? (
          <ol ref={stripRef} className="pics-strip" aria-label="全部图片">
            {pictures.map((f, i) => (
              <li key={f.index} data-on={i === at || undefined} data-picked={picked.has(f.index) || undefined}>
                <button type="button" className="pics-strip__thumb" onClick={() => setAt(i)} aria-label={`看第 ${i + 1} 张`} aria-current={i === at || undefined}>
                  {f.src ? <img src={f.src} alt="" loading="lazy" /> : <span className="pics-strip__wait" />}
                  <span className="pics-strip__n mono-sm">{i + 1}</span>
                  {picked.has(f.index) ? <span className="pics-strip__picked" aria-hidden="true"><IconCheck size={10} /></span> : null}
                </button>
              </li>
            ))}
          </ol>
        ) : null}

        {body || tags.length ? (
          <section className="pics-body" data-full={fullBody || undefined} aria-label="正文">
            {body ? <p className="pics-body__text">{body}</p> : null}
            {tags.length ? <p className="pics-body__tags">{tags.map((t) => <span key={t}>#{t}</span>)}</p> : null}
            {body.length > 120 ? (
              <button type="button" className="link-btn pics-body__more" onClick={() => setFullBody((v) => !v)} aria-expanded={fullBody}>
                {fullBody ? '收起' : '展开全文'}
              </button>
            ) : null}
          </section>
        ) : null}

        <details className="pics-text" aria-label={`第 ${at + 1} 张的文字`}>
          <summary>
            <IconChevron size={11} className="pics-text__fold" />
            <span>图中文字</span>
            <span className="mono-sm muted">{lines?.length ? `第 ${at + 1} 张 · ${lines.length} 行` : textNote}</span>
          </summary>
          {lines?.length ? <ul>{lines.map((l, k) => <li key={k}>{l}</li>)}</ul> : null}
        </details>
      </section>

      <div className="pics-chat">{children}</div>

      {zoom ? (
        <FrameLightbox
          items={pictures.filter((f) => f.src).map((f) => ({ src: f.src, time: f.time, label: `第 ${f.index + 1} 张` }))}
          at={Math.max(0, pictures.filter((f) => f.src).findIndex((f) => f.index === current?.index))}
          onAt={(k) => setAt(pictures.findIndex((f) => f.index === pictures.filter((x) => x.src)[k].index))}
          onClose={() => setZoom(false)}
        />
      ) : null}
    </div>
  )
}
