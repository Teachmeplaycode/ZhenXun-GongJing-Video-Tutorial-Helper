import React from 'react';
import {AbsoluteFill, Easing} from 'remotion';
import {linearTiming} from '@remotion/transitions';
import type {TransitionPresentation, TransitionPresentationComponentProps} from '@remotion/transitions';
import {BLUE, hash, LIME, NIGHT, Sfx, SfxName} from './kit';

// The PV's transitions. The next scene arrives through a shape — a + or × opening from a point,
// a ◆ from where the hand clicked, blocks, slashes, a > sweeping across, bands sliding in — while
// the scene before keeps moving under it (pushed in, scaled up), so no cut is a plain swap. Each
// one plays its own sound as it starts. Shapes are clip-path paths in frame pixels.

const W = 1920;
const H = 1080;

export const timing = (frames: number) => linearTiming({durationInFrames: frames, easing: Easing.bezier(0.7, 0, 0.18, 1)});

type Props = {kind: Kind; x?: number; y?: number; at?: () => {x: number; y: number}; sound?: SfxName; angle?: number; seed?: number;
  /** the colour that leads the reveal (blocks, slashes, bars), so scenes on the same ground still read as a change */ tint?: string};
type Kind = 'plus' | 'cross' | 'diamond' | 'blocks' | 'slashes' | 'chevron' | 'bands' | 'zoom' | 'bars';

const rect = (x: number, y: number, w: number, h: number) => `M${x} ${y}h${w}v${h}h${-w}Z`;
const poly = (pts: [number, number][]) => `M${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join('L')}Z`;
const turn = (pts: [number, number][], cx: number, cy: number, deg: number): [number, number][] => {
  const a = (deg * Math.PI) / 180;
  return pts.map(([x, y]) => [cx + x * Math.cos(a) - y * Math.sin(a), cy + x * Math.sin(a) + y * Math.cos(a)]);
};

/** A + (or ×) at (cx, cy): the arms shoot out long first, then thicken until they cover the frame. */
const plusShape = (p: number, cx: number, cy: number, deg: number) => {
  const L = 60 + Math.min(1, p * 2.2) * 2600;
  const a = 6 + Math.pow(p, 2.2) * 1500;
  const pts: [number, number][] = [[-a, -L], [a, -L], [a, -a], [L, -a], [L, a], [a, a], [a, L], [-a, L], [-a, a], [-L, a], [-L, -a], [-a, -a]];
  return poly(turn(pts, cx, cy, deg));
};

const diamondShape = (p: number, cx: number, cy: number) => {
  const r = p * 3100;
  return poly([[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]]);
};

const CELL = 120;
const blocksShape = (p: number, seed: number) => {
  let d = '';
  const cols = W / CELL;
  const rows = H / CELL;
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const t = 0.62 * ((c + r) / (cols + rows)) + 0.26 * hash(c, r, seed);
      const k = Math.min(1, Math.max(0, (p - t) / 0.12));
      if (k <= 0) continue;
      const s = CELL * k;
      d += rect(c * CELL + (CELL - s) / 2, r * CELL + (CELL - s) / 2, s + 0.5, s + 0.5);
    }
  }
  return d || 'M0 0Z';
};

/** Slanted stripes opening one after another. */
const slashesShape = (p: number, angle: number) => {
  const n = 10;
  const period = (W + H) / n;
  const lean = Math.tan((angle * Math.PI) / 180) * H;
  let d = '';
  for (let i = -1; i <= n + 1; i += 1) {
    const k = Math.min(1, Math.max(0, p * 1.6 - (i / n) * 0.6));
    if (k <= 0) continue;
    const x = i * period - lean / 2;
    const w = period * k + 1;
    d += poly([[x, 0], [x + w, 0], [x + w - lean, H], [x - lean, H]]);
  }
  return d || 'M0 0Z';
};

/** Everything left of a > edge sweeping right. */
const chevronEdge = (p: number) => -700 + p * (W + 1400);
const chevronShape = (p: number) => {
  const x = chevronEdge(p);
  return poly([[-10, -10], [x - 420, -10], [x, H / 2], [x - 420, H + 10], [-10, H + 10]]);
};

/** Staggered horizontal bars ("pulled strips"): each bar is led across by a band of `tint`, the new
 *  picture following it, in a few judder steps with a glitch offset — the strips of a torn frame. */
export const Bars: React.FC<{p: number; tint?: string; seed?: number; children: React.ReactNode; old?: React.ReactNode}> = ({p, tint = LIME, seed = 7, children, old}) => {
  const bars: {y: number; h: number; d: number; dir: number}[] = [];
  let y = 0;
  for (let i = 0; y < H; i += 1) {
    const h = 36 + Math.floor(hash(i, seed) * 6) * 26;
    bars.push({y, h, d: hash(i, seed, 2) * 0.45, dir: hash(i, seed, 3) < 0.5 ? 1 : -1});
    y += h;
  }
  const BAND = 260;
  return (
    <AbsoluteFill>
      {old}
      {bars.map((b, i) => {
        const k = Math.min(1, Math.max(0, (p - b.d) / 0.55));
        const steps = Math.floor(k * 9) / 9; // a judder: the bar moves in steps
        const e = (k < 1 ? steps : 1) * (W + BAND);
        const glitch = k > 0 && k < 1 && hash(i, Math.floor(p * 40)) < 0.25 ? (hash(i, Math.floor(p * 40), 1) - 0.5) * 80 : 0;
        const from = b.dir > 0 ? 0 : W - Math.max(0, e - BAND);
        const shown = Math.max(0, e - BAND);
        const bandX = b.dir > 0 ? Math.max(0, e - BAND) : W - e;
        return (
          <React.Fragment key={i}>
            {shown > 0 ? (
              <AbsoluteFill style={{clipPath: `polygon(${from}px ${b.y}px, ${from + shown}px ${b.y}px, ${from + shown}px ${b.y + b.h + 0.5}px, ${from}px ${b.y + b.h + 0.5}px)`,
                transform: `translateX(${glitch}px)`}}>{children}</AbsoluteFill>
            ) : null}
            {k > 0 && k < 1 ? <div style={{position: 'absolute', left: bandX, top: b.y, width: Math.min(BAND, e), height: b.h, background: tint,
              opacity: 0.92, transform: `translateX(${glitch * 0.5}px)`}} /> : null}
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};

const Edge: React.FC<{kind: Kind; p: number; x: number; y: number; angle: number}> = ({kind, p, x, y, angle}) => {
  // A thin lime/blue rim riding the shape's edge, so the reveal reads as a drawn line, not a cut.
  if (p <= 0.02 || p >= 0.98) return null;
  if (kind === 'diamond') {
    const r = p * 3100 + 18;
    return <svg width={W} height={H} style={{position: 'absolute', inset: 0}}><path d={poly([[x, y - r], [x + r, y], [x, y + r], [x - r, y]])} fill="none" stroke={LIME} strokeWidth={10} /></svg>;
  }
  if (kind === 'chevron') {
    const e = chevronEdge(p);
    return (
      <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
        <path d={poly([[e - 420, -10], [e, H / 2], [e - 420, H + 10], [e - 380, H + 10], [e + 40, H / 2], [e - 380, -10]])} fill={LIME} />
        <path d={poly([[e - 340, -10], [e + 80, H / 2], [e - 340, H + 10], [e - 320, H + 10], [e + 100, H / 2], [e - 320, -10]])} fill={BLUE} />
      </svg>
    );
  }
  if (kind === 'plus' || kind === 'cross') {
    const deg = (kind === 'cross' ? 45 : 0) + angle * (1 - p);
    return <svg width={W} height={H} style={{position: 'absolute', inset: 0}}><path d={plusShape(p * 1.02 + 0.004, x, y, deg)} fill="none" stroke={LIME} strokeWidth={8} /></svg>;
  }
  return null;
};

const BlockTint: React.FC<{p: number; seed: number; tint: string}> = ({p, seed, tint}) => {
  const cells: React.ReactNode[] = [];
  const cols = W / CELL;
  const rows = H / CELL;
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const t = 0.62 * ((c + r) / (cols + rows)) + 0.26 * hash(c, r, seed);
      const k = (p - t) / 0.12;
      if (k <= 0 || k >= 1.6) continue;
      const s = CELL * Math.min(1, k) * (k > 1 ? 1 - (k - 1) / 0.6 : 1);
      cells.push(<div key={`${r}-${c}`} style={{position: 'absolute', left: c * CELL + (CELL - s) / 2, top: r * CELL + (CELL - s) / 2, width: s, height: s, background: tint}} />);
    }
  }
  return <AbsoluteFill>{cells}</AbsoluteFill>;
};

const Presentation: React.FC<TransitionPresentationComponentProps<Props>> = ({children, presentationProgress: p, presentationDirection, passedProps}) => {
  const {kind, sound = 'whoosh', angle = 90, seed = 1, tint = LIME} = passedProps;
  // the opening point, measured while rendering when the scene's layout decides it
  const {x = W / 2, y = H / 2} = passedProps.at ? passedProps.at() : passedProps;
  if (presentationDirection === 'exiting') {
    // The old scene keeps moving under the reveal: pushed in toward the opening point.
    const scale = kind === 'zoom' ? 1 + Math.pow(p, 2) * 7 : 1 + p * 0.12;
    return (
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: `${x}px ${y}px`, opacity: kind === 'zoom' ? 1 - Math.max(0, p - 0.5) * 2 : 1}}>
        {children}
      </AbsoluteFill>
    );
  }
  let clip: string | undefined;
  let style: React.CSSProperties = {};
  if (kind === 'plus') clip = plusShape(p, x, y, angle * (1 - p));
  else if (kind === 'cross') clip = plusShape(p, x, y, 45 + angle * (1 - p));
  else if (kind === 'diamond') clip = diamondShape(p, x, y);
  else if (kind === 'blocks') clip = blocksShape(p, seed);
  else if (kind === 'slashes') clip = slashesShape(p, angle);
  else if (kind === 'chevron') clip = chevronShape(p);
  else if (kind === 'zoom') style = {transform: `scale(${0.35 + p * 0.65})`, transformOrigin: `${x}px ${y}px`, opacity: Math.min(1, p * 2.2)};
  const sfx = <Sfx name={sound} volume={0.55} />;
  const push: React.CSSProperties = kind === 'zoom' ? {} : {transform: `scale(${1.1 - 0.1 * p})`, transformOrigin: `${x}px ${y}px`};
  if (kind === 'bars') {
    return (
      <AbsoluteFill>
        {sfx}
        <Sfx name="glitch" volume={0.3} />
        <Bars p={p} tint={tint} seed={seed}><AbsoluteFill style={push}>{children}</AbsoluteFill></Bars>
      </AbsoluteFill>
    );
  }
  if (kind === 'bands') {
    // Six bands of the new scene slide in from alternate sides, one after another.
    const n = 6;
    return (
      <AbsoluteFill>
        {sfx}
        {Array.from({length: n}, (_, i) => {
          const k = Math.min(1, Math.max(0, p * 1.5 - (i / n) * 0.5));
          const e = 1 - Math.pow(1 - k, 3);
          return (
            <AbsoluteFill key={i} style={{clipPath: `polygon(0 ${(i / n) * 100}%, 100% ${(i / n) * 100}%, 100% ${((i + 1) / n) * 100 + 0.1}%, 0 ${((i + 1) / n) * 100 + 0.1}%)`,
              transform: `translateX(${(1 - e) * (i % 2 ? 1 : -1) * W}px)`}}>
              {children}
            </AbsoluteFill>
          );
        })}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill>
      {sfx}
      <AbsoluteFill style={{clipPath: clip ? `path('${clip}')` : undefined, ...style}}><AbsoluteFill style={push}>{children}</AbsoluteFill></AbsoluteFill>
      {kind === 'blocks' ? <BlockTint p={p} seed={seed} tint={tint} /> : null}
      <Edge kind={kind} p={p} x={x} y={y} angle={angle} />
    </AbsoluteFill>
  );
};

export const reveal = (props: Props): TransitionPresentation<Props> => ({component: Presentation, props});
