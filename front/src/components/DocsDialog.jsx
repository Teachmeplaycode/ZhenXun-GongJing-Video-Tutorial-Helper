import React from 'react'
import { createPortal } from 'react-dom'
import { IconBook, IconClose } from './Icons'
import '../styles/guide.css'

// 文档: what 帧寻 does, how to use it, how to read its evidence, and the web demo's allowances.

const SECTIONS = [
  {
    title: '帧寻是什么',
    body: [
      '帧寻（GongJ!ng?）是一个视频与图文理解助手。它把视频拆成关键帧，转写语音，识别画面上的文字，再根据这些内容回答你的问题。',
      '最擅长的是软件教程：哪一步点了什么按钮、为什么这么设置、跟着做卡在哪里。知识讲解和生活类视频也可以问。',
    ],
  },
  {
    title: '三步上手',
    list: [
      '导入：粘贴 B 站链接，或上传本地视频 / 图片，点「开始解析」。抽帧、语音转写、画面文字识别会同时进行，一般一两分钟。',
      '提问：在对话框里直接问。可以先点推荐问题；也可以在时间轴上选几帧，只针对这几帧提问。',
      '回看：回答里的证据标签可以点，点了就跳到原片那一刻；上传的视频还能慢放某一段。',
    ],
  },
  {
    title: '证据标签怎么看',
    chips: [
      ['frame', '画面 00:56', '原片画面，看得到的操作和界面'],
      ['speech', '原声 00:54', '视频里说的话（语音转写）'],
      ['screentext', '画面文字 00:55', '画面上出现的字（文字识别）'],
      ['source', '资料 · 链接', '视频之外查到的资料'],
      ['inference', '推断', '没有直接证据，是推出来的判断'],
    ],
    after: '每个标签的时间都会自动核对：对不上视频内容的会变灰，提醒你不要直接相信。',
  },
  {
    title: '账号与次数（网页版）',
    list: [
      '不登录可以浏览首页；导入视频和提问需要登录。可以用用户名注册，也可以用 GitHub 登录。',
      '免费账号每天可以导入 3 个视频、提问 10 次，北京时间 0 点重置。链接解析失败不算次数。',
      '登录后，在其他电脑或手机上登录同一个账号，历史会话都在。',
    ],
  },
  {
    title: '支持的来源',
    list: [
      '网页版：B 站链接，以及本地上传的视频和图片。',
      '其他平台（视频号、抖音、小红书等）的视频，可以先下载，再用「上传文件」导入。',
    ],
  },
  {
    title: '数据与隐私',
    list: [
      '你导入的视频和对话只有你自己能看到，其他账号打不开。',
      '上传的视频保存在云存储中，供回看使用；在会话里可以随时删除原视频或整个会话，删除后一并清除。',
      'B 站视频不会下载保存，回看时直接从 B 站读取。',
    ],
  },
]

export default function DocsDialog({ onClose, onGuide }) {
  return createPortal(
    <div className="overlay guide-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <section className="docs" role="dialog" aria-modal="true" aria-label="使用文档">
        <header className="docs__head">
          <strong><IconBook size={14} /> 使用文档</strong>
          <div className="docs__actions">
            {onGuide ? <button type="button" className="btn btn--ghost" onClick={onGuide}>重新看新手引导</button> : null}
            <button type="button" className="icon-btn" onClick={onClose} aria-label="关闭"><IconClose size={14} /></button>
          </div>
        </header>
        <div className="docs__body">
          {SECTIONS.map((s) => (
            <section key={s.title} className="docs__section">
              <h2>{s.title}</h2>
              {s.body?.map((p) => <p key={p}>{p}</p>)}
              {s.list ? <ol>{s.list.map((li) => <li key={li}>{li}</li>)}</ol> : null}
              {s.chips ? (
                <dl className="docs__chips">
                  {s.chips.map(([kind, label, meaning]) => (
                    <div key={kind}><dt><span className={`ev-chip ev-chip--${kind}`}>{label}</span></dt><dd>{meaning}</dd></div>
                  ))}
                </dl>
              ) : null}
              {s.after ? <p>{s.after}</p> : null}
            </section>
          ))}
        </div>
      </section>
    </div>,
    document.body,
  )
}
