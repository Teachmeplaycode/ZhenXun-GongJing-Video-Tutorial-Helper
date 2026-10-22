import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp01, hash, INK, LIME, PAPER, SC, stepped} from '../pv/kit';

// The ad's paper world: sheets with torn edges and a little grain, photos with white borders, tape,
// pins, a sagging thread, rubber stamps, words cut out a glyph at a time, halftone. Every piece
// moves like stop motion — on 12 fps steps, landing with one frame of squash — and every shadow
// falls the same way (light from the upper left).

export const SHADOW = 'drop-shadow(9px 11px 0 rgba(26,26,26,0.17))';
export const RED = '#D9483A'; // the evidence thread, used sparingly
export const KRAFT = '#E6D9C2';

/** Frames on the 12 fps stop-motion grid (a whole number of steps since `at`). */
export const useStep = (at = 0) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return stepped(frame - at, fps, 12) / 12; // seconds since `at`, in 1/12 s steps
};

/** A torn outline for a w×h sheet: the edges walked in small steps, each nudged in or out. */
export function tornPath(w: number, h: number, seed = 1, rough = 5, step = 16): string {
  const pts: [number, number][] = [];
  const edge = (x0: number, y0: number, x1: number, y1: number, k: number) => {
    const n = Math.max(2, Math.round(Math.hypot(x1 - x0, y1 - y0) / step));
    const nx = -(y1 - y0) / Math.hypot(x1 - x0, y1 - y0);
    const ny = (x1 - x0) / Math.hypot(x1 - x0, y1 - y0);
    for (let i = 0; i < n; i += 1) {
      const u = i / n;
      const j = (hash(i, seed, k) - 0.5) * 2 * rough;
      pts.push([x0 + (x1 - x0) * u + nx * j, y0 + (y1 - y0) * u + ny * j]);
    }
  };
  edge(0, 0, w, 0, 1);
  edge(w, 0, w, h, 2);
  edge(w, h, 0, h, 3);
  edge(0, h, 0, 0, 4);
  return `M${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join('L')}Z`;
}

/** How a piece arrives: dropped from above (or slid from a side) in a few steps, a squash on landing. */
export const landing = (t: number, from: [number, number] = [0, -160], steps = 3) => {
  if (t < 0) return {x: from[0], y: from[1], s: 1, on: false};
  const k = Math.min(1, t / (steps / 12));
  const land = t >= steps / 12 && t < (steps + 1) / 12;
  return {x: from[0] * (1 - k), y: from[1] * (1 - k), s: land ? 1.035 : 1, on: true};
};

type Piece = {x: number; y: number; w: number; h: number; rot?: number; at?: number; from?: [number, number]; z?: number; style?: React.CSSProperties; children?: React.ReactNode};

/** A sheet of paper, torn or cut, with grain and the common shadow. `at` is its arrival frame. */
export const Paper: React.FC<Piece & {color?: string; torn?: boolean; seed?: number; grain?: number}> = ({x, y, w, h, rot = 0, at = 0, from, z, color = PAPER, torn = true, seed = 1, grain = 0.08, style, children}) => {
  const t = useStep(at);
  const l = landing(t, from);
  if (!l.on) return null;
  const clip = torn ? `path('${tornPath(w, h, seed)}')` : undefined;
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, zIndex: z, filter: SHADOW,
      transform: `translate(${l.x}px, ${l.y}px) rotate(${rot}deg) scale(${l.s})`, ...style}}>
      <div style={{position: 'absolute', inset: 0, background: color, clipPath: clip, overflow: 'hidden'}}>
        {children}
        <svg width={w} height={h} style={{position: 'absolute', inset: 0, mixBlendMode: 'multiply', opacity: grain, pointerEvents: 'none'}}>
          <filter id={`g${seed}`}><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} /><feColorMatrix type="saturate" values="0" /></filter>
          <rect width={w} height={h} filter={`url(#g${seed})`} />
        </svg>
      </div>
    </div>
  );
};

/** A photo: a cut sheet with a white border holding a picture (or anything). */
export const Photo: React.FC<Piece & {seed?: number; border?: number}> = ({border = 14, children, ...p}) => (
  <Paper {...p} torn={false} color="#FFFFFF" grain={0.04}>
    <div style={{position: 'absolute', inset: border, overflow: 'hidden', background: '#000'}}>{children}</div>
  </Paper>
);

/** A strip of translucent tape. */
export const Tape: React.FC<{x: number; y: number; w?: number; rot?: number; at?: number; seed?: number}> = ({x, y, w = 150, rot = -8, at = 0, seed = 3}) => {
  const t = useStep(at);
  if (t < 0) return null;
  return (
    <div style={{position: 'absolute', left: x - w / 2, top: y - 20, width: w, height: 40, transform: `rotate(${rot}deg)`, zIndex: 50,
      background: 'rgba(250,246,226,0.62)', clipPath: `path('${tornPath(w, 40, seed, 3, 8)}')`, boxShadow: '0 1px 0 rgba(0,0,0,0.05)'}} />
  );
};

/** A push pin, drawn flat in two tones like the cel-shaded snake. */
export const Pin: React.FC<{x: number; y: number; color?: string; at?: number}> = ({x, y, color = LIME, at = 0}) => {
  const t = useStep(at);
  const l = landing(t, [0, -60], 2);
  if (!l.on) return null;
  return (
    <svg width={44} height={44} style={{position: 'absolute', left: x - 22, top: y - 22 + l.y, zIndex: 60, overflow: 'visible', filter: SHADOW}}>
      <circle cx={22} cy={22} r={15} fill={color} stroke={INK} strokeWidth={3} />
      <path d="M13 17 A10 10 0 0 1 24 10" stroke="#fff" strokeWidth={4} fill="none" strokeLinecap="round" />
    </svg>
  );
};

/** A thread from a to b, sagging, drawn out from a in steps. */
export const Thread: React.FC<{a: [number, number]; b: [number, number]; at?: number; dur?: number; color?: string}> = ({a, b, at = 0, dur = 0.5, color = RED}) => {
  const t = useStep(at);
  if (t < 0) return null;
  const k = clamp01(t / dur);
  const mid: [number, number] = [(a[0] + b[0]) / 2, Math.max(a[1], b[1]) + 60];
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]) * 1.3;
  return (
    <svg width={1920} height={1080} style={{position: 'absolute', inset: 0, zIndex: 55, pointerEvents: 'none', overflow: 'visible'}}>
      <path d={`M${a[0]} ${a[1]} Q${mid[0]} ${mid[1]} ${b[0]} ${b[1]}`} stroke="rgba(26,26,26,0.15)" strokeWidth={4} fill="none" transform="translate(5 7)"
        strokeDasharray={len} strokeDashoffset={len * (1 - k)} />
      <path d={`M${a[0]} ${a[1]} Q${mid[0]} ${mid[1]} ${b[0]} ${b[1]}`} stroke={color} strokeWidth={4} fill="none" strokeLinecap="round"
        strokeDasharray={len} strokeDashoffset={len * (1 - k)} />
    </svg>
  );
};

/** A rubber stamp: pressed down in two frames, the ink a little uneven. */
export const Stamp: React.FC<{x: number; y: number; text: string; rot?: number; at?: number; color?: string; size?: number; seed?: number}> = ({x, y, text, rot = -6, at = 0, color = INK, size = 44, seed = 5}) => {
  const t = useStep(at);
  if (t < 0) return null;
  const press = t < 1 / 12 ? 1.5 : t < 2 / 12 ? 0.94 : 1;
  return (
    <div style={{position: 'absolute', left: x, top: y, zIndex: 58, transform: `translate(-50%, -50%) rotate(${rot}deg) scale(${press})`,
      border: `5px solid ${color}`, borderRadius: 8, padding: '4px 16px', fontFamily: SC, fontWeight: 900, fontSize: size, color, whiteSpace: 'nowrap',
      opacity: 0.88, maskImage: `radial-gradient(circle at ${30 + hash(seed) * 40}% ${30 + hash(seed, 1) * 40}%, #000 55%, rgba(0,0,0,0.55) 100%)`}}>
      {text}
    </div>
  );
};

/** Big words cut out a glyph at a time, each on its own scrap, dropped one after another. */
export const CutText: React.FC<{x: number; y: number; text: string; size?: number; at?: number; gap?: number; colors?: [string, string][]; seed?: number}> =
  ({x, y, text, size = 180, at = 0, gap = 3, colors = [[PAPER, INK], [INK, PAPER], [LIME, INK]], seed = 11}) => {
    const glyphs = Array.from(text);
    let cx = x;
    return (
      <>
        {glyphs.map((g, i) => {
          const [bg, fg] = colors[Math.floor(hash(i, seed) * colors.length)];
          const w = /[\x00-\x7F]/.test(g) ? size * 0.66 : size * 1.06;
          const left = cx;
          cx += w + 10;
          return (
            <Paper key={i} x={left} y={y + (hash(i, seed, 2) - 0.5) * 24} w={w} h={size * 1.12} rot={(hash(i, seed, 3) - 0.5) * 10} at={at + i * gap}
              color={bg} seed={seed + i} z={40}>
              <div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', fontFamily: SC, fontWeight: 900, fontSize: size * 0.86, color: fg, lineHeight: 1}}>{g}</div>
            </Paper>
          );
        })}
      </>
    );
  };

/** A patch of halftone dots. */
export const Halftone: React.FC<{x: number; y: number; w: number; h: number; color?: string; dot?: number; rot?: number}> = ({x, y, w, h, color = INK, dot = 14, rot = 0}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w, height: h, transform: `rotate(${rot}deg)`, opacity: 0.16,
    backgroundImage: `radial-gradient(${color} 30%, transparent 32%)`, backgroundSize: `${dot}px ${dot}px`}} />
);
