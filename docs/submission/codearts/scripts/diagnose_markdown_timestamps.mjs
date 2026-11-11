// Stage-03 (93bcda8) 时间戳渲染行为诊断：实际调用 front/src/lib/markdown.jsx 的 renderMarkdown，
// 检查产出 React 元素（不是构建通过代替行为验证）。
// 运行：node diag_markdown_times.mjs（在 repro-stage-03/front 下，依赖其 node_modules）
import { transformSync } from 'esbuild'
import { readFileSync, writeFileSync } from 'node:fs'
import React from 'react'

const SRC = '/workspace/repro-stage-03/front/src/lib/markdown.jsx'
const OUT = '/workspace/repro-stage-03/front/.diag-markdown.mjs'
const js = transformSync(readFileSync(SRC, 'utf8'), { loader: 'jsx', format: 'esm' }).code
writeFileSync(OUT, js)
const { renderMarkdown, toSeconds } = await import(OUT)

const CLICKS = []
const onTime = (s) => CLICKS.push(s)

// 把 React 元素树压成紧凑描述：btn[01:23→83s] 表示会渲染成可点击时间按钮
function describe(node) {
  if (node == null || node === false) return ''
  if (typeof node === 'string') return JSON.stringify(node)
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(describe).filter(Boolean).join(' ')
  const { type, props } = node
  if (type === 'button') {
    return `btn[${props.children}→${toSeconds(props.children)}s${props.onClick ? '' : ',无onClick'}]`
  }
  if (type === 'code') return `code[${describe(props.children)}]`
  if (type === 'strong') return `bold(${describe(props.children)})`
  if (type === 'em') return `em(${describe(props.children)})`
  if (type === 'br') return '⏎'
  if (typeof type === 'string') return describe(props.children) // p / div / Fragment 包装，只看内容
  return describe(props.children)
}

const CASES = [
  { tag: '正文 [01:23]', text: '她在 [01:23] 开始画眼妆' },
  { tag: '正文 06:10（无括号）', text: '06:10 左右镜头切到特写' },
  { tag: '正文 1:02:03（时:分:秒）', text: '到 1:02:03 时总结开始' },
  { tag: '行内代码 `01:23`', text: '时间戳 `01:23` 是行内代码' },
  { tag: 'fenced 代码块里的时间', text: '用这个命令截帧：\n```\nffmpeg -ss 00:01:23 -i in.mp4 -frames:v 1 out.jpg\n```' },
  { tag: 'URL 参数里的冒号 t=1:23', text: '看 https://example.com/watch?t=1:23 这一段' },
  { tag: 'URL 端口 127.0.0.1:8080', text: '服务在 http://127.0.0.1:8080/api 健康检查' },
  { tag: '宽高比 16:9', text: '画面比例是 16:9 没错' },
  { tag: '上下文紧邻数字 10:301', text: '编号 10:301 是编号不是时间' },
]

function run(tag, text, duration) {
  const els = renderMarkdown(text, { onTime, duration })
  const rendered = els.map(describe).join(' | ')
  const hasBtn = rendered.includes('btn[')
  console.log(`\n--- ${tag} · duration=${duration}s ---`)
  console.log(`输入: ${JSON.stringify(text)}`)
  console.log(`产出: ${rendered}`)
  console.log(`含时间按钮: ${hasBtn ? '是 ⚠️' : '否'}`)
  return hasBtn
}

console.log('== 场景一：10 分钟视频（duration=600），onTime 提供 ==')
const s1 = CASES.map((c) => run(c.tag, c.text, 600))

console.log('\n== 场景二：2 小时视频（duration=7200），同一批输入 ==')
const s2 = CASES.map((c) => run(c.tag, c.text, 7200))

console.log('\n== 场景三：无 onTime（只读展示，如纯文本导出） ==')
;(function noOnTime() {
  const els = renderMarkdown('她在 [01:23] 开始', { onTime: null, duration: 600 })
  console.log('输入: "她在 [01:23] 开始" · onTime=null · duration=600')
  console.log(`产出: ${els.map(describe).join(' | ')}  ← 纯文本，括号原样保留`)
})()

console.log('\n== 点击行为 ==')
renderMarkdown('看 [02:30] 这里', { onTime, duration: 600 })
console.log(`onClick 触发记录: ${JSON.stringify(CLICKS)}`)

console.log('\n== 总结论 ==')
const verdict = (i, name) => `  ${name}: 600s=${s1[i] ? '按钮' : '文本'} / 7200s=${s2[i] ? '按钮' : '文本'}`
console.log(verdict(0, '正文[01:23]      '))
console.log(verdict(1, '正文06:10        '))
console.log(verdict(2, '正文1:02:03      '))
console.log(verdict(3, '行内代码`01:23`  '))
console.log(verdict(4, 'fenced块内时间    '))
console.log(verdict(5, 'URL t=1:23       '))
console.log(verdict(6, 'URL :8080 端口   '))
console.log(verdict(7, '宽高比16:9       '))
console.log(verdict(8, '紧邻数字10:301   '))
