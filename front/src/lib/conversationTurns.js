import { fmtTime } from './format.js'

// UI keys stay unchanged when durable ids arrive. Match duplicate questions in saved order,
// including the independent command metadata, rather than replacing the live conversation.
export function withSavedIds(messages, saved) {
  let cursor = 0
  return messages.map((message) => {
    if (message.status === 'running') return { ...message, savedId: null }
    const index = saved.findIndex((row, i) => i >= cursor && row.role === message.role
      && (message.savedId != null ? row.id === message.savedId
        : (row.manual || null) === (message.manual || null)
          && (row.content || '') === (message.text || '')
          && (message.role !== 'user' || (row.command || null) === (message.command || null))))
    if (index < 0) return { ...message, savedId: null }
    cursor = index + 1
    return { ...message, savedId: saved[index].id, savedStatus: saved[index].status }
  })
}

const REPORT_NAMES = { 'skill.factcheck': '科普核查报告', 'skill.antifraud': '反诈识别报告', 'skill.recipe': '节点图报告' }
function answerPreview(answer) {
  if ((answer?.text || '').trim()) return answer.text
  const names = new Set((answer?.parts || []).filter((part) => part.kind === 'steps')
    .flatMap((part) => part.calls || []).filter((call) => REPORT_NAMES[call.tool] && call.data?.report
      && call.status === 'done' && !call.exitCode).map((call) => REPORT_NAMES[call.tool]))
  return names.size ? `包含${[...names].join('、')}` : ''
}

function describe(turn) {
  const { user, answer, kind } = turn
  const preview = answerPreview(answer)
  const ids = [user?.savedId, answer?.savedId].filter((id) => id != null)
  let reason = ''
  if (kind !== 'qa') reason = '画面操作可跳转，笔记仅选择完整问答'
  else if (!user) reason = '缺少对应问题'
  else if (answer?.status === 'running') reason = '正在回答'
  else if (!answer) reason = '等待回答'
  else if (['error', 'failed', 'stopped'].includes(answer.status)
    || ['error', 'failed', 'stopped'].includes(answer.savedStatus)) reason = '回答未完成'
  else if (user.savedId == null || answer.savedId == null) reason = '尚未保存'
  else if (!preview) reason = '没有可整理的回答'
  const status = answer?.status === 'running' ? 'running'
    : ['error', 'failed', 'stopped'].includes(answer?.status) ? 'error' : reason ? 'pending' : 'done'
  return { ...turn, ids, selectable: !reason, reason, status, answerPreview: preview,
    question: user?.text || '', anchorId: (user || answer).id,
    title: turn.title || user?.text || (user?.command ? `/${user.command}` : '') || answer?.text || '问答' }
}

/** All visible conversation turns, separate from whether a turn can be used in notes/exports. */
export function conversationTurns(messages) {
  const turns = []
  for (let i = 0; i < messages.length; i += 1) {
    const m = messages[i]
    const next = messages[i + 1]
    if (m.role === 'user' && next?.manual === 'clip') {
      turns.push(describe({ key: m.id, kind: 'clip', user: m, answer: next, title: m.text || '生成视频片段' }))
      i += 1
    } else if (m.manual === 'clip') {
      turns.push(describe({ key: m.id, kind: 'clip', answer: m, title: '生成视频片段' }))
    } else if (m.manual === 'replay') {
      const replay = m.parts?.flatMap((part) => part.calls || []).find((call) => call.tool === 'frames.replay')?.data
      const [start, end] = m.range || [replay?.start, replay?.end]
      const title = start != null && end != null ? `手动慢放 ${fmtTime(start)}–${fmtTime(end)}` : '手动慢放'
      turns.push(describe({ key: m.id, kind: 'replay', answer: m, title }))
    } else if (m.role === 'user') {
      const answer = next?.role === 'assistant' && !next.manual ? next : null
      turns.push(describe({ key: m.id, kind: 'qa', user: m, answer }))
      if (answer) i += 1
    } else if (m.role === 'assistant') {
      turns.push(describe({ key: m.id, kind: 'qa', answer: m }))
    }
  }
  return turns.map((turn, i) => ({ ...turn, number: i + 1 }))
}

// Existing Q&A exports still include hand-framed replays, and keep their own selection defaults.
export function exportItems(messages) {
  return conversationTurns(messages).filter((turn) => turn.kind !== 'clip').map((turn) => ({
    ...turn, kind: turn.kind === 'replay' ? 'manual' : 'qa',
    pending: turn.answer?.status === 'running' || (turn.user && turn.user.savedId == null)
      || (turn.answer ? turn.answer.savedId == null : true),
  }))
}
