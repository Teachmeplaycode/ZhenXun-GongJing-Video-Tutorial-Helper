import React, {useEffect, useLayoutEffect, useMemo, useRef} from 'react';
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
  /** a pose of its own (world units, radians), blended in by `mix` */
  to?: {x: number; y: number; z: number; rx?: number; ry?: number; rz?: number; sx?: number; sy?: number; sz?: number};
  mix?: number;
};
const _e3 = new THREE.Euler();
const _q2 = new THREE.Quaternion();

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

type View = [number, number, number];
const Slats: React.FC<{time: number; pose: (i: number, u: number) => SlatPose; spin: number; view: View}> = ({time, pose, spin, view}) => {
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
      if (p.to && (p.mix ?? 1) > 0) {
        const k = p.mix ?? 1;
        const o = p.to;
        _p.lerp(_tmp.set(o.x, o.y, o.z), k);
        _q.slerp(_q2.setFromEuler(_e3.set(o.rx ?? 0, o.ry ?? 0, o.rz ?? 0)), k);
        _s.lerp(_tmp.set(o.sx ?? 1, o.sy ?? 1, o.sz ?? 1), k);
      }
      if (p.lift) _p.z += p.lift;
      _s.multiplyScalar(p.size ?? 1);
      _m.compose(_p, _q, _s);
      m.setMatrixAt(i, _m);
      m.setColorAt(i, color.set(p.color ?? '#F0EDE8')); // --sculpture-light
    });
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  });
  return (
    <group rotation={[view[0], view[1] + spin, view[2]]}>
      <instancedMesh ref={mesh} args={[undefined, undefined, SHEETS]}>
        <boxGeometry args={[SHEET.width, SHEET.height, SHEET.thickness]} />
        <meshStandardMaterial color="#ffffff" roughness={0.5} metalness={0.05} />
      </instancedMesh>
    </group>
  );
};

/** The sculpture over the whole frame (transparent around it). World units: about 43 px each at
 *  scale 1. `view` turns the whole piece (the site's view by default); `focus` is the camera
 *  following a point on the ribbon (its u), pushed in to `zoom`, blended in by `mix`. */
export const Sculpture: React.FC<{pose?: (i: number, u: number) => SlatPose; spin?: number; scale?: number; x?: number; y?: number; style?: React.CSSProperties;
  phase?: number; view?: View; focus?: {u: number; zoom: number; mix: number}}> = ({pose = () => ({}), spin = 0, scale = 1, x = 0, y = 0, style, phase = 0,
  view = [VIEW.x, VIEW.y, VIEW.z], focus}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps + phase;
  let pos: [number, number, number] = [x, y, 0];
  let s = scale;
  if (focus && focus.mix > 0) {
    // where that point of the ribbon is after the view's turn, so it can be brought to the centre
    const p = loopPoint(focus.u).applyEuler(new THREE.Euler(view[0], view[1] + spin, view[2]));
    const z = scale + (focus.zoom - scale) * focus.mix;
    pos = [x + (-p.x * z - x) * focus.mix, y + (-p.y * z - y) * focus.mix, -p.z * z * focus.mix];
    s = z;
  }
  // Free the WebGL context when the scene ends: a long render mounts many sculptures, and Chrome
  // drops the oldest context once too many are alive — the sculpture then vanishes from frames.
  const gl = useRef<THREE.WebGLRenderer | null>(null);
  useEffect(() => () => {
    gl.current?.dispose();
    gl.current?.forceContextLoss();
  }, []);
  return (
    <ThreeCanvas width={width} height={height} style={{position: 'absolute', inset: 0, ...style}} camera={{fov: 22, position: [0, 0, 64], near: 1, far: 400}}
      gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}} onCreated={(state) => { gl.current = state.gl; }}>
      {/* the site's light field: hemisphere fill, a broad key, a low rim */}
      <hemisphereLight args={['#ffffff', '#D8D4CE', 1.6]} />
      <directionalLight position={[-14, 22, 18]} intensity={1.5} />
      <directionalLight position={[16, -6, -12]} intensity={0.55} />
      <group position={pos} scale={s}>
        <Slats time={time} pose={pose} spin={spin} view={view} />
      </group>
    </ThreeCanvas>
  );
};

export const SITE_VIEW: View = [VIEW.x, VIEW.y, VIEW.z];

// ---------------------------------------------------------------- the timeline on the floor
/** The view for the floor scenes: looking down at a timeline laid on the ground, receding. */
export const FLOOR_VIEW: View = [0.78, -0.42, 0.02];
const REST = (-68 * Math.PI) / 180; // the site's timeline: slats stand obliquely, like a deck seen from the side
export const FLOOR_Y = -4.5;
/** Slat `u` standing on a curving, undulating floor timeline (as in the site's TimelineSculpture):
 *  `head` is the slat being read — it and its neighbours rise and turn along a cosine bell. */
export const floorSlat = (u: number, time: number, head = -1, length = 50) => {
  const a = u * TAU * 0.85 + 0.9;
  const x = (u - 0.5) * length;
  const z = -2 + 7 * Math.sin(a);
  const tx = length;
  const tz = 7 * TAU * 0.85 * Math.cos(a);
  const d = Math.abs(u - head) * SHEETS;
  const bell = head >= 0 && d < 7 ? 0.5 + 0.5 * Math.cos((Math.PI * d) / 7) : 0;
  const sy = 0.5 + 0.24 * Math.sin(u * TAU * 2.6 - time * 1.3) + 0.12 * bell; // the heights roll like a wave
  return {
    x, z, y: FLOOR_Y + (SHEET.height * sy) / 2 + bell * 4.2,
    ry: Math.atan2(tx, tz) + REST + bell * 0.9, rx: 0, rz: 0,
    sx: 1.1, sy, sz: 4, bell,
  };
};
/** Where a world point (inside a group turned by `view`) lands on the 1920×1080 frame, and how
 *  many px one unit is there. */
export const project = (p: {x: number; y: number; z: number}, view: View) => {
  const v = new THREE.Vector3(p.x, p.y, p.z).applyEuler(new THREE.Euler(view[0], view[1], view[2]));
  const f = 540 / Math.tan((11 * Math.PI) / 180) / (64 - v.z);
  return {x: 960 + v.x * f, y: 540 - v.y * f, unit: f};
};
