import React, {useEffect, useLayoutEffect, useMemo, useRef} from 'react';
import * as THREE from 'three';

// The mascot snake in 3D, drawn as anime (三渲二): a black body that is a tube of varying
// thickness along a spline (a coil at the base, an S rising to the head, as in mascot.png), a
// rounded head with the logo's eyes — a big white oval and a small lime one; cel shading in three
// flat bands, a lime rim light, and an ink outline (the inverted hull). Poses are functions of
// time and a few dials, so any frame can be drawn on its own.

export const INK = '#151515';
const BANDS = ['#141414', '#2A2A2A', '#5E5E5E']; // shadow, mid, light: flat, no gradients
const RIM = '#C8F04A';

/** The dials of a pose; every one 0 is the snake at rest. */
export type Pose = {
  sway?: number; // the S of the neck swinging (radians of phase)
  tilt?: number; // head roll: a curious tilt, −1…1
  look?: number; // head turn left/right, −1…1
  nod?: number; // head dip, 0…1
  blink?: number; // 0 open … 1 shut
  lift?: number; // tail raised out of the coil, pointing, 0…1
  happy?: number; // a wiggle down the body, 0…1
  rise?: number; // how tall it stands, 0…1 (1: full height)
  turn?: number; // the whole snake turned about its vertical axis (radians)
};

const N = 44; // spine control points

/** The spine for a pose at time `t` (seconds). */
function spine(t: number, p: Pose): THREE.Vector3[] {
  const rise = p.rise ?? 1;
  const pts: THREE.Vector3[] = [];
  const wig = (p.happy ?? 0) * 0.55;
  for (let i = 0; i <= N; i += 1) {
    const u = i / N;
    if (u < 0.5) {
      // the coil at the base: a flat spiral, the tail at its outside; lifted when pointing
      const s = u / 0.5;
      const a = -Math.PI * 0.4 + s * Math.PI * 2.05;
      const R = 3.4 - s * 0.9;
      const lift = (p.lift ?? 0) * Math.pow(1 - s, 3) * 3.2;
      pts.push(new THREE.Vector3(R * Math.cos(a) + lift * 0.6, -4.2 + s * 0.35 + lift, R * Math.sin(a) * 0.75 + Math.sin(t * 9 + s * 8) * wig * 0.3));
    } else {
      // the rising S, swaying; the top hooks forward into the head
      const s = (u - 0.5) / 0.5;
      const sw = (p.sway ?? 0) + Math.sin(t * 1.6) * 0.18;
      const x = 1.5 * Math.sin(s * Math.PI * 1.25 + 0.4 + sw * (1 - s * 0.5)) * (1 - 0.25 * s) + Math.sin(t * 10 + s * 10) * wig * s;
      const y = -3.85 + s * 8.6 * (0.55 + 0.45 * rise) - (p.nod ?? 0) * s * s * 1.2;
      const z = 0.6 * Math.sin(s * Math.PI) + 0.4 * Math.sin(t * 1.3 + s * 3) * 0.3;
      pts.push(new THREE.Vector3(x, y, z));
    }
  }
  return pts;
}

/** Body thickness along the spine: a fine tail, a full belly, a slimmer neck. */
const radius = (u: number) => {
  const tail = Math.min(1, u / 0.22);
  const neck = u > 0.78 ? 1 - (u - 0.78) * 1.2 : 1;
  return 0.12 + 0.88 * Math.sin((tail * Math.PI) / 2) * neck;
};

/** A tube of varying radius along a curve (TubeGeometry is constant). */
function taperedTube(curve: THREE.CatmullRomCurve3, segs = 150, ring = 22, scale = 1): THREE.BufferGeometry {
  const frames = curve.computeFrenetFrames(segs, false);
  const pos: number[] = [];
  const nrm: number[] = [];
  const idx: number[] = [];
  for (let i = 0; i <= segs; i += 1) {
    const u = i / segs;
    const c = curve.getPointAt(u);
    const r = radius(u) * scale;
    for (let j = 0; j <= ring; j += 1) {
      const a = (j / ring) * Math.PI * 2;
      const n = frames.normals[i].clone().multiplyScalar(Math.cos(a)).add(frames.binormals[i].clone().multiplyScalar(Math.sin(a))).normalize();
      pos.push(c.x + n.x * r, c.y + n.y * r, c.z + n.z * r);
      nrm.push(n.x, n.y, n.z);
    }
  }
  for (let i = 0; i < segs; i += 1) {
    for (let j = 0; j < ring; j += 1) {
      const a = i * (ring + 1) + j;
      const b = a + ring + 1;
      idx.push(a, a + 1, b, b, a + 1, b + 1); // counter-clockwise from outside, so the front faces face out
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
  g.setIndex(idx);
  return g;
}

// ---------------------------------------------------------------- the cel shader and the outline
const toonVert = `
  varying vec3 vN; varying vec3 vV;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }`;
const toonFrag = `
  uniform vec3 c0; uniform vec3 c1; uniform vec3 c2; uniform vec3 rim; uniform vec3 light; uniform float rimOn;
  varying vec3 vN; varying vec3 vV;
  void main() {
    float d = dot(normalize(vN), normalize(light));
    vec3 col = d > 0.42 ? c2 : d > -0.05 ? c1 : c0;
    float f = 1.0 - max(dot(normalize(vN), vV), 0.0);
    if (rimOn > 0.5 && f > 0.62 && d > -0.15) col = rim;
    gl_FragColor = vec4(col, 1.0);
  }`;
const outlineVert = `
  uniform float width;
  void main() {
    vec3 p = position + normal * width;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
  }`;
const outlineFrag = `uniform vec3 ink; void main() { gl_FragColor = vec4(ink, 1.0); }`;

const LIGHT = new THREE.Vector3(-0.5, 0.75, 0.6).normalize();
export const toon = (bands = BANDS, rimOn = true) => new THREE.ShaderMaterial({
  vertexShader: toonVert, fragmentShader: toonFrag,
  uniforms: {c0: {value: new THREE.Color(bands[0])}, c1: {value: new THREE.Color(bands[1])}, c2: {value: new THREE.Color(bands[2])},
    rim: {value: new THREE.Color(RIM)}, light: {value: LIGHT}, rimOn: {value: rimOn ? 1 : 0}},
});
export const outline = (width = 0.09, ink = '#050505') => new THREE.ShaderMaterial({
  vertexShader: outlineVert, fragmentShader: outlineFrag, side: THREE.BackSide,
  uniforms: {width: {value: width}, ink: {value: new THREE.Color(ink)}},
});

/** A mesh drawn twice: cel-shaded, and as its ink outline. */
export const Inked: React.FC<{geometry: THREE.BufferGeometry; mat: THREE.Material; line: THREE.Material; position?: THREE.Vector3; quaternion?: THREE.Quaternion; scale?: THREE.Vector3}> =
  ({geometry, mat, line, position, quaternion, scale}) => (
    <group position={position} quaternion={quaternion} scale={scale}>
      <mesh geometry={geometry} material={mat} />
      <mesh geometry={geometry} material={line} />
    </group>
  );

/** The snake at time `t` (seconds, already stepped to the frame rate you want) in a pose. */
export const Snake: React.FC<{t: number; pose?: Pose; position?: [number, number, number]; scale?: number}> = ({t, pose = {}, position = [0, 0, 0], scale = 1}) => {
  const mats = useMemo(() => ({
    body: toon(), line: outline(0.08),
    white: toon(['#CFCBC2', '#EDEAE3', '#FFFFFF'], false), lime: toon(['#7FA020', '#A8CC3A', '#D8FF6A'], false), pupilLine: outline(0.04),
  }), []);
  const sphere = useMemo(() => new THREE.SphereGeometry(1, 40, 28), []);
  const body = useMemo(() => {
    const pts = spine(t, pose);
    const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    return {curve, geo: taperedTube(curve)};
  }, [t, pose]);
  useEffect(() => () => body.geo.dispose(), [body]);
  // the head: at the end of the spine, pointing along it, turned toward +x (the logo's facing)
  const head = useMemo(() => {
    const end = body.curve.getPointAt(1);
    const tan = body.curve.getTangentAt(0.985).normalize();
    const fwd = new THREE.Vector3(1, 0.15, 0.25).normalize().lerp(tan, 0.25).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1, 0, 0), fwd);
    q.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler((pose.tilt ?? 0) * 0.45, (pose.look ?? 0) * 0.6, -(pose.nod ?? 0) * 0.4)));
    return {pos: end.clone().add(fwd.clone().multiplyScalar(0.95)), q};
  }, [body, pose.tilt, pose.look, pose.nod]);
  const blink = 1 - (pose.blink ?? 0) * 0.92;
  return (
    <group position={position} scale={scale} rotation={[0.42, pose.turn ?? 0, 0]}>
      <Inked geometry={body.geo} mat={mats.body} line={mats.line} />
      <group position={head.pos} quaternion={head.q}>
        {/* the head: rounded, a little flat, longer toward the snout */}
        <Inked geometry={sphere} mat={mats.body} line={mats.line} scale={new THREE.Vector3(2.35, 1.7, 1.8)} />
        {/* the big white oval eye, toward the back of the head, on the camera side */}
        <Inked geometry={sphere} mat={mats.white} line={mats.pupilLine} position={new THREE.Vector3(-0.45, 0.45, 1.5)} scale={new THREE.Vector3(0.7, 1.08 * blink, 0.3)} />
        {/* the small lime eye near the snout */}
        <Inked geometry={sphere} mat={mats.lime} line={mats.pupilLine} position={new THREE.Vector3(1.3, 0.62, 1.15)} scale={new THREE.Vector3(0.44, 0.44 * blink, 0.24)} />
      </group>
    </group>
  );
};

/** Releases the WebGL context when the view goes away (a long render mounts many). */
export const useFreeContext = () => {
  const gl = useRef<THREE.WebGLRenderer | null>(null);
  useEffect(() => () => { gl.current?.dispose(); gl.current?.forceContextLoss(); }, []);
  return (state: {gl: THREE.WebGLRenderer}) => { gl.current = state.gl; };
};
void useLayoutEffect;
