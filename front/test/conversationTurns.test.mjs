import test from 'node:test'
import assert from 'node:assert/strict'
import { conversationTurns, withSavedIds, exportItems } from '../src/lib/conversationTurns.js'

const question = (id, text, extra = {}) => ({ id, role: 'user', text, ...extra })
const answer = (id, text, extra = {}) => ({ id, role: 'assistant', text, status: 'done', ...extra })

test('duplicate questions retain their UI keys while matching durable rows in order', () => {
  const messages = [question('q1', '为什么'), answer('a1', '第一个回答'), question('q2', '为什么'), answer('a2', '第二个回答')]
  const saved = messages.map((m, i) => ({ id: i + 1, role: m.role, content: m.text, status: 'done' }))
  const turns = conversationTurns(withSavedIds(messages, saved))
  assert.deepEqual(turns.map((t) => [t.key, t.ids, t.selectable]), [['q1', [1, 2], true], ['q2', [3, 4], true]])
})

test('a command-only question matches the independent command metadata', () => {
  const rows = [{ id: 1, role: 'user', content: '', command: '总结' }, { id: 2, role: 'user', content: '', command: '卡点' }]
  const [mapped] = withSavedIds([question('q', '', { command: '卡点' })], rows)
  assert.equal(mapped.savedId, 2)
  assert.equal(conversationTurns([mapped])[0].title, '/卡点')
})

test('running, failed, unsaved and incomplete turns are navigable but cannot enter notes', () => {
  const turns = conversationTurns([
    question('q1', '运行中', { savedId: 1 }), answer('a1', '半句', { savedId: 2, status: 'running' }),
    question('q2', '失败', { savedId: 3 }), answer('a2', '半句', { savedId: 4, status: 'error' }),
    question('q3', '未保存'), answer('a3', '完成'), question('q4', '等待回答', { savedId: 5 }),
  ])
  assert.equal(turns.length, 4)
  assert.deepEqual(turns.map((t) => t.reason), ['正在回答', '回答未完成', '尚未保存', '等待回答'])
  assert.ok(turns.every((t) => !t.selectable))
  assert.deepEqual(turns.map((t) => t.anchorId), ['q1', 'q2', 'q3', 'q4'])
})

test('manual replays and GIF cards get anchors without becoming note material', () => {
  const turns = conversationTurns([
    question('q', '片段'), answer('clip', '', { manual: 'clip', savedId: 1 }),
    answer('replay', '', { manual: 'replay', savedId: 2, range: [60, 61] }),
    question('q2', '分析', { savedId: 3 }), answer('a2', '分析内容', { savedId: 4 }),
  ])
  assert.deepEqual(turns.map((t) => t.kind), ['clip', 'replay', 'qa'])
  assert.deepEqual(turns.map((t) => t.selectable), [false, false, true])
  assert.equal(turns[1].title, '手动慢放 01:00.0–01:01.0')
  const exported = exportItems([
    question('q', '片段'), answer('clip', '', { manual: 'clip', savedId: 1 }),
    answer('replay', '', { manual: 'replay', savedId: 2, range: [60, 61] }),
    question('q2', '分析', { savedId: 3 }), answer('a2', '分析内容', { savedId: 4 }),
  ])
  assert.deepEqual(exported.map((t) => [t.kind, t.ids, t.pending]), [['manual', [2], false], ['qa', [3, 4], false]])
})

test('the streaming answer never inherits a saved id from an older identical response', () => {
  const [mapped] = withSavedIds([answer('live', '相同内容', { status: 'running', savedId: 2 })], [{ id: 2, role: 'assistant', content: '相同内容' }])
  assert.equal(mapped.savedId, null)
})

test('an orphan answer is never selectable as a complete Q&A', () => {
  const [turn] = conversationTurns([answer('orphan', '回答', { savedId: 1 })])
  assert.equal(turn.selectable, false)
  assert.equal(turn.reason, '缺少对应问题')
})


test('completed skill reports are usable notes even without assistant prose', () => {
  for (const [tool, label] of [['skill.factcheck', '科普核查报告'], ['skill.antifraud', '反诈识别报告'], ['skill.recipe', '节点图报告']]) {
    const parts = [{ kind: 'steps', calls: [{ tool, status: 'done', exitCode: 0, data: { report: { summary: {} } } }] }]
    const [turn] = conversationTurns([question('q', '请核查', { savedId: 1 }), answer('a', '', { savedId: 2, parts })])
    assert.equal(turn.selectable, true)
    assert.equal(turn.answerPreview, `包含${label}`)
  }
})

test('an incomplete or failed skill report cannot stand in for a completed answer', () => {
  for (const [status, exitCode] of [['running', 0], ['error', 1]]) {
    const parts = [{ kind: 'steps', calls: [{ tool: 'skill.factcheck', status, exitCode, data: { report: {} } }] }]
    const [turn] = conversationTurns([question('q', '核查', { savedId: 1 }), answer('a', '', { savedId: 2, parts })])
    assert.equal(turn.selectable, false)
  }
})
