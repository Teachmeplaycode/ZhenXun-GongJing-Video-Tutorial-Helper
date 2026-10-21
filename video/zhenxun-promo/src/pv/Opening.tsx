import React, {useCallback, useMemo} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BG, BLUE, CharField, clamp01, CONSOLE, DIM, easeOut, Fill, Glyphs, hash, LIME, MONO, PIXEL, PixelCursor, pop, SC, Sfx, SILK, stepped, Typed, WHITE, WORDMARK} from './kit';

// The first ten seconds — cut into the deck on its own — ending on the name:
//   Greeting   >( 帧 )=  →  >( 帧, 画面 )={<  … 原声 / 文字 / 证据; then the film zooms into the 帧
//   Stream     a character field, a big 帧 in blue blocks, a frame counter and a timecode running
//   NameWall   rows slide in (帧 / 寻 / GongJ!ng?); a lime wall types over them with 帧寻 cut out;
//              the wall drains away and the cut-out 帧寻 itself becomes the title, which settles
//              into the lockup: 帧寻 GongJ!ng?, 看见，再求证。

/** Cells covered by `text` drawn big in the middle of a cols×rows character grid (true = inside a
 *  stroke). Cells are 0.62 as wide as tall, so the text is drawn stretched to come out upright. */
export function textMask(text: string, cols: number, rows: number, font: string, scale = 0.8): boolean[][] {
  if (typeof document === 'undefined') return [];
  const canvas = document.createElement('canvas');
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext('2d')!;
  const stretch = 1 / 0.62;
  ctx.fillStyle = '#fff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `900 ${Math.floor(rows * scale)}px ${font}`;
  const fit = Math.min(1, (cols * 0.92) / (ctx.measureText(text).width * stretch));
  ctx.font = `900 ${Math.floor(rows * scale * fit)}px ${font}`;
  ctx.setTransform(stretch, 0, 0, 1, cols / 2, 0);
  ctx.fillText(text, 0, rows / 2 + rows * 0.03);
  const data = ctx.getImageData(0, 0, cols, rows).data;
  return Array.from({length: rows}, (_, r) => Array.from({length: cols}, (_, c) => data[(r * cols + c) * 4 + 3] > 110));
}

// ---------------------------------------------------------------- Greeting
const WORDS = ['', '画面', '原声', '文字', '证据'];
/** Where 帧 sits in the greeting: the next scene zooms out of this point. */
export const GREETING_ZHEN = {x: 960, y: 410};

const Greeting: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const step = frame < 24 ? 0 : Math.min(WORDS.length - 1, 1 + Math.floor((frame - 24) / 22));
  const word = WORDS[step];
  const since = step === 0 ? frame : (frame - 24) % 22;
  // Each new word arrives scrambled for a few frames, then settles.
  const scramble = since < 6 && word ? Array.from(word).map((_, i) => '帧寻画面原声文字证据回看'[Math.floor(hash(i, frame) * 12)]).join('') : word;
  const enter = pop(frame, 0, fps);
  const bars = useCallback((c: number, r: number, tick: number, cols: number, rows: number) => {
    // The reference's ragged code bars: a band in the lower third, runs of blue and lime.
    if (r < rows * 0.62 || r > rows * 0.82) return null;
    const run = Math.floor((c + tick * (r % 2 ? 2 : -1)) / 7);
    if (run * 7 > (frame / 30) * cols * 1.4) return null; // the band runs in from the left
    const on = hash(run, r) < 0.55;
    if (!on) return hash(c, r, tick) < 0.06 ? DIM : null;
    return hash(run, r, 3) < 0.45 ? BLUE : hash(run, r, 4) < 0.5 ? LIME : WHITE;
  }, [frame]);
  const right = word ? `, ${scramble} )={<` : ' )=';
  const cursorX = GREETING_ZHEN.x + 90 + (word ? (2 + word.length) * 105 : 160) + Math.sin(frame / 9) * 6;
  return (
    <Fill>
      <CharField cell={20} set="code" fps={15} paint={bars} style={{opacity: 0.9}} />
      {[1, 2, 3, 4].map((s) => <Sfx key={s} name="key" at={24 + (s - 1) * 22} volume={0.4} />)}
      <Sfx name="glitch" volume={0.25} />
      <div style={{position: 'absolute', left: 92, top: 70, fontFamily: CONSOLE, fontSize: 40, color: BG, background: LIME, padding: '0 12px',
        clipPath: `inset(0 ${(1 - enter) * 100}% 0 0)`}}>// ---[ + ]</div>
      <div style={{position: 'absolute', right: 96, bottom: 70, fontFamily: CONSOLE, fontSize: 44, color: '#8B9171'}}>const 帧寻 = {'{'}</div>
      <div style={{position: 'absolute', top: GREETING_ZHEN.y - 80, height: 160, left: 0, right: 0, fontFamily: MONO, fontWeight: 800, fontSize: 132, color: BLUE,
        letterSpacing: -2, whiteSpace: 'nowrap', transform: `scale(${0.7 + enter * 0.3})`, transformOrigin: `${GREETING_ZHEN.x}px 80px`}}>
        <span style={{position: 'absolute', right: 1920 - GREETING_ZHEN.x + 76, lineHeight: '160px'}}>{'>('}</span>
        <span style={{position: 'absolute', left: GREETING_ZHEN.x - 66, width: 132, textAlign: 'center', fontFamily: SC, fontWeight: 900, color: LIME, lineHeight: '160px'}}>帧</span>
        <span style={{position: 'absolute', left: GREETING_ZHEN.x + 76, lineHeight: '160px'}}>
          {word ? <>, <span style={{fontFamily: PIXEL, fontSize: 132, color: LIME}}>{scramble}</span> )={'{<'}</> : right}
        </span>
      </div>
      <PixelCursor x={cursorX} y={GREETING_ZHEN.y + 70 + Math.cos(frame / 11) * 5} size={6} />
      <Glyphs count={10} seed={2} opacity={0.75} />
    </Fill>
  );
};

// ---------------------------------------------------------------- Stream
const Stream: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cols = Math.ceil(1920 / (22 * 0.62));
  const rows = Math.ceil(1080 / 22);
  const mask = useMemo(() => textMask('帧', cols, rows, SC, 0.86), [cols, rows]);
  const grow = easeOut(frame / 26); // the glyph fills in
  const paint = useCallback((c: number, r: number, tick: number) => {
    const inside = mask[r]?.[c];
    if (inside) return hash(c, r, 7) < grow ? (hash(c, r, tick) < 0.9 ? BLUE : WHITE) : null;
    const lane = r % 3 === 0;
    const moving = (c + tick * (lane ? 3 : 1)) % 47 < (lane ? 22 : 6);
    if (!moving) return hash(c, r, tick) < 0.03 ? DIM : null;
    const near = mask[r]?.[c - 3] || mask[r]?.[c + 3] || mask[r - 1]?.[c] || mask[r + 1]?.[c]; // keep the glyph's edge clear
    if (near) return null;
    return hash(c, r) < 0.55 ? '#7E8C3C' : hash(c, r, 1) < 0.6 ? LIME : '#4A5230';
  }, [mask, grow]);
  const t = (frame / fps) * 7.5; // the timecode runs fast
  const tc = `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`;
  const n = String(Math.min(3600, Math.floor(frame * 24))).padStart(4, '0');
  const a = pop(frame, 10, fps);
  const b = pop(frame, 18, fps);
  return (
    <Fill>
      <CharField cell={22} set="code" fps={20} paint={paint} />
      <div style={{position: 'absolute', right: 120, top: 92, fontFamily: CONSOLE, fontSize: 64, color: WHITE, background: BG, padding: '0 16px',
        transform: `translateY(${(1 - a) * -80}px)`}}>
        t = "<span style={{color: LIME}}>{tc}</span>"
      </div>
      <div style={{position: 'absolute', left: 120, bottom: 96, fontFamily: CONSOLE, fontSize: 64, color: WHITE, background: BG, padding: '0 16px',
        transform: `translateY(${(1 - b) * 80}px)`}}>
        帧 = <span style={{color: BLUE}}>{n}</span> / 3600
      </div>
      <Glyphs count={8} seed={5} opacity={0.8} />
    </Fill>
  );
};

// ---------------------------------------------------------------- the lockup (shared with the next scene)
/** Where the lockup's lime rule sits; the next scene starts from it. */
export const RULE = {y: 650, left: 400, width: 1120};
const TITLE_Y = 470; // centre line of 帧寻 GongJ!ng?
const TITLE_SIZE = 260;
/** 帧寻's centre in the lockup (the cut-out in the wall flies to it). */
const ZX_CENTER = {x: 640, y: TITLE_Y};

export const NameLockup: React.FC<{
  /** frames since the title started settling (0 = the big 帧寻 in the middle) */ t: number;
  /** 0 → 1: the title and the line under it leave upward, the rule stays */ exit?: number;
}> = ({t, exit = 0}) => {
  const {fps} = useVideoConfig();
  const settle = pop(t, 0, fps, 120);
  const big = 648 / TITLE_SIZE; // the cut-out in the wall was this much bigger
  const zx = `translate(${(1 - settle) * (960 - ZX_CENTER.x)}px, ${(1 - settle) * (572 - ZX_CENTER.y)}px) scale(${big + (1 - big) * settle})`;
  const g = easeOut((t - 14) / 16);
  const rule = easeOut((t - 18) / 18);
  const steps = stepped(t, 60, 12);
  const up = easeOut(exit);
  return (
    <>
      <div style={{position: 'absolute', left: 0, right: 0, top: TITLE_Y - TITLE_SIZE / 2, height: TITLE_SIZE,
        transform: `translateY(${-up * 120}px)`, clipPath: exit > 0 ? `inset(-400px 0 ${up * 100}% 0)` : undefined}}>
        <span style={{position: 'absolute', left: ZX_CENTER.x - TITLE_SIZE, width: TITLE_SIZE * 2, textAlign: 'center', fontFamily: SC, fontWeight: 900, fontSize: TITLE_SIZE,
          color: WHITE, lineHeight: `${TITLE_SIZE}px`, transform: zx, transformOrigin: '50% 50%', whiteSpace: 'nowrap'}}>帧寻</span>
        <span style={{position: 'absolute', left: ZX_CENTER.x + TITLE_SIZE + 54, top: (TITLE_SIZE - 136) / 2 + 10, fontFamily: WORDMARK, fontWeight: 700, fontSize: 136, color: WHITE,
          letterSpacing: -6, lineHeight: 1, whiteSpace: 'nowrap', clipPath: `inset(${(1 - g) * 100}% 0 0 0)`, transform: `translateY(${(1 - g) * 40}px)`}}>
          GongJ<span style={{color: LIME}}>!</span>ng<span style={{color: LIME}}>{steps % 10 < 7 ? '?' : '!'}</span>
        </span>
      </div>
      {exit > 0 ? null : <div style={{position: 'absolute', left: RULE.left, top: RULE.y - 3, width: RULE.width, height: 6, background: LIME, transform: `scaleX(${rule})`, transformOrigin: '0 50%'}} />}
      <div style={{position: 'absolute', left: 0, right: 0, top: RULE.y + 36, display: 'flex', justifyContent: 'center', alignItems: 'center', fontFamily: SILK, fontWeight: 700, fontSize: 52, color: LIME, gap: 26,
        transform: `translateY(${-up * 60}px)`, opacity: 1 - up}}>
        <span style={{color: BLUE, opacity: t > 26 ? 1 : 0}}>*//</span>
        <Typed text="看见，再求证。" at={30} cps={22} style={{fontFamily: PIXEL, fontSize: 60, color: WHITE}} sound={exit === 0} />
        <span style={{color: BLUE, opacity: t > 26 ? 1 : 0}}>{'>>'}</span>
      </div>
    </>
  );
};

// ---------------------------------------------------------------- NameWall
const ROWS = [
  {lead: '////////////', word: '帧', color: BLUE, font: SC},
  {lead: '>>>>>>>>>>>>', word: '寻', color: LIME, font: SC},
  {lead: '[[[[[[[[[[[[', word: 'GongJ!ng?', color: WHITE, font: WORDMARK},
];
const WALL_AT = 72; // the wall starts typing over the rows
const HOLE_AT = 100; // 帧寻 is cut out of it
const FILL_AT = 118; // the cut-out fills with white characters
const DRAIN_AT = 150; // the wall drains away; the white 帧寻 becomes the title
const TITLE_AT = 164;

const NameWall: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cols = Math.ceil(1920 / (24 * 0.62));
  const rows = Math.ceil(1080 / 24);
  const mask = useMemo(() => textMask('帧寻', cols, rows, SC, 0.6), [cols, rows]);
  const paint = useCallback((c: number, r: number, tick: number) => {
    // Typing in: each row fills left to right, a few frames after the row above.
    const typed = (frame - WALL_AT - r * 0.6) * 9;
    if (c > typed) return null;
    // Draining: each column falls away (cells drop by `drop` rows), staggered.
    const drop = frame < DRAIN_AT ? 0 : Math.pow(Math.max(0, frame - DRAIN_AT - hash(c, 4) * 14) / 6, 2);
    const src = Math.floor(r - drop);
    if (src < 0) return null;
    if (mask[r]?.[c]) {
      // the cut-out: empty, then filling with white; it stays put while the wall drains
      if (frame < HOLE_AT || hash(c, r, 9) > easeOut((frame - HOLE_AT) / 12)) return frame < HOLE_AT ? LIME : null;
      if (frame >= TITLE_AT + 4) return null; // the solid title has taken over
      return hash(c, r, 11) < easeOut((frame - FILL_AT) / 14) ? WHITE : null;
    }
    if (mask[src]?.[c]) return null;
    return hash(c, src, tick) < 0.92 ? LIME : '#7E8C3C';
  }, [mask, frame]);
  return (
    <Fill>
      {frame < WALL_AT + 40 ? (
        <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 150, gap: 26}}>
          {ROWS.map((row, i) => {
            const start = 4 + i * 9;
            const k = pop(frame, start, fps, 220);
            const steps = stepped(frame - start, 60, 20);
            const leadShown = row.lead.slice(0, Math.max(0, Math.min(row.lead.length, steps * 3)));
            const settled = frame - start > 12;
            return (
              <div key={i} style={{display: 'flex', alignItems: 'center', gap: 34, transform: `translateX(${(1 - k) * (i % 2 ? 700 : -700)}px)`, opacity: frame >= start ? 1 : 0}}>
                <Sfx name="whoosh" at={start} volume={0.3} rate={1.2} />
                <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 108, color: row.color, letterSpacing: -4}}>{leadShown}</span>
                <span style={{fontFamily: row.font, fontWeight: 900, fontSize: row.font === WORDMARK ? 120 : 150, color: row.color, lineHeight: 1}}>
                  {settled ? row.word : Array.from(row.word).map((ch, j) => (hash(i, j, frame) < 0.5 ? ch : '#')).join('')}
                </span>
              </div>
            );
          })}
        </AbsoluteFill>
      ) : null}
      <CharField cell={24} set="han" fps={15} paint={paint} />
      <Sfx name="glitch" at={WALL_AT} volume={0.35} />
      <Sfx name="swish" at={DRAIN_AT - 20} volume={0.4} />
      <Sfx name="impact" at={TITLE_AT + 8} volume={0.4} />
      {frame >= TITLE_AT ? (
        <div style={{position: 'absolute', inset: 0, opacity: clamp01((frame - TITLE_AT) / 6)}}>
          <NameLockup t={frame - TITLE_AT} />
        </div>
      ) : null}
      <Glyphs count={frame > TITLE_AT ? 16 : 10} seed={11} opacity={0.8} />
    </Fill>
  );
};

/** The opening's scenes and the transitions between them (60 fps; 600 frames all together). */
export const OPENING = {Greeting, Stream, NameWall};
