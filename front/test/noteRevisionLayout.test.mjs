import test from 'node:test'
import assert from 'node:assert/strict'
import { settleRevision } from '../src/notes/layout.js'

test('expanded revision pushes only obstructed content and preserves edited columns, sizes and unrelated annotations', () => {
  const blocks = [
    { id: 'sec-a', type: 'section', x: 120, y: 10, w: 450 },
    { id: 'sec-b', type: 'section', x: 120, y: 180, w: 450 },
    { id: 'pic-b', type: 'figure', section: 'sec-b', x: 650, y: 190, w: 300 },
    { id: 'annotation', type: 'text', text: '我的批注', x: 1100, y: 180, w: 200 },
    { id: 'sec-c', type: 'section', x: 120, y: 350, w: 450 },
  ]
  const result = settleRevision(blocks, { 'sec-a': 400, 'sec-b': 130, 'pic-b': 80, annotation: 100, 'sec-c': 140 }, ['sec-a'])
  assert.equal(result[1].y, 430)
  assert.equal(result[2].y, 440)
  assert.equal(result[4].y, 580)
  assert.deepEqual(result[3], blocks[3])
  assert.equal(result[1].x, 120)
  assert.equal(result[1].w, 450)
  assert.equal(blocks[1].y, 180)
})

test('new material respects measured height of the preceding handwritten section', () => {
  const blocks = [
    { id: 'old', type: 'section', x: 20, y: 0, w: 500 },
    { id: 'new', type: 'section', x: 20, y: 350, w: 500 },
    { id: 'side', type: 'text', x: 700, y: 0, w: 300 },
  ]
  const result = settleRevision(blocks, { old: 700, new: 200, side: 100 }, ['new'])
  assert.equal(result[1].y, 720)
  assert.deepEqual(result[0], blocks[0])
  assert.deepEqual(result[2], blocks[2])
})
