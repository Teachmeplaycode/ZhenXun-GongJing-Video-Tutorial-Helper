import React, {useLayoutEffect, useRef} from 'react';
import {AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';
import {loadFont as loadSC} from '@remotion/google-fonts/NotoSansSC';

// The PV's kit: colours (帧寻's lime; the site's 画面 blue; white on near-black), fonts, and the
// primitives every scene is made of. Everything is drawn from the frame number (no CSS animation),
// so a frame always renders the same.
export const BG = '#0B0C09';
export const LIME = '#C8F04A';
export const BLUE = '#3B6EFF';
export const WHITE = '#F5F3EF';
export const DIM = '#3A3F2C';

export const MONO = `${loadMono('normal', {weights: ['500', '700', '800']}).fontFamily}, Menlo, monospace`;
export const SC = `${loadSC('normal', {weights: ['500', '900']}).fontFamily}, "PingFang SC", sans-serif`;
export const WORDMARK = 'ZXWordmark, Arial, sans-serif';

const wordmarkReady = (() => {
  if (typeof document === 'undefined') return;
  const handle = delayRender('wordmark font');
  const face = new FontFace('ZXWordmark', `url(${staticFile('fonts/wordmark.woff2')}) format('woff2')`, {weight: '700'});
  face.load().then((f) => { (document.fonts as unknown as {add: (font: FontFace) => void}).add(f); continueRender(handle); }).catch(() => continueRender(handle));
  return true;
})();
void wordmarkReady;

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
        const color = [LIME, BLUE, WHITE][Math.floor(r(11) * 3)];
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

/** A white pixel arrow (or a pointing hand) made of squares, like the reference's cursors. */
export const PixelCursor: React.FC<{x: number; y: number; hand?: boolean; size?: number; press?: number}> = ({x, y, hand = false, size = 5, press = 0}) => {
  const arrow = ['X', 'XX', 'X.X', 'X..X', 'X...X', 'X....X', 'X.....X', 'X..XXXX', 'X.X', 'XX', 'X'];
  const glove = ['...XX', '...X.X', '...X.X', '...X.XXX', 'XX.X.X.XX', 'X.XX.....X', 'X..X.....X', '.X.......X', '..X......X', '...X....X', '....XXXXX'];
  const map = hand ? glove : arrow;
  return (
    <svg style={{position: 'absolute', left: x, top: y, transform: `scale(${1 - press * 0.15})`, transformOrigin: '0 0', overflow: 'visible'}}
      width={12 * size} height={12 * size}>
      {map.flatMap((row, r) => Array.from(row).map((ch, c) => (ch === 'X' ? <rect key={`${r}-${c}`} x={c * size} y={r * size} width={size} height={size} fill={WHITE} />
        : ch === '.' ? <rect key={`${r}-${c}`} x={c * size} y={r * size} width={size} height={size} fill={BG} /> : null)))}
    </svg>
  );
};

/** Text typed in at `cps` characters a second from frame `at`, a block caret after it while typing. */
export const Typed: React.FC<{text: string; at: number; cps?: number; style?: React.CSSProperties; caret?: string}> = ({text, at, cps = 24, style, caret = LIME}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = Math.max(0, Math.floor(((frame - at) / fps) * cps));
  const chars = Array.from(text);
  if (frame < at) return null;
  return (
    <span style={style}>
      {chars.slice(0, n).join('')}
      {n < chars.length || Math.floor(frame / 15) % 2 === 0 ? <span style={{color: caret}}>▌</span> : null}
    </span>
  );
};

export const Fill: React.FC<{children?: React.ReactNode}> = ({children}) => <AbsoluteFill style={{background: BG, overflow: 'hidden'}}>{children}</AbsoluteFill>;
