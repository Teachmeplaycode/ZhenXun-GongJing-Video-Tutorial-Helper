import React, { memo, useMemo } from 'react'
import katex from 'katex'
import { formulaSource, splitMath } from '../lib/math'
import 'katex/dist/katex.min.css'
import '../styles/math.css'

export const MathFormula = memo(function MathFormula({ text, display = false }) {
  const tex = formulaSource(text)
  const html = useMemo(() => katex.renderToString(tex, {
    throwOnError: false, displayMode: display, output: 'htmlAndMathml', trust: false,
    strict: 'ignore', maxExpand: 1000, maxSize: 20,
  }), [tex, display])
  return <span className={`math-tex${display ? ' math-tex--display' : ''}`} dangerouslySetInnerHTML={{ __html: html }} />
})

// Notes' editable fields keep their original source; this only changes their read view.
export default function MathText({ text }) {
  return splitMath(text).map((part, i) => part.type === 'math'
    ? <MathFormula key={i} text={part.text} display={part.display} /> : <React.Fragment key={i}>{part.text}</React.Fragment>)
}
