import test from 'node:test'
import assert from 'node:assert/strict'
import { splitMath, formulaSource } from '../src/lib/math.js'

const math = (text) => splitMath(text).filter((part) => part.type === 'math')
test('recognizes the four TeX delimiters and numeric expressions', () => {
  assert.deepEqual(math(String.raw`$x_1$ \(a<\xi<b\) $$\frac{1}{x}$$ \[\lim_n a_n\] $2x+1$`).map((part) => [part.text, part.display]), [
    ['x_1', false], [String.raw`a<\xi<b`, false], [String.raw`\frac{1}{x}`, true], [String.raw`\lim_n a_n`, true], ['2x+1', false],
  ])
})
test('leaves incomplete streaming input literal, then renders the completed formula', () => {
  assert.deepEqual(math(String.raw`开始 $\frac{1}{x}`), [])
  assert.equal(math(String.raw`开始 $\frac{1}{x}$`)[0].text, String.raw`\frac{1}{x}`)
  assert.deepEqual(math('$$\nx^2'), [])
  assert.equal(math('$$\nx^2\n$$')[0].display, true)
})
test('preserves code, links, escaped dollars and currency while finding later math', () => {
  for (const text of ['`$x$`', '```latex\n$$x$$\n```', 'https://example.com/$x$', String.raw`\$x\$`, '价格 $20 和 $30']) assert.deepEqual(math(text), [])
  assert.deepEqual(math('价格 $20 和 $30，公式 $x^2$').map((part) => part.text), ['x^2'])
})
test('normalizes existing formula fields without changing their source data', () => {
  for (const text of ['$x^2$', '$$x^2$$', String.raw`\(x^2\)`, String.raw`\[x^2\]`, 'x^2']) assert.equal(formulaSource(text), 'x^2')
})
