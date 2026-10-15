import React, { useMemo } from 'react'
import * as THREE from 'three'
import { SCULPTURE_SETTINGS } from '../config/workspace'
import { SHEET, SCULPTURE_VIEW, sampleSheets, composeSheetMatrix } from '../lib/sculptureMath'

// Static SVG rendering of the sculpture for browsers without WebGL (§7.1 webgl_fallback).
// Project the broad face of every sheet so the fallback retains the same volume.
export default function SculptureFallback({ className = '', spread = 0, align = 'center' }) {
  const faces = useMemo(() => {
    const sheets = sampleSheets(220)
    const rot = new THREE.Euler(SCULPTURE_VIEW.x, SCULPTURE_VIEW.y, SCULPTURE_VIEW.z)
    const out = []
    const matrix = new THREE.Matrix4()
    const corners = [
      [-SHEET.width / 2, -SHEET.height / 2],
      [SHEET.width / 2, -SHEET.height / 2],
      [SHEET.width / 2, SHEET.height / 2],
      [-SHEET.width / 2, SHEET.height / 2],
    ]
    for (const s of sheets) {
      composeSheetMatrix(s, 0, true, matrix, spread)
      const points = corners.map(([x, y]) => new THREE.Vector3(x, y, 0).applyMatrix4(matrix).applyEuler(rot))
      out.push({ points: points.map((p) => `${p.x},${-p.y}`).join(' '), z: points.reduce((sum, p) => sum + p.z, 0) / points.length })
    }
    return out.sort((l, r) => l.z - r.z)
  }, [spread])

  return (
    <div className={`sculpture sculpture--fallback ${className}`}>
      <svg viewBox="-22 -13.5 44 27" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        <g transform={`translate(${align === 'side' ? SCULPTURE_SETTINGS.sideOffset : 0}, 0)`}>
          {faces.map((face, i) => (
            <polygon
              key={i}
              points={face.points}
              strokeWidth={0.035}
              style={{ fillOpacity: THREE.MathUtils.clamp(0.65 + face.z / 40, 0.35, 1) }}
            />
          ))}
        </g>
      </svg>
    </div>
  )
}
