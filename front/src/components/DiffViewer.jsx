import React from 'react'

// §9.2 file.edit.diff — unified diff.
export default function DiffViewer({ path, diff }) {
  const lines = diff.split('\n')
  return (
    <div className="diff">
      <div className="diff__head">{path}</div>
      <pre className="diff__body">
        {lines.map((line, i) => {
          const kind = line.startsWith('@@') ? 'hunk' : line[0] === '+' ? 'added' : line[0] === '-' ? 'removed' : 'context'
          return <div key={i} className={`diff__line diff__line--${kind}`}>{line || ' '}</div>
        })}
      </pre>
    </div>
  )
}
