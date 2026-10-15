import * as THREE from 'three'
import { SCULPTURE_SETTINGS } from '../config/workspace.js'
import { buildShapePoses, composeMobiusMatrix, composeRibbonMatrix } from './sculptureShapes.js'

// Parametric slat ribbon (design_2.md §7.1, art direction: Rhine Lab PV).
// Shared by the WebGL renderer, the static SVG fallback and the DOM timeline.
export const TAU = Math.PI * 2
// width = slat depth, height = ribbon width (across the band), thickness = along the curve
export const SHEET = { width: 3.2, height: 6.8, thickness: 0.065 }
export const SCULPTURE_VIEW = { x: 0.14, y: -0.12, z: -0.06 }
export const TWIST_SPEED = 0.15 // rad/s
export const BREATH = { amplitude: 0.22, period: 8 }

const CONTROL_POINTS = 24
const LOBE_X = 11.2
const LOBE_Y = 6.7
const CROSS_Z = 3.6

// 3D figure-eight: the two lobes pass in front of / behind each other at the crossing.
function loopPoint(u) {
  const t = u * TAU
  return new THREE.Vector3(LOBE_X * Math.sin(t), LOBE_Y * Math.sin(2 * t), CROSS_Z * Math.cos(t) + 0.8 * Math.sin(3 * t))
}

export function buildCurve() {
  const pts = []
  for (let i = 0; i < CONTROL_POINTS; i += 1) pts.push(loopPoint(i / CONTROL_POINTS))
  return new THREE.CatmullRomCurve3(pts, true, 'centripetal')
}

// Twist of a cross-section. Integer turn count keeps it continuous across the loop seam,
// so slat normals never flip abruptly.
export function twistAngle(u, time) {
  return TAU * u + TWIST_SPEED * time + 0.55 * Math.sin(TAU * 2 * u - TWIST_SPEED * 2 * time)
}

// Keep a substantial cross-section even at the narrowest point of the wave.
export function bandScale(u, time) {
  return 0.96 + 0.14 * Math.sin(TAU * 2 * u + 0.6 + 0.12 * time)
}

export function breathOffset(u, time) {
  return BREATH.amplitude * Math.sin((TAU * time) / BREATH.period + TAU * 2 * u)
}

// A travelling wave where slats fan out of the band and scatter, then fold back in.
export function fanAmount(u, time) {
  const s = Math.sin(TAU * u - 0.11 * time)
  return s > 0 ? s ** 8 : 0
}

// Precompute positions + rotation-minimizing frames (three's computeFrenetFrames does
// parallel transport and spreads the closing correction along a closed curve).
export function sampleSheets(count, wordPoses = []) {
  const curve = buildCurve()
  const frames = curve.computeFrenetFrames(count, true)
  const sheets = []
  const shapePoses = buildShapePoses(count)
  for (let i = 0; i < count; i += 1) {
    const u = i / count
    sheets.push({
      u,
      // per-slat jitter so the scattered part reads as individual pieces
      jitter: Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1,
      position: curve.getPointAt(u),
      tangent: frames.tangents[i].clone(),
      normal: frames.normals[i].clone(),
      binormal: frames.binormals[i].clone(),
      scatterPosition: new THREE.Vector3(
        (((i * 0.61803398875) % 1) * 2 - 1) * SCULPTURE_SETTINGS.scatter.width,
        (((i * 0.754877666) % 1) * 2 - 1) * SCULPTURE_SETTINGS.scatter.height,
        (((i * 0.569840291) % 1) * 2 - 1) * SCULPTURE_SETTINGS.scatter.depth,
      ),
      scatterRotation: new THREE.Quaternion().setFromEuler(new THREE.Euler(
        Math.sin(i * 2.4) * 0.7, Math.cos(i * 1.7) * 0.9, Math.sin(i * 0.8) * Math.PI,
      )),
      shapes: shapePoses[i],
      words: wordPoses.map((poses) => poses[i]),
    })
  }
  return sheets
}

const _a = new THREE.Vector3()
const _e = new THREE.Vector3()
const _t = new THREE.Vector3()
const _tmp = new THREE.Vector3()
const _p = new THREE.Vector3()
const _q = new THREE.Quaternion()
const _scale = new THREE.Vector3()
const _scatterScale = new THREE.Vector3().setScalar(SCULPTURE_SETTINGS.scatter.scale)

// Write the instance matrix for one slat at a given time.
export function composeSheetMatrix(sheet, time, animated, out, spread = 0, shape = 'infinity', wordIndex) {
  if (shape !== 'infinity' && sheet.shapes[shape]) {
    const pose = sheet.shapes[shape]
    if (shape === 'mobius' && animated) composeMobiusMatrix(sheet.u, time, out)
    else if (pose.normal) composeRibbonMatrix(pose, sheet.u, time, animated, out)
    else out.compose(pose.position, pose.quaternion, pose.scale)
    return scatterMatrix(sheet, time, animated, out, spread, wordIndex)
  }
  const { u } = sheet
  const theta = twistAngle(u, time)
  const c = Math.cos(theta)
  const s = Math.sin(theta)
  // a: across-band axis; e: slat depth axis; e × a = tangent (right-handed basis)
  _a.copy(sheet.normal).multiplyScalar(c).addScaledVector(sheet.binormal, s)
  _e.copy(sheet.normal).multiplyScalar(s).addScaledVector(sheet.binormal, -c)
  _t.copy(sheet.tangent)
  _p.copy(sheet.position)

  if (animated) {
    _p.addScaledVector(sheet.normal, breathOffset(u, time))
    const fan = fanAmount(u, time)
    if (fan > 0.001) {
      // rotate the slat about its across-band axis and push it out of the band
      const phi = fan * (0.32 + 0.12 * sheet.jitter)
      const cp = Math.cos(phi)
      const sp = Math.sin(phi)
      _tmp.copy(_t)
      _t.multiplyScalar(cp).addScaledVector(_e, sp)
      _e.multiplyScalar(cp).addScaledVector(_tmp, -sp)
      _p.addScaledVector(_e, fan * (0.4 + 0.35 * sheet.jitter))
      _p.addScaledVector(_a, fan * (sheet.jitter - 0.5) * 0.5)
    }
  }
  _a.multiplyScalar(animated ? bandScale(u, time) : 1)
  out.makeBasis(_e, _a, _t)
  out.setPosition(_p)
  return scatterMatrix(sheet, time, animated, out, spread, wordIndex)
}

function scatterMatrix(sheet, time, animated, out, spread, wordIndex) {
  if (spread > 0) {
    out.decompose(_p, _q, _scale)
    const word = sheet.words[wordIndex]
    _p.lerp(word ? word.position : sheet.scatterPosition, spread)
    if (animated) {
      const drift = word ? SCULPTURE_SETTINGS.scatterText.drift : 0.35
      _p.x += Math.sin(time * 0.3 + sheet.u * TAU) * drift * spread
      _p.y += Math.cos(time * 0.25 + sheet.u * TAU) * drift * spread
    }
    _q.slerp(word ? word.rotation : sheet.scatterRotation, spread)
    _scale.lerp(word ? word.scale : _scatterScale, spread)
    out.compose(_p, _q, _scale)
  }
  return out
}
