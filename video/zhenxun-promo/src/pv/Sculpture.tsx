import React, {useLayoutEffect, useMemo, useRef} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import * as THREE from 'three';

// The homepage's thin-sheet sculpture — a figure-eight ribbon of 250 slats — in 3D, driven by the
// frame number. The ribbon math is the site's (front/src/lib/sculptureMath.js: the curve, twist,
// band width, breathing and fan wave); here each slat can also be scattered, pulled out of the
// band toward the camera, tinted, or laid out as a straight strip (a video's timeline).

const TAU = Math.PI * 2;
const SHEET = {width: 3.2, height: 6.8, thickness: 0.065};
const VIEW = {x: 0.14, y: -0.12, z: -0.06};
const TWIST_SPEED = 0.15;
const LOBE = {x: 11.2, y: 6.7, z: 3.6};
export const SHEETS = 250;

const loopPoint = (u: number) => {
  const t = u * TAU;
  return new THREE.Vector3(LOBE.x * Math.sin(t), LOBE.y * Math.sin(2 * t), LOBE.z * Math.cos(t) + 0.8 * Math.sin(3 * t));
};
const twistAngle = (u: number, time: number) => TAU * u + TWIST_SPEED * time + 0.55 * Math.sin(TAU * 2 * u - TWIST_SPEED * 2 * time);
const bandScale = (u: number, time: number) => 0.96 + 0.14 * Math.sin(TAU * 2 * u + 0.6 + 0.12 * time);
const breath = (u: number, time: number) => 0.22 * Math.sin((TAU * time) / 8 + TAU * 2 * u);
const fanAmount = (u: number, time: number) => {
  const s = Math.sin(TAU * u - 0.11 * time);
  return s > 0 ? s ** 8 : 0;
};

type Sheet = {u: number; jitter: number; position: THREE.Vector3; tangent: THREE.Vector3; normal: THREE.Vector3; binormal: THREE.Vector3;
  scatter: THREE.Vector3; scatterRot: THREE.Quaternion};

const sampleSheets = (count: number): Sheet[] => {
  const pts = Array.from({length: 24}, (_, i) => loopPoint(i / 24));
  const curve = new THREE.CatmullRomCurve3(pts, true, 'centripetal');
  const frames = curve.computeFrenetFrames(count, true);
  return Array.from({length: count}, (_, i) => ({
    u: i / count,
    jitter: Math.abs(Math.sin(i * 12.9898) * 43758.5453) % 1,
    position: curve.getPointAt(i / count),
    tangent: frames.tangents[i].clone(),
    normal: frames.normals[i].clone(),
    binormal: frames.binormals[i].clone(),
    scatter: new THREE.Vector3((((i * 0.61803398875) % 1) * 2 - 1) * 23, (((i * 0.754877666) % 1) * 2 - 1) * 11, (((i * 0.569840291) % 1) * 2 - 1) * 8),
    scatterRot: new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.sin(i * 2.4) * 0.7, Math.cos(i * 1.7) * 0.9, Math.sin(i * 0.8) * Math.PI)),
  }));
};

const _a = new THREE.Vector3();
const _e = new THREE.Vector3();
const _t = new THREE.Vector3();
const _tmp = new THREE.Vector3();
const _p = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _s = new THREE.Vector3();
const _m = new THREE.Matrix4();
const _strip = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.05, -1.22, 0.06)); // slats standing like a deck seen from the side

/** Per-slat state for one frame. */
export type SlatPose = {
  /** 0 = in the ribbon, 1 = scattered in a cloud */ spread?: number;
  /** 0 = ribbon or cloud, 1 = a straight strip across the frame (the video's timeline) */ strip?: number;
  /** pulled out of the band toward the camera, in world units */ lift?: number;
  color?: string;
  /** 0 hides the slat (scaled away) */ size?: number;
};

const ribbonMatrix = (sheet: Sheet, time: number, out: THREE.Matrix4) => {
  const {u} = sheet;
  const theta = twistAngle(u, time);
  const c = Math.cos(theta);
  const s = Math.sin(theta);
  _a.copy(sheet.normal).multiplyScalar(c).addScaledVector(sheet.binormal, s);
  _e.copy(sheet.normal).multiplyScalar(s).addScaledVector(sheet.binormal, -c);
  _t.copy(sheet.tangent);
  _p.copy(sheet.position).addScaledVector(sheet.normal, breath(u, time));
  const fan = fanAmount(u, time);
  if (fan > 0.001) {
    const phi = fan * (0.32 + 0.12 * sheet.jitter);
    const cp = Math.cos(phi);
    const sp = Math.sin(phi);
    _tmp.copy(_t);
    _t.multiplyScalar(cp).addScaledVector(_e, sp);
    _e.multiplyScalar(cp).addScaledVector(_tmp, -sp);
    _p.addScaledVector(_e, fan * (0.4 + 0.35 * sheet.jitter));
    _p.addScaledVector(_a, fan * (sheet.jitter - 0.5) * 0.5);
  }
  _a.multiplyScalar(bandScale(u, time));
  out.makeBasis(_e, _a, _t);
  out.setPosition(_p);
  return out;
};

const Slats: React.FC<{time: number; pose: (i: number, u: number) => SlatPose; spin: number}> = ({time, pose, spin}) => {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const sheets = useMemo(() => sampleSheets(SHEETS), []);
  const color = useMemo(() => new THREE.Color(), []);
  useLayoutEffect(() => {
    const m = mesh.current;
    if (!m) return;
    sheets.forEach((sheet, i) => {
      const p = pose(i, sheet.u);
      ribbonMatrix(sheet, time, _m);
      _m.decompose(_p, _q, _s);
      const spread = p.spread ?? 0;
      if (spread > 0) {
        _p.lerp(_tmp.copy(sheet.scatter).add(new THREE.Vector3(Math.sin(time * 0.3 + sheet.u * TAU) * 0.35, Math.cos(time * 0.25 + sheet.u * TAU) * 0.35, 0)), spread);
        _q.slerp(sheet.scatterRot, spread);
        _s.lerp(_tmp.setScalar(0.5), spread);
      }
      const strip = p.strip ?? 0;
      if (strip > 0) {
        // a straight row along x, slats standing obliquely, like the site's timeline deck
        _p.lerp(_tmp.set((sheet.u - 0.5) * 38, -1.5 + (sheet.u - 0.5) * 0.9, 0), strip);
        _q.slerp(_strip, strip);
        _s.lerp(_tmp.set(0.42, 0.4, 1), strip);
      }
      if (p.lift) _p.z += p.lift;
      _s.multiplyScalar(p.size ?? 1);
      _m.compose(_p, _q, _s);
      m.setMatrixAt(i, _m);
      m.setColorAt(i, color.set(p.color ?? '#F5F3EF'));
    });
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  });
  return (
    <group rotation={[VIEW.x, VIEW.y + spin, VIEW.z]}>
      <instancedMesh ref={mesh} args={[undefined, undefined, SHEETS]}>
        <boxGeometry args={[SHEET.width, SHEET.height, SHEET.thickness]} />
        <meshStandardMaterial color="#ffffff" roughness={0.5} metalness={0.05} />
      </instancedMesh>
    </group>
  );
};

/** The sculpture over the whole frame (transparent around it). World units: about 43 px each at scale 1. */
export const Sculpture: React.FC<{pose?: (i: number, u: number) => SlatPose; spin?: number; scale?: number; x?: number; y?: number; style?: React.CSSProperties;
  /** seconds offset, so different scenes don't show the same phase */ phase?: number}> = ({pose = () => ({}), spin = 0, scale = 1, x = 0, y = 0, style, phase = 0}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps + phase;
  return (
    <ThreeCanvas width={width} height={height} style={{position: 'absolute', inset: 0, ...style}} camera={{fov: 22, position: [0, 0, 64], near: 1, far: 400}}
      gl={{alpha: true, antialias: true}}>
      <hemisphereLight args={['#ffffff', '#3A3F2C', 1.4]} />
      <directionalLight position={[-14, 22, 18]} intensity={1.6} />
      <directionalLight position={[16, -6, -12]} intensity={0.6} />
      <group position={[x, y, 0]} scale={scale}>
        <Slats time={time} pose={pose} spin={spin} />
      </group>
    </ThreeCanvas>
  );
};
