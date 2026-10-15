import { fmtTime, frameNo } from '../lib/format'

const wait = (ms, signal) =>
  new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('aborted', 'AbortError')) })
  })

export async function mockUpload(file, { onProgress, signal } = {}) {
  // long enough to show at least one full contour cycle
  const total = Math.min(7000, 4600 + (file?.size || 0) / 40000)
  const start = performance.now()
  for (;;) {
    const p = Math.min(1, (performance.now() - start) / total)
    onProgress?.(p)
    if (p >= 1) break
    await wait(60, signal)
  }
  return { video_id: `vid_${Date.now().toString(36)}` }
}

// Scripted run that exercises every §9.2 event type. The branch is chosen by the question
// so the demo prompts can show browser use and file diffs.
export async function mockAgentRun(request, emit, signal) {
  const { question, frames, scope, coverage } = request
  const run_id = `run_${Date.now().toString(36)}`
  const started = performance.now()
  const wantsBrowser = /搜|查|网|浏览|browser|search/i.test(question)
  const wantsReport = /报告|笔记|文档|report|写/i.test(question)
  const range = scope.type === 'all'
    ? '整段视频'
    : `${frames.length} 帧 (${frames.map((f) => frameNo(f.index)).slice(0, 4).join(', ')}${frames.length > 4 ? ' …' : ''})`
  let steps = 0
  const send = async (event, delay = 0) => {
    if (delay) await wait(delay, signal)
    emit({ run_id, ...event })
  }
  const tool = async (call_id, tool_name, input, output, resultCount, delays = [200, 700]) => {
    steps += 1
    await send({ type: 'tool_call.started', call_id, tool_name }, delays[0])
    await send({ type: 'tool_call.input', call_id, input }, 160)
    await send({ type: 'tool_call.output', call_id, ...output }, delays[1])
    await send({ type: 'tool_call.completed', call_id, result_count: resultCount }, 180)
  }

  await send({ type: 'progress.update', step: '解析问题', percent: 8 }, 300)
  await tool('c1', 'frame_index.search', {
    kind: 'params',
    params: { query: question, scope: range, top_k: 8 },
  }, { stdout: (frames.slice(0, 6).map((f, i) => `${frameNo(f.index)}  ${fmtTime(f.time)}  score=${(0.92 - i * 0.07).toFixed(2)}`)).join('\n'), exit_code: 0 }, Math.min(6, frames.length))

  await send({ type: 'progress.update', step: '读取关键帧', percent: 34 })
  await tool('c2', 'bash', {
    kind: 'bash',
    command: `ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 input.mp4`,
  }, { stdout: 'h264,1920,1080,30/1\naac', exit_code: 0 }, 2)

  await tool('c3', 'vision.describe_frames', {
    kind: 'params',
    params: { frames: frames.slice(0, 4).map((f) => frameNo(f.index)).join(', '), detail: 'high' },
  }, { stdout: '4 帧描述已生成，平均置信度 0.87', exit_code: 0 }, 4, [200, 1100])

  if (wantsBrowser) {
    await send({ type: 'progress.update', step: '浏览网页核实', percent: 58 })
    steps += 1
    const call_id = 'c4'
    await send({ type: 'tool_call.started', call_id, tool_name: 'browser.use' }, 200)
    await send({ type: 'tool_call.input', call_id, input: { kind: 'params', params: { task: '核实视频中出现的信息', engine: 'chromium' } } }, 150)
    await send({ type: 'browser.open', call_id, url: 'https://www.bing.com/' }, 200)
    const actions = [
      { action: 'navigate', detail: 'https://www.bing.com/', x: 0.5, y: 0.1 },
      { action: 'click', detail: '(640, 212)', x: 0.5, y: 0.32 },
      { action: 'type', detail: `'${question.slice(0, 24)}'`, x: 0.5, y: 0.32 },
      { action: 'click', detail: '(412, 388)', x: 0.32, y: 0.56 },
      { action: 'navigate', detail: 'https://example.com/article', x: 0.32, y: 0.56, url: 'https://example.com/article' },
    ]
    for (const a of actions) await send({ type: 'browser.action', call_id, ...a }, 900)
    await send({ type: 'tool_call.output', call_id, stdout: '已打开 1 个页面，提取 3 段相关文字', exit_code: 0 }, 600)
    await send({ type: 'tool_call.completed', call_id, result_count: 3 }, 150)
  }

  if (wantsReport) {
    await send({ type: 'progress.update', step: '写入分析报告', percent: 76 })
    steps += 1
    const call_id = 'c5'
    await send({ type: 'tool_call.started', call_id, tool_name: 'file.edit' }, 200)
    await send({ type: 'tool_call.input', call_id, input: { kind: 'params', params: { path: 'reports/summary.md' } } }, 160)
    await send({
      type: 'file.edit.diff',
      call_id,
      path: 'reports/summary.md',
      diff: [
        '@@ -1,4 +1,7 @@',
        ' # 视频分析报告',
        ' ',
        `-范围：待定`,
        `+范围：${range}`,
        '+',
        '+## 关键片段',
        `+- ${fmtTime(frames[0]?.time ?? 0)} 开场，主体出现`,
        ` 生成时间：${new Date().toISOString().slice(0, 10)}`,
      ].join('\n'),
    }, 700)
    await send({ type: 'tool_call.output', call_id, stdout: 'reports/summary.md  +4 −1', exit_code: 0 }, 200)
    await send({ type: 'tool_call.completed', call_id, result_count: 1 }, 150)
  }

  await send({ type: 'progress.update', step: '生成回答', percent: 92 }, 200)
  const first = frames[0]
  const last = frames[frames.length - 1]
  const answer = [
    `基于${scope.type === 'all' ? '整段视频' : `所选的 ${frames.length} 帧`}（${fmtTime(first?.time)} – ${fmtTime(last?.time)}），这是当前的理解：`,
    '',
    `1. 开场 ${fmtTime(first?.time)} 附近画面以主体介绍为主，镜头稳定。`,
    `2. 中段出现主要信息变化，关键帧 ${frameNo(frames[Math.floor(frames.length / 2)]?.index ?? 0)} 是转折点。`,
    `3. 结尾 ${fmtTime(last?.time)} 对前文进行收束。`,
    ...(coverage?.missing_ranges?.length
      ? ['', `注意：${coverage.missing_ranges.map(([a, b]) => `${fmtTime(a)}–${fmtTime(b)}`).join('、')} 没有取到画面，以上结论不覆盖这些时段。`]
      : []),
    ...(frames.length ? [] : ['', '目前没有可用的画面，以上只能基于视频标题和简介推断。']),
    '',
    '（当前为前端模拟数据，接入后端后将替换为真实分析结果。）',
  ].join('\n')
  for (let i = 0; i < answer.length; i += 3) {
    await send({ type: 'assistant.message.delta', delta: answer.slice(i, i + 3) }, 24)
  }
  await send({
    type: 'run.completed',
    steps,
    elapsed_ms: performance.now() - started,
    summary: [wantsBrowser && '浏览 1 页', wantsReport && '改动 1 个文件', `检索 ${frames.length} 帧`].filter(Boolean).join(' · '),
  }, 200)
}
