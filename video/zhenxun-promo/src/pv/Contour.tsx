import React, {useLayoutEffect, useMemo, useRef} from 'react';
import {useVideoConfig} from 'remotion';
import {AMBER, INK, INK3, LINE2, SHADE} from './kit';

// The site's loading terrain (front/src/components/ContourLoader.jsx): a warped-fbm height field
// cut into closed iso-lines by marching squares, stacked as paper terraces lifted by elevation
// and drawn level by level from the lowest up, the active line drawn along with an amber pen.
// Here it is driven by a progress value instead of a clock; `Topo` draws the same lines flat, as
// a faint survey map behind other scenes.

const GRID = 132;
const LEVELS = 42;
const SETTINGS = {width: 0.95, height: 1.25, tilt: 0.72, relief: 0.22, centerY: 0.62};

const hash = (x: number, y: number) => {
  let h = Math.imul(x, 374761393) + Math.imul(y, 668265263);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
};
const noise = (x: number, y: number) => {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = x - ix;
  const fy = y - iy;
  const u = fx * fx * (3 - 2 * fx);
  const v = fy * fy * (3 - 2 * fy);
  const a = hash(ix, iy);
  const b = hash(ix + 1, iy);
  const c = hash(ix, iy + 1);
  const d = hash(ix + 1, iy + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
};
const fbm = (x: number, y: number) => {
  let sum = 0;
  let amp = 0.5;
  let freq = 1;
  for (let o = 0; o < 5; o += 1) {
    sum += amp * noise(x * freq, y * freq);
    freq *= 2;
    amp *= 0.5;
  }
  return sum;
};
const rawHeight = (x: number, z: number) => {
  const wx = x + 6 * fbm(x * 0.05 + 11, z * 0.05 + 3);
  const wz = z + 6 * fbm(x * 0.05 + 5, z * 0.05 + 17);
  const base = fbm(wx * 0.055 + 3, wz * 0.055 + 7);
  const ridge = 1 - Math.abs(2 * fbm(wx * 0.04 + 20, wz * 0.04 + 9) - 1);
  return 0.62 * base + 0.38 * ridge * ridge;
};
const smooth = (e0: number, e1: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

function buildField() {
  const n = GRID + 1;
  const h = new Float32Array(n * n);
  let lo = Infinity;
  let hi = -Infinity;
  for (let j = 0; j < n; j += 1) {
    for (let i = 0; i < n; i += 1) {
      const v = rawHeight(((i / GRID) * 2 - 1) * 40, ((j / GRID) * 2 - 1) * 40);
      h[j * n + i] = v;
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  }
  const peak = (x: number, y: number, px: number, py: number, r: number) => Math.exp(-((x - px) ** 2 + (y - py) ** 2) / (r * r));
  let max = 0;
  for (let j = 0; j < n; j += 1) {
    for (let i = 0; i < n; i += 1) {
      const x = (i / GRID) * 2 - 1;
      const y = (j / GRID) * 2 - 1;
      const base = ((h[j * n + i] - lo) / (hi - lo)) ** 1.6;
      const summits = 0.95 * peak(x, y, -0.18, -0.12, 0.34) + 0.7 * peak(x, y, 0.36, 0.28, 0.24);
      const rim = (x ** 4 + y ** 4) ** 0.25;
      const v = (0.55 * base + summits * (0.4 + 0.6 * base)) * (1 - smooth(0.62, 0.96, rim));
      h[j * n + i] = v;
      max = Math.max(max, v);
    }
  }
  for (let k = 0; k < h.length; k += 1) h[k] /= max;
  return h;
}

const CASES = [
  [], [[3, 2]], [[2, 1]], [[3, 1]], [[0, 1]], [[3, 0], [2, 1]], [[0, 2]], [[3, 0]],
  [[3, 0]], [[0, 2]], [[0, 1], [3, 2]], [[0, 1]], [[3, 1]], [[2, 1]], [[3, 2]], [],
];
function contourLoops(h: Float32Array, level: number) {
  const n = GRID + 1;
  const vOffset = n * n;
  const px = new Map<number, [number, number]>();
  const adj = new Map<number, number[]>();
  const edgeId = (i: number, j: number, e: number) => (e === 0 ? j * n + i : e === 2 ? (j + 1) * n + i : e === 3 ? vOffset + j * n + i : vOffset + j * n + i + 1);
  const edgePoint = (i: number, j: number, e: number): [number, number] => {
    let x0 = i; let y0 = j; let x1 = i + 1; let y1 = j;
    if (e === 1) { x0 = i + 1; x1 = i + 1; y1 = j + 1; }
    if (e === 2) { y0 = j + 1; y1 = j + 1; }
    if (e === 3) { x1 = i; y1 = j + 1; }
    const a = h[y0 * n + x0];
    const b = h[y1 * n + x1];
    const t = (level - a) / (b - a);
    return [((x0 + (x1 - x0) * t) / GRID) * 2 - 1, ((y0 + (y1 - y0) * t) / GRID) * 2 - 1];
  };
  const link = (a: number, b: number) => {
    if (!adj.has(a)) adj.set(a, []);
    if (!adj.has(b)) adj.set(b, []);
    adj.get(a)!.push(b);
    adj.get(b)!.push(a);
  };
  for (let j = 0; j < GRID; j += 1) {
    for (let i = 0; i < GRID; i += 1) {
      const idx = (h[j * n + i] > level ? 8 : 0) | (h[j * n + i + 1] > level ? 4 : 0) | (h[(j + 1) * n + i + 1] > level ? 2 : 0) | (h[(j + 1) * n + i] > level ? 1 : 0);
      for (const [ea, eb] of CASES[idx]) {
        const ida = edgeId(i, j, ea);
        const idb = edgeId(i, j, eb);
        if (!px.has(ida)) px.set(ida, edgePoint(i, j, ea));
        if (!px.has(idb)) px.set(idb, edgePoint(i, j, eb));
        link(ida, idb);
      }
    }
  }
  const seen = new Set<number>();
  const loops: Float32Array[] = [];
  for (const start of adj.keys()) {
    if (seen.has(start)) continue;
    const pts: number[] = [];
    let prev = -1;
    let cur: number | undefined = start;
    while (cur !== undefined && !seen.has(cur)) {
      seen.add(cur);
      pts.push(...px.get(cur)!);
      const nb: number[] = adj.get(cur)!;
      const next: number = nb[0] !== prev ? nb[0] : nb[1];
      prev = cur;
      cur = next;
    }
    if (pts.length >= 24) loops.push(new Float32Array(pts));
  }
  return loops;
}

let cache: {v: number; loops: Float32Array[]}[] | null = null;
const terrain = () => {
  if (!cache) {
    const field = buildField();
    cache = Array.from({length: LEVELS}, (_, k) => {
      const v = (k + 0.5) / LEVELS;
      return {v, loops: contourLoops(field, v)};
    });
  }
  return cache;
};

/** The loading terrain. `progress` 0 → 1 builds it from the lowest terrace up; `yaw` turns it. */
export const Contour: React.FC<{progress: number; yaw?: number; alpha?: number; scale?: number; cx?: number; cy?: number}> = ({progress, yaw = 0.6, alpha = 1, scale = 1, cx, cy}) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const {width: W, height: H} = useVideoConfig();
  const levels = useMemo(terrain, []);
  useLayoutEffect(() => {
    const ctx = ref.current!.getContext('2d')!;
    ctx.clearRect(0, 0, W, H);
    // as on the site, which draws it full screen (cropped at the edges); `scale` < 1 pulls it back
    const Sx = W * SETTINGS.width * scale;
    const Sy = H * SETTINGS.height * scale;
    const relief = H * SETTINGS.relief * scale;
    const step = relief / LEVELS;
    const ox = cx ?? W / 2;
    const oy = cy ?? H * SETTINGS.centerY;
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const reached = progress * LEVELS;
    ctx.lineJoin = 'round';
    const trace = (pts: Float32Array, count: number) => {
      ctx.beginPath();
      ctx.moveTo(pts[0], pts[1]);
      for (let p = 2; p < count; p += 2) ctx.lineTo(pts[p], pts[p + 1]);
    };
    for (let k = 0; k < LEVELS; k += 1) {
      const local = reached - k;
      if (local <= 0) break;
      const f = Math.min(1, local);
      const lift = levels[k].v * relief;
      const front = local < 1;
      for (const loop of levels[k].loops) {
        const pts = new Float32Array(loop.length);
        for (let p = 0; p < loop.length; p += 2) {
          const x = loop[p];
          const y = loop[p + 1];
          pts[p] = ox + (x * cosY - y * sinY) * Sx;
          pts[p + 1] = oy + (x * sinY + y * cosY) * Sy * SETTINGS.tilt - lift;
        }
        // the terrace's side (one step tall), then its top face: stacked paper
        ctx.save();
        ctx.translate(0, step);
        trace(pts, loop.length);
        ctx.closePath();
        ctx.fillStyle = SHADE;
        ctx.globalAlpha = alpha * f * (0.55 + 0.45 * levels[k].v);
        ctx.fill();
        ctx.restore();
        ctx.globalAlpha = alpha * f;
        trace(pts, loop.length);
        ctx.closePath();
        ctx.fillStyle = '#FAF8F5';
        ctx.fill();
        const count = front ? Math.max(2, Math.floor((loop.length / 2) * f) * 2) : loop.length;
        trace(pts, count);
        if (!front) ctx.closePath();
        ctx.lineWidth = front ? 2.4 : 1.5;
        ctx.strokeStyle = front ? INK : k % 5 === 4 ? '#6B6B6B' : INK3; // every fifth line an index contour
        ctx.stroke();
        if (front && count < loop.length) {
          ctx.fillStyle = AMBER;
          ctx.fillRect(pts[count - 2] - 4, pts[count - 1] - 4, 8, 8);
        }
      }
    }
    ctx.globalAlpha = 1;
  });
  return <canvas ref={ref} width={W} height={H} style={{position: 'absolute', inset: 0}} />;
};

/** The same terrain as a flat survey map: faint iso-lines, every fifth one darker. */
export const Topo: React.FC<{opacity?: number; scale?: number; x?: number; y?: number; turn?: number}> = ({opacity = 0.5, scale = 1.6, x = 960, y = 540, turn = 0}) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const {width: W, height: H} = useVideoConfig();
  const levels = useMemo(terrain, []);
  useLayoutEffect(() => {
    const ctx = ref.current!.getContext('2d')!;
    ctx.clearRect(0, 0, W, H);
    const R = 560 * scale;
    const c = Math.cos(turn);
    const s = Math.sin(turn);
    levels.forEach((lv, k) => {
      ctx.strokeStyle = k % 5 === 4 ? INK3 : LINE2;
      ctx.lineWidth = k % 5 === 4 ? 1.6 : 1;
      for (const loop of lv.loops) {
        ctx.beginPath();
        for (let p = 0; p < loop.length; p += 2) {
          const px = x + (loop[p] * c - loop[p + 1] * s) * R;
          const py = y + (loop[p] * s + loop[p + 1] * c) * R;
          if (p === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
      }
    });
  });
  return <canvas ref={ref} width={W} height={H} style={{position: 'absolute', inset: 0, opacity}} />;
};
