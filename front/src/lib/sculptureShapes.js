import * as THREE from 'three'
import { SCULPTURE_SETTINGS } from '../config/workspace.js'

export const SHAPE_LABELS = {
  infinity: { name: '无穷环', code: 'INFINITY / ∞' },
  mobius: { name: '莫比乌斯环', code: 'MÖBIUS / ½ TURN' },
  trefoil: { name: '三叶结', code: 'TREFOIL / 3 LOBES' },
  waveRing: { name: '双扭波环', code: 'WAVE LOOP / 2 CRESTS' },
}

const TAU = Math.PI * 2
const smooth = (t) => t * t * (3 - 2 * t)

// A phrase is shared by the outgoing and incoming shape within each segment.
export function morphStateAt(time, settings = SCULPTURE_SETTINGS.morph) {
  const { shapes, scatterDuration, scatterHold, assembleDuration, shapeHold } = settings
  const duration = scatterDuration + scatterHold + assembleDuration + shapeHold
  const segment = Math.floor(time / duration)
  const local = time % duration
  const source = shapes[segment % shapes.length]
  const target = shapes[(segment + 1) % shapes.length]
  const words = SCULPTURE_SETTINGS.scatterText.words
  const wordIndex = segment % words.length
  const text = { wordIndex, word: words[wordIndex] }
  if (local < scatterDuration) return { ...text, shape: source, spread: smooth(local / scatterDuration), phase: 'scatter' }
  if (local < scatterDuration + scatterHold) return { ...text, shape: target, spread: 1, phase: 'word' }
  if (local < scatterDuration + scatterHold + assembleDuration) {
    return { ...text, shape: target, spread: 1 - smooth((local - scatterDuration - scatterHold) / assembleDuration), phase: 'assemble' }
  }
  return { ...text, shape: target, spread: 0, phase: 'hold' }
}

function mobiusPose(index, count) {
  const t = index / count * TAU
  const radius = 8.6
  const position = new THREE.Vector3(radius * Math.cos(t), radius * Math.sin(t), 0)
  const tangent = new THREE.Vector3(-Math.sin(t), Math.cos(t), 0)
  const across = new THREE.Vector3(Math.cos(t) * Math.cos(t / 2), Math.sin(t) * Math.cos(t / 2), Math.sin(t / 2))
  const depth = across.clone().cross(tangent).normalize()
  const matrix = new THREE.Matrix4().makeBasis(depth, across, tangent)
  return { position, quaternion: new THREE.Quaternion().setFromRotationMatrix(matrix), scale: new THREE.Vector3(0.8, 1.08, 1) }
}

const fluidPosition = new THREE.Vector3()
const fluidTangent = new THREE.Vector3()
const fluidAcross = new THREE.Vector3()
const fluidDepth = new THREE.Vector3()

// Deform the centerline and follow its tangent so the sheets form a flowing surface.
// Integer spatial frequencies preserve the closed loop and its half-turn seam.
export function composeMobiusMatrix(u, time, out) {
  const motion = SCULPTURE_SETTINGS.mobiusMotion
  const angle = u * TAU
  const phase = TAU * time / motion.period
  const flow = phase * motion.flowSpeed
  const wave = 2 * angle - flow
  const ridgePhase = 3 * angle - 0.7 * flow
  const crest = (1 + Math.sin(ridgePhase)) / 2
  const radius = 8.6 * (1 + motion.radiusBreath * Math.sin(phase))
    + motion.radialWave * Math.sin(wave) + motion.ridge * crest ** 4
  const radiusSlope = 2 * motion.radialWave * Math.cos(wave)
    + 6 * motion.ridge * crest ** 3 * Math.cos(ridgePhase)
  const liftPhase = 2 * angle - 0.8 * flow
  const lift = motion.lift * Math.sin(liftPhase)
  const liftSlope = 2 * motion.lift * Math.cos(liftPhase)
  const c = Math.cos(angle)
  const s = Math.sin(angle)
  fluidPosition.set(radius * c, radius * s, lift)
  fluidTangent.set(radiusSlope * c - radius * s, radiusSlope * s + radius * c, liftSlope).normalize()

  const twist = angle / 2 + motion.twist * Math.sin(wave)
  fluidAcross.set(c * Math.cos(twist), s * Math.cos(twist), Math.sin(twist))
  fluidAcross.addScaledVector(fluidTangent, -fluidAcross.dot(fluidTangent)).normalize()
  fluidDepth.crossVectors(fluidAcross, fluidTangent).normalize()

  // Width pulses lag the centerline, creating a soft fan of thin sheets.
  fluidAcross.multiplyScalar(1.08 * (1 + motion.widthBreath * Math.sin(phase - 0.45) + 0.1 * Math.sin(wave - 0.7)))
  fluidDepth.multiplyScalar(0.8 * (1 + 0.06 * Math.sin(wave)))
  out.makeBasis(fluidDepth, fluidAcross, fluidTangent)
  out.setPosition(fluidPosition)
  return out
}

// Closed ribbons share the same thin-sheet cross-section as the infinity and Möbius.
function ribbonPoint(u, shape) {
  const t = u * TAU
  if (shape === 'trefoil') {
    const r = 3.65 * (2 + Math.cos(3 * t))
    return new THREE.Vector3(r * Math.cos(2 * t), r * Math.sin(2 * t), 3.5 * Math.sin(3 * t))
  }
  return new THREE.Vector3(9.8 * Math.cos(t), 7.6 * Math.sin(t), 2.8 * Math.sin(2 * t))
}

export function composeRibbonMatrix(pose, u, time, animated, out) {
  const motion = SCULPTURE_SETTINGS.ribbonMotion
  const phase = animated ? TAU * time / motion.period : 0
  const wave = TAU * 2 * u - phase
  const theta = TAU * u + (animated ? motion.twist * Math.sin(wave) : 0)
  const c = Math.cos(theta)
  const s = Math.sin(theta)
  fluidAcross.copy(pose.normal).multiplyScalar(c).addScaledVector(pose.binormal, s)
  fluidDepth.copy(pose.normal).multiplyScalar(s).addScaledVector(pose.binormal, -c)
  fluidTangent.copy(pose.tangent)
  fluidPosition.copy(pose.position)
  if (animated) {
    fluidPosition.multiplyScalar(1 + motion.breath * Math.sin(phase))
    fluidPosition.addScaledVector(pose.normal, motion.wave * Math.sin(wave))
  }
  fluidDepth.multiplyScalar(pose.scale.x)
  fluidAcross.multiplyScalar(pose.scale.y * (animated ? 1 + motion.widthBreath * Math.sin(wave - 0.5) : 1))
  out.makeBasis(fluidDepth, fluidAcross, fluidTangent)
  out.setPosition(fluidPosition)
  return out
}

function buildRibbonPoses(count, shape) {
  const curve = new THREE.CatmullRomCurve3(Array.from({ length: 80 }, (_, i) => ribbonPoint(i / 80, shape)), true, 'centripetal')
  const frames = curve.computeFrenetFrames(count, true)
  return Array.from({ length: count }, (_, i) => ({
    position: curve.getPointAt(i / count),
    normal: frames.normals[i].clone(),
    binormal: frames.binormals[i].clone(),
    tangent: frames.tangents[i].clone(),
    scale: new THREE.Vector3(0.75, shape === 'trefoil' ? 0.64 : 0.94, 1),
  }))
}

export function buildShapePoses(count) {
  const trefoil = buildRibbonPoses(count, 'trefoil')
  const waveRing = buildRibbonPoses(count, 'waveRing')
  return Array.from({ length: count }, (_, index) => ({
    mobius: mobiusPose(index, count),
    trefoil: trefoil[index],
    waveRing: waveRing[index],
  }))
}
