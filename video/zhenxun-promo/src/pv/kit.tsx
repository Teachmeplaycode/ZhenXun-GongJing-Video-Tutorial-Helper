import React, {createContext, useContext, useLayoutEffect, useRef} from 'react';
import {AbsoluteFill, Audio, continueRender, delayRender, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';
import {loadFont as loadSC} from '@remotion/google-fonts/NotoSansSC';
import {loadFont as loadDisplay} from '@remotion/google-fonts/Unbounded';
import {loadFont as loadConsole} from '@remotion/google-fonts/VT323';
import {loadFont as loadSilk} from '@remotion/google-fonts/Silkscreen';

// The PV's kit: the site's day theme (front/src/styles/tokens.css: paper, ink, lime), fonts, and
// the primitives every scene is made of. Everything is drawn from the frame number (no CSS
// animation), so a frame always renders the same.
export const PAPER = '#F5F3EF'; // --bg-canvas
export const SURFACE = '#FFFFFF'; // --bg-surface
export const INK = '#1A1A1A'; // --text-primary
export const INK2 = '#6B6B6B'; // --text-secondary
export const INK3 = '#9B9B9B'; // --text-tertiary
export const LINE = '#E0DDD8'; // --border-default
export const LINE2 = '#C8C4BD'; // --border-strong
export const SHADE = '#D8D4CE'; // --sculpture-shadow
export const LIME = '#C8F04A'; // --accent-active
export const LIME_DIM = '#A8CC3A'; // --accent-active-dim
export const AMBER = '#F5A623'; // --accent-processing (the contour loader's pen)
// the night side (from the click scene to the slogan): GSAP-style warm black and cream
export const NIGHT = '#0E100F';
export const CREAM = '#FFFCE1';
export const GREEN = '#7FE36A'; // the lime's partner in gradients

/** The current side — light (paper) or dark (night) — so the shared pieces draw in its colours. */
export type Tone = {dark: boolean; bg: string; fg: string; fg2: string; fg3: string; line: string; line2: string};
export const LIGHT: Tone = {dark: false, bg: '#F5F3EF', fg: '#1A1A1A', fg2: '#6B6B6B', fg3: '#9B9B9B', line: '#E0DDD8', line2: '#C8C4BD'};
export const DARK: Tone = {dark: true, bg: NIGHT, fg: CREAM, fg2: '#BDBAA6', fg3: '#7D7E72', line: '#24272A', line2: '#3B3F3C'};
const ToneCtx = createContext<Tone>(LIGHT);
export const useTone = () => useContext(ToneCtx);
export const ToneProvider = ToneCtx.Provider;
// older names, kept so the scenes read the same: the ground, the foreground, a second ink, faint marks
export const BG = PAPER;
export const WHITE = INK;
export const BLUE = INK;
export const DIM = LINE2;

export const MONO = `${loadMono('normal', {weights: ['500', '700', '800']}).fontFamily}, Menlo, monospace`;
export const SC = `${loadSC('normal', {weights: ['500', '900']}).fontFamily}, "PingFang SC", sans-serif`;
/** The site's English title face (Unbounded), used for the wordmark and Latin display type. */
export const DISPLAY = `${loadDisplay('normal', {weights: ['700', '900']}).fontFamily}, Arial, sans-serif`;
export const WORDMARK = DISPLAY;
/** A terminal face for code, timecodes and counters. */
export const CONSOLE = `${loadConsole('normal', {weights: ['400']}).fontFamily}, Menlo, monospace`;
/** A pixel face for Latin HUD labels. */
export const SILK = `${loadSilk('normal', {weights: ['400', '700']}).fontFamily}, Menlo, monospace`;
/** A Chinese pixel face (Fusion Pixel 12px, OFL — public/fonts/pixel-zh.OFL.txt): crisp at multiples of 12 px. */
export const PIXEL = 'ZXPixel, "PingFang SC", sans-serif';

const pixelReady = (() => {
  if (typeof document === 'undefined') return;
  const handle = delayRender('pixel font');
  const face = new FontFace('ZXPixel', `url(${staticFile('fonts/pixel-zh.woff2')}) format('woff2')`);
  face.load().then((f) => { (document.fonts as unknown as {add: (font: FontFace) => void}).add(f); continueRender(handle); }).catch(() => continueRender(handle));
  return true;
})();
void pixelReady;

/** Deterministic noise: the same cell and tick always give the same number in [0, 1). */
export const hash = (a: number, b = 0, c = 0) => {
  let h = Math.imul(a | 0, 374761393) ^ Math.imul(b | 0, 668265263) ^ Math.imul(c | 0, 2147483647);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
/** Stepped time: the frame rounded down to `fps` steps a second (the PV's judder). */
export const stepped = (frame: number, fps: number, steps = 12) => Math.floor(frame / (fps / steps));

/** A snappy spring from 0 to 1 starting at `at` (a little overshoot), for things arriving. */
export const pop = (frame: number, at: number, fps: number, stiff = 180) =>
  spring({frame: frame - at, fps, config: {damping: 14, stiffness: stiff, mass: 0.7}});

// Sound effects: Pixabay Content License (public/sfx/CREDITS.md), free for commercial use.
const SFX = {
  key: 'key-press', click: 'click', soft: 'click-soft', pop: 'pop', whoosh: 'whoosh-short', swish: 'whoosh-cinematic',
  impact: 'impact-bass-1', swell: 'impact-bass-2', riser: 'riser', sparkle: 'sparkle', glitch: 'glitch-3', hit: 'glitch-1', ping: 'ping',
} as const;
export type SfxName = keyof typeof SFX;

/** One sound starting `at` frames into the current sequence. */
export const Sfx: React.FC<{name: SfxName; at?: number; volume?: number; rate?: number; startFrom?: number}> = ({name, at = 0, volume = 0.5, rate = 1, startFrom}) => (
  <Sequence from={Math.max(0, Math.round(at))} layout="none">
    <Audio src={staticFile(`sfx/${SFX[name]}.mp3`)} volume={volume} playbackRate={rate} startFrom={startFrom} />
  </Sequence>
);

const CHARSETS = {
  code: '/\\<>[]{}=+*#:;.-_|01',
  marks: '+*x/<>|.:',
  digits: '0123456789',
  han: '帧寻看见画面原声文字证据回看卡点',
};

/** A canvas character field: `cell` px cells over the frame, each a char from `set`, coloured by
 *  `paint(col, row, tick)` → a colour or null (empty). Redrawn every frame. */
export const CharField: React.FC<{cell?: number; set?: keyof typeof CHARSETS | string; fps?: number;
  paint: (col: number, row: number, tick: number, cols: number, rows: number) => string | null; style?: React.CSSProperties}> = ({cell = 22, set = 'code', fps = 12, paint, style}) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const frame = useCurrentFrame();
  const {width, height, fps: rate} = useVideoConfig();
  const chars = CHARSETS[set as keyof typeof CHARSETS] ?? set;
  useLayoutEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, width, height);
    ctx.font = `700 ${cell * 0.82}px ${MONO}`;
    ctx.textBaseline = 'top';
    const tick = stepped(frame, rate, fps);
    const cols = Math.ceil(width / (cell * 0.62));
    const rows = Math.ceil(height / cell);
    for (let r = 0; r < rows; r += 1) {
      for (let c = 0; c < cols; c += 1) {
        const color = paint(c, r, tick, cols, rows);
        if (!color) continue;
        ctx.fillStyle = color;
        ctx.fillText(chars[Math.floor(hash(c, r, tick) * chars.length)], c * cell * 0.62, r * cell);
      }
    }
  }, [frame, width, height, cell, chars, fps, rate, paint]);
  return <canvas ref={ref} width={width} height={height} style={{position: 'absolute', inset: 0, ...style}} />;
};

/** The HUD: X, + and * glyphs drifting and turning all the time, in the corners and margins. */
export const Glyphs: React.FC<{count?: number; seed?: number; opacity?: number}> = ({count = 14, seed = 1, opacity = 0.9}) => {
  const frame = useCurrentFrame();
  const tone = useTone();
  const {width, height} = useVideoConfig();
  const glyphs = ['×', '+', '*', '×', '+'];
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {Array.from({length: count}, (_, i) => {
        const r = (k: number) => hash(i, seed, k);
        const edge = r(1) < 0.5; // hug the left/right margins or the top/bottom bands
        const x = edge ? (r(2) < 0.5 ? r(3) * 0.14 : 0.86 + r(3) * 0.12) * width : r(3) * width;
        const y = edge ? r(4) * height : (r(5) < 0.5 ? r(4) * 0.13 : 0.87 + r(4) * 0.11) * height;
        const size = 22 + r(6) * 46;
        const spin = (r(7) < 0.5 ? -1 : 1) * (40 + r(8) * 140); // degrees a second
        const drift = Math.sin(frame / 60 * (0.6 + r(9)) + r(10) * 6) * 14;
        const blink = hash(i, seed, Math.floor(frame / 9)) < 0.08 ? 0.25 : 1;
        const color = [tone.fg, tone.dark ? LIME : LIME_DIM, tone.fg3][Math.floor(r(11) * 3)];
        return (
          <div key={i} style={{position: 'absolute', left: x, top: y + drift, fontFamily: MONO, fontWeight: 800, fontSize: size,
            color, opacity: opacity * blink, transform: `rotate(${(frame / 60) * spin + r(12) * 360}deg)`, lineHeight: 1}}>
            {glyphs[Math.floor(r(13) * glyphs.length)]}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

/** An ink pixel arrow (or a pointing hand) made of squares, outlined in paper. */
export const PixelCursor: React.FC<{x: number; y: number; hand?: boolean; size?: number; press?: number}> = ({x, y, hand = false, size = 5, press = 0}) => {
  const tone = useTone();
  const arrow = ['X', 'XX', 'X.X', 'X..X', 'X...X', 'X....X', 'X.....X', 'X..XXXX', 'X.X', 'XX', 'X'];
  const glove = ['...XX', '...X.X', '...X.X', '...X.XXX', 'XX.X.X.XX', 'X.XX.....X', 'X..X.....X', '.X.......X', '..X......X', '...X....X', '....XXXXX'];
  const map = hand ? glove : arrow;
  return (
    <svg style={{position: 'absolute', left: x, top: y, transform: `scale(${1 - press * 0.15})`, transformOrigin: '0 0', overflow: 'visible'}}
      width={12 * size} height={12 * size}>
      {map.flatMap((row, r) => Array.from(row).map((ch, c) => (ch === 'X' ? <rect key={`${r}-${c}`} x={c * size} y={r * size} width={size} height={size} fill={tone.fg} />
        : ch === '.' ? <rect key={`${r}-${c}`} x={c * size} y={r * size} width={size} height={size} fill={tone.bg} /> : null)))}
    </svg>
  );
};

/** Text typed in at `cps` characters a second from frame `at`, a block caret after it while typing,
 *  a key sound on every character. */
export const Typed: React.FC<{text: string; at: number; cps?: number; style?: React.CSSProperties; caret?: string; sound?: boolean}> = ({text, at, cps = 30, style, caret = LIME_DIM, sound = true}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = Math.max(0, Math.floor(((frame - at) / fps) * cps));
  const chars = Array.from(text);
  const keys = sound ? chars.map((ch, i) => (ch.trim() ? <Sfx key={i} name="key" at={at + (i * fps) / cps} volume={0.22 + hash(i, at) * 0.14} rate={0.92 + hash(i, at, 1) * 0.2} /> : null)) : null;
  return (
    <>
      {keys}
      {frame < at ? null : (
        <span style={style}>
          {chars.slice(0, n).join('')}
          {n < chars.length || Math.floor(frame / 15) % 2 === 0 ? <span style={{color: caret}}>▌</span> : null}
        </span>
      )}
    </>
  );
};

export const Fill: React.FC<{children?: React.ReactNode; grid?: boolean; dark?: boolean}> = ({children, grid = true, dark = false}) => {
  const tone = dark ? DARK : LIGHT;
  return (
    <ToneProvider value={tone}>
      <AbsoluteFill style={{background: tone.bg, overflow: 'hidden'}}>
        {grid ? <Paper /> : null}
        {children}
      </AbsoluteFill>
    </ToneProvider>
  );
};

/** The ground: a faint dot grid with a + at every fourth crossing, like a survey sheet. */
export const Paper: React.FC = () => {
  const {width, height} = useVideoConfig();
  const tone = useTone();
  const id = tone.dark ? 'd' : 'l';
  return (
    <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
      <defs>
        <pattern id={`zx-dots-${id}`} width={40} height={40} patternUnits="userSpaceOnUse"><circle cx={1} cy={1} r={1.3} fill={tone.line2} /></pattern>
        <pattern id={`zx-cross-${id}`} width={160} height={160} patternUnits="userSpaceOnUse"><path d="M-7 0H7M0 -7V7M153 0H167M160 -7V7M-7 160H7M0 153V167M153 160H167M160 153V167" stroke={tone.fg3} strokeWidth={1.4} /></pattern>
      </defs>
      <rect width={width} height={height} fill={`url(#zx-dots-${id})`} opacity={0.7} />
      <rect width={width} height={height} fill={`url(#zx-cross-${id})`} opacity={0.5} />
    </svg>
  );
};

/** Film grain over everything (the frosted, printed feel): fresh noise every other frame. */
export const Grain: React.FC<{opacity?: number}> = ({opacity = 0.11}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const seed = Math.floor(frame / 2) % 24;
  return (
    <svg width={width} height={height} style={{position: 'absolute', inset: 0, pointerEvents: 'none', opacity, mixBlendMode: 'overlay'}}>
      <filter id={`zx-grain-${seed}`}><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={seed} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
      <rect width={width} height={height} filter={`url(#zx-grain-${seed})`} />
    </svg>
  );
};

/** A soft gradient shape with grain, like the GSAP site's: lime into green, drifting. */
export const Blob: React.FC<{x: number; y: number; r: number; from?: string; to?: string; opacity?: number; turn?: number}> = ({x, y, r, from = LIME, to = '#2FE0A8', opacity = 0.9, turn = 0}) => (
  <div style={{position: 'absolute', left: x - r, top: y - r, width: r * 2, height: r * 2, borderRadius: '42% 58% 55% 45% / 48% 40% 60% 52%', opacity,
    background: `radial-gradient(circle at 30% 28%, #F4FFB8 0%, ${from} 32%, ${to} 100%)`, transform: `rotate(${turn}deg)`}}>
    <svg width={r * 2} height={r * 2} style={{position: 'absolute', inset: 0, borderRadius: 'inherit', mixBlendMode: 'overlay', opacity: 0.6}}>
      <filter id={`zx-blob-${Math.round(r)}`}><feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="1" seed={3} /><feColorMatrix type="saturate" values="0" /></filter>
      <rect width={r * 2} height={r * 2} filter={`url(#zx-blob-${Math.round(r)})`} />
    </svg>
  </div>
);

/** A big index numeral in outline (ink stroke, no fill), the section marker of the UI. */
export const Index: React.FC<{n: string; size?: number; style?: React.CSSProperties}> = ({n, size = 220, style}) => {
  const tone = useTone();
  return <span style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: size, lineHeight: 0.8, color: 'transparent', WebkitTextStroke: `2px ${tone.fg}`, letterSpacing: -6, ...style}}>{n}</span>;
};

/** A hairline that draws on from its start (0 → 1). */
export const Rule: React.FC<{x: number; y: number; w: number; k: number; color?: string; thick?: number; vertical?: boolean}> = ({x, y, w, k, color, thick = 2, vertical = false}) => {
  const tone = useTone();
  return <div style={{position: 'absolute', left: x, top: y, width: vertical ? thick : w * clamp01(k), height: vertical ? w * clamp01(k) : thick, background: color ?? tone.fg}} />;
};

/** Diagonal stripes in a strip: the PV's one hazard-tape accent (lime and ink), used sparingly. */
export const Hatch: React.FC<{x: number; y: number; w: number; h: number; k?: number; shift?: number}> = ({x, y, w, h, k = 1, shift = 0}) => (
  <div style={{position: 'absolute', left: x, top: y, width: w * clamp01(k), height: h, overflow: 'hidden',
    background: `repeating-linear-gradient(-45deg, ${INK} 0 6px, transparent 6px 14px)`, backgroundPosition: `${shift}px 0`, opacity: 0.85}} />
);

/** Width of `text` in a CSS font (e.g. `900 260px ${SC}`), measured now — call it while rendering a
 *  frame, after the fonts have loaded, so centred layouts come out centred. */
export const textWidth = (text: string, font: string, letterSpacing = 0) => {
  if (typeof document === 'undefined') return text.length * 10;
  const ctx = document.createElement('canvas').getContext('2d')!;
  ctx.font = font;
  return ctx.measureText(text).width + letterSpacing * Array.from(text).length;
};

/** A section header in the UI's manner: an outline index numeral, a title, a hairline drawing on
 *  under them and a small second line. No box. */
export const Head: React.FC<{n: string; title: string; sub?: string; at?: number; x?: number; y?: number}> = ({n, title, sub, at = 0, x = 96, y = 82}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = pop(frame, at, fps, 200);
  const tone = useTone();
  return (
    <>
      <div style={{position: 'absolute', left: x, top: y, display: 'flex', alignItems: 'flex-end', gap: 22, transform: `translateX(${(1 - k) * -60}px)`, opacity: clamp01(k * 2)}}>
        <Index n={n} size={132} />
        <div style={{display: 'flex', flexDirection: 'column', gap: 2, paddingBottom: 4}}>
          <span style={{fontFamily: PIXEL, fontSize: 48, color: tone.fg}}>{title}</span>
          {sub ? <span style={{fontFamily: CONSOLE, fontSize: 32, color: tone.fg2}}>{sub}</span> : null}
        </div>
      </div>
      <Rule x={x} y={y + 128} w={460} k={easeOut((frame - at - 4) / 22)} />
      <Rule x={x + 470} y={y + 124} w={10} k={frame > at + 20 ? 1 : 0} thick={10} color={LIME} />
    </>
  );
};
