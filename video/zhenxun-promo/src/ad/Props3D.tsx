import React, {useMemo} from 'react';
import * as THREE from 'three';
import {ThreeCanvas} from '@remotion/three';
import {Inked, outline, toon, useFreeContext} from './Snake3D';
import {PAPER_EDGE} from './SnakeSheet';
import {useStep} from './paper';

// Props for the ad's boards, modelled and drawn the way the snake is (三渲二): three flat bands of
// colour, a lime rim, an ink outline (the inverted hull); only the site's ink, cream and lime. Each one
// pops in on the stop-motion grid and then rocks (its face stays toward us) and bobs a little, on twelve steps a second.

export type PropKind = 'cursor' | 'magnifier' | 'play' | 'stopwatch' | 'star' | 'question' | 'check' | 'bulb' | 'bubble' | 'pin';

const INKS = ['#141414', '#2A2A2A', '#5E5E5E'];
const CREAM = ['#CFCBC2', '#EDEAE3', '#FFFFFF'];
const LIMES = ['#7FA020', '#A8CC3A', '#D8FF6A'];
const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

const extrude = (shape: THREE.Shape, depth = 0.6, bevel = 0.18) => {
  const g = new THREE.ExtrudeGeometry(shape, {depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 4, curveSegments: 24});
  g.center();
  return g;
};
const tube = (pts: [number, number][], r = 0.42) =>
  new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map(([x, y]) => V(x, y, 0))), 64, r, 16, false);

/** One prop's meshes (each a geometry, its colours, where it sits), built once. */
function parts(kind: PropKind): {geo: THREE.BufferGeometry; bands: string[]; rim?: boolean; at?: THREE.Vector3; rot?: THREE.Euler; scale?: THREE.Vector3}[] {
  const sphere = new THREE.SphereGeometry(1, 32, 24);
  switch (kind) {
    case 'cursor': {
      const s = new THREE.Shape();
      [[0, 0], [0, -4.2], [1.05, -3.2], [1.85, -4.9], [2.6, -4.55], [1.85, -2.9], [3.1, -2.9]].forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y)));
      s.closePath();
      return [{geo: extrude(s, 0.5, 0.14), bands: CREAM}];
    }
    case 'magnifier':
      return [
        {geo: new THREE.TorusGeometry(1.6, 0.36, 18, 48), bands: INKS},
        {geo: new THREE.CylinderGeometry(1.5, 1.5, 0.12, 40), bands: ['#B9D7D2', '#DDEFEA', '#FFFFFF'], rim: false, rot: new THREE.Euler(Math.PI / 2, 0, 0)},
        {geo: new THREE.CylinderGeometry(0.36, 0.42, 2.4, 20), bands: LIMES, at: V(1.95, -1.95, 0), rot: new THREE.Euler(0, 0, Math.PI / 4)},
      ];
    case 'play': {
      const s = new THREE.Shape();
      s.moveTo(-1.3, -1.6); s.lineTo(1.9, 0); s.lineTo(-1.3, 1.6); s.closePath();
      return [{geo: new THREE.CylinderGeometry(2.5, 2.5, 0.7, 48), bands: INKS, rot: new THREE.Euler(Math.PI / 2, 0, 0)},
        {geo: extrude(s, 0.4, 0.12), bands: LIMES, rim: false, at: V(0.15, 0, 0.45)}];
    }
    case 'stopwatch':
      return [
        {geo: new THREE.CylinderGeometry(2.2, 2.2, 0.8, 48), bands: CREAM, rot: new THREE.Euler(Math.PI / 2, 0, 0)},
        {geo: new THREE.TorusGeometry(2.2, 0.32, 16, 48), bands: INKS},
        {geo: new THREE.CylinderGeometry(0.38, 0.38, 0.8, 16), bands: LIMES, at: V(0, 2.75, 0)},
        {geo: new THREE.BoxGeometry(0.22, 1.5, 0.2), bands: INKS, at: V(0.3, 0.55, 0.55), rot: new THREE.Euler(0, 0, -0.45)},
      ];
    case 'star': {
      const s = new THREE.Shape();
      for (let i = 0; i < 8; i += 1) {
        const a = (i / 8) * Math.PI * 2 + Math.PI / 2;
        const r = i % 2 ? 0.75 : 2.4;
        if (i) s.lineTo(Math.cos(a) * r, Math.sin(a) * r); else s.moveTo(Math.cos(a) * r, Math.sin(a) * r);
      }
      s.closePath();
      return [{geo: extrude(s, 0.5, 0.16), bands: LIMES}];
    }
    case 'question':
      return [{geo: tube([[-1.3, 1.6], [-0.9, 2.7], [0.4, 3], [1.4, 2.2], [1.1, 1], [0, 0.4], [0, -0.7]]), bands: INKS},
        {geo: sphere, bands: INKS, at: V(0, -1.9, 0), scale: V(0.55, 0.55, 0.55)}];
    case 'check':
      return [{geo: tube([[-1.9, 0.2], [-0.6, -1.2], [2.2, 2]], 0.5), bands: LIMES}];
    case 'bulb':
      return [{geo: sphere, bands: ['#C9B85A', '#F0E07A', '#FFF8C8'], scale: V(1.9, 2.05, 1.9), at: V(0, 0.6, 0)},
        {geo: new THREE.CylinderGeometry(0.85, 0.85, 1.4, 24), bands: INKS, at: V(0, -1.75, 0)}];
    case 'bubble': {
      const s = new THREE.Shape();
      s.moveTo(-2.6, -1); s.lineTo(-2.6, 1.3); s.quadraticCurveTo(-2.6, 2, -1.9, 2); s.lineTo(1.9, 2); s.quadraticCurveTo(2.6, 2, 2.6, 1.3);
      s.lineTo(2.6, -1); s.quadraticCurveTo(2.6, -1.7, 1.9, -1.7); s.lineTo(-0.6, -1.7); s.lineTo(-1.6, -2.8); s.lineTo(-1.5, -1.7); s.lineTo(-1.9, -1.7);
      s.quadraticCurveTo(-2.6, -1.7, -2.6, -1);
      return [{geo: extrude(s, 0.5, 0.16), bands: CREAM},
        ...[-1.1, 0, 1.1].map((x) => ({geo: sphere, bands: INKS, rim: false, at: V(x, 0.15, 0.55), scale: V(0.32, 0.32, 0.2)}))];
    }
    case 'pin':
      return [{geo: sphere, bands: LIMES, at: V(0, 1, 0), scale: V(1.3, 1.3, 1.3)},
        {geo: new THREE.ConeGeometry(0.22, 2.2, 12), bands: CREAM, at: V(0, -1.1, 0), rot: new THREE.Euler(Math.PI, 0, 0)}];
  }
}

const Model: React.FC<{kind: PropKind; t: number; spin: number; tilt: number}> = ({kind, t, spin, tilt}) => {
  const meshes = useMemo(() => parts(kind).map((p) => ({...p, mat: toon(p.bands, p.rim ?? true), line: outline(0.1)})), [kind]);
  return (
    <group rotation={[tilt, Math.sin(t * 1.4) * spin * 0.9 - 0.25, Math.sin(t * 0.9) * 0.1]} position={[0, Math.sin(t * 2.1) * 0.25, 0]}>
      {meshes.map((m, i) => (
        <group key={i} position={m.at} rotation={m.rot}>
          <Inked geometry={m.geo} mat={m.mat} line={m.line} scale={m.scale} />
        </group>
      ))}
    </group>
  );
};

/** A prop in a size×size square at (x, y) of its board, arriving at frame `at`. */
export const Prop: React.FC<{kind: PropKind; x: number; y: number; size?: number; at?: number; spin?: number; tilt?: number; z?: number; rot?: number}> =
  ({kind, x, y, size = 180, at = 0, spin = 0.6, tilt = 0.25, z = 48, rot = 0}) => {
    const t = useStep(at);
    const onCreated = useFreeContext();
    if (t < 0) return null;
    const pop = t < 1 / 12 ? 0.4 : t < 2 / 12 ? 1.18 : t < 3 / 12 ? 0.94 : 1;
    return (
      <div style={{position: 'absolute', left: x, top: y, width: size, height: size, zIndex: z, filter: PAPER_EDGE, transform: `rotate(${rot}deg) scale(${pop})`}}>
        <ThreeCanvas width={size} height={size} camera={{fov: 22, position: [0, 0, 17], near: 1, far: 200}}
          gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}} onCreated={onCreated}>
          <Model kind={kind} t={t} spin={spin} tilt={tilt} />
        </ThreeCanvas>
      </div>
    );
  };
