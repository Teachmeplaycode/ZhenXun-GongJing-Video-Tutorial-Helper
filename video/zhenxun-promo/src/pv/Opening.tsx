import React, {useCallback, useMemo} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {CharField, clamp01, CONSOLE, DISPLAY, easeOut, Fill, Glyphs, hash, Index, INK, INK2, INK3, LIME, LIME_DIM, LINE, LINE2, MONO, PAPER, PIXEL, pop, Rule,
  SC, Sfx, SILK, stepped, textWidth, Typed, WORDMARK} from './kit';
import {Contour} from './Contour';
import {Sculpture} from './Sculpture';

// The first ten seconds — cut into the deck on its own — ending on the name, in the site's day
// theme:
//   Boot       the site's contour loader builds its terrain, level by level, while the reads tick
//              off (画面 / 原声 / 文字) and a counter runs to 100
//   Stream     a field of characters; a big 帧 made of them; a timecode and a frame count running
//   NameWall   帧 / 寻 / GongJ!ng? slide in; an ink wall of characters types over them with 帧寻
//              cut out; the wall drains away and the cut-out becomes the title, which settles into
//              the lockup while the homepage's sculpture gathers behind it

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

// ---------------------------------------------------------------- Boot: the contour loader
/** The point the next scene zooms out of: the terrain's summit. */
export const BOOT_SUMMIT = {x: 900, y: 470};
const READS = [{at: 24, word: '画面'}, {at: 60, word: '原声'}, {at: 96, word: '文字'}];

const Boot: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = clamp01(frame / 150);
  const progress = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2; // the site's power1.inOut
  const pct = Math.round(progress * 100);
  const level = Math.min(42, Math.ceil(progress * 42));
  const head = pop(frame, 0, fps, 200);
  return (
    <Fill>
      <Sfx name="glitch" volume={0.2} />
      {Array.from({length: 14}, (_, i) => <Sfx key={i} name="soft" at={8 + i * 10} volume={0.18} rate={0.9 + i * 0.03} />)}
      <Contour progress={progress} yaw={0.6 + frame * 0.0012} scale={0.4} cy={590} />
      {/* top left: the section marker */}
      <div style={{position: 'absolute', left: 96, top: 82, display: 'flex', alignItems: 'flex-end', gap: 22, transform: `translateY(${(1 - head) * -40}px)`, opacity: clamp01(head * 2)}}>
        <Index n="00" size={150} />
        <div style={{display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: 8}}>
          <span style={{fontFamily: PIXEL, fontSize: 48, color: INK}}>逐帧读取</span>
          <span style={{fontFamily: CONSOLE, fontSize: 34, color: INK2}}>{'>( 帧 )={<'}</span>
        </div>
      </div>
      <Rule x={96} y={250} w={520} k={easeOut(frame / 30)} />
      {/* the reads, ticking off */}
      <div style={{position: 'absolute', left: 96, top: 282, display: 'flex', flexDirection: 'column', gap: 12}}>
        {READS.map((r, i) => {
          const done = frame > r.at + 40;
          return frame >= r.at ? (
            <div key={i} style={{display: 'flex', gap: 16, alignItems: 'center', fontFamily: CONSOLE, fontSize: 40, color: INK}}>
              <span style={{width: 12, height: 12, background: done ? LIME_DIM : INK3}} />
              <span style={{fontFamily: PIXEL, fontSize: 48}}>{r.word}</span>
              <span style={{color: INK3}}>{'.'.repeat(Math.min(12, Math.floor((frame - r.at) / 3)))}</span>
              <span style={{color: done ? INK : INK3}}>{done ? 'ok' : `${Math.min(99, (frame - r.at) * 3)}%`}</span>
              <Sfx name="key" volume={0.3} />
            </div>
          ) : null;
        })}
      </div>
      {/* right: the terrace count */}
      <div style={{position: 'absolute', right: 110, top: 300, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, fontFamily: CONSOLE, fontSize: 30}}>
        {Array.from({length: 9}, (_, i) => {
          const n = level - i;
          return n > 0 ? <span key={i} style={{color: i === 0 ? INK : INK3, opacity: 1 - i * 0.1}}>L{String(n).padStart(2, '0')} {i === 0 ? '◆' : '—'}</span> : null;
        })}
      </div>
      {/* bottom: the counter */}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 92, display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: 12}}>
        <span style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 120, color: INK, letterSpacing: -4, fontVariantNumeric: 'tabular-nums'}}>{String(pct).padStart(3, '0')}</span>
        <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 40, color: INK2}}>%</span>
      </div>
      <Rule x={660} y={1006} w={600} k={1} color={LINE} thick={4} />
      <Rule x={660} y={1006} w={600} k={progress} color={INK} thick={4} />
      <Glyphs count={8} seed={2} opacity={0.6} />
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
  const grow = easeOut(frame / 26);
  const paint = useCallback((c: number, r: number, tick: number) => {
    if (mask[r]?.[c]) return hash(c, r, 7) < grow ? (hash(c, r, tick) < 0.93 ? INK : LIME_DIM) : null;
    const lane = r % 3 === 0;
    const moving = (c + tick * (lane ? 3 : 1)) % 47 < (lane ? 22 : 6);
    if (!moving) return hash(c, r, tick) < 0.03 ? LINE : null;
    const near = mask[r]?.[c - 3] || mask[r]?.[c + 3] || mask[r - 1]?.[c] || mask[r + 1]?.[c];
    if (near) return null;
    return hash(c, r) < 0.6 ? LINE2 : hash(c, r, 1) < 0.5 ? INK3 : LIME_DIM;
  }, [mask, grow]);
  const t = (frame / fps) * 7.5;
  const tc = `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`;
  const n = String(Math.min(3600, Math.floor(frame * 24))).padStart(4, '0');
  const a = pop(frame, 10, fps);
  const b = pop(frame, 18, fps);
  return (
    <Fill>
      <CharField cell={22} set="code" fps={20} paint={paint} />
      <div style={{position: 'absolute', right: 120, top: 92, fontFamily: CONSOLE, fontSize: 64, color: INK, background: PAPER, padding: '0 16px', transform: `translateY(${(1 - a) * -80}px)`}}>
        t = "<span style={{borderBottom: `5px solid ${LIME}`}}>{tc}</span>"
      </div>
      <div style={{position: 'absolute', left: 120, bottom: 96, fontFamily: CONSOLE, fontSize: 64, color: INK, background: PAPER, padding: '0 16px', transform: `translateY(${(1 - b) * 80}px)`}}>
        帧 = <span style={{borderBottom: `5px solid ${LIME}`}}>{n}</span> / 3600
      </div>
      <Glyphs count={8} seed={5} opacity={0.7} />
    </Fill>
  );
};

// ---------------------------------------------------------------- the lockup (shared with the next scene)
/** Where the lockup's lime rule sits; the next scene starts from it. */
export const RULE = {y: 650, left: 400, width: 1120};
const TITLE_Y = 470;
const TITLE_SIZE = 260;
const zxCenter = () => {
  const mark = textWidth('GongJ!ng?', `700 136px ${WORDMARK}`, -6);
  return {x: 960 - (TITLE_SIZE * 2 + 54 + mark) / 2 + TITLE_SIZE, y: TITLE_Y};
};

export const NameLockup: React.FC<{t: number; exit?: number}> = ({t, exit = 0}) => {
  const {fps} = useVideoConfig();
  const ZX_CENTER = zxCenter();
  const settle = pop(t, 0, fps, 120);
  const big = 648 / TITLE_SIZE;
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
          color: INK, lineHeight: `${TITLE_SIZE}px`, transform: zx, transformOrigin: '50% 50%', whiteSpace: 'nowrap'}}>帧寻</span>
        <span style={{position: 'absolute', left: ZX_CENTER.x + TITLE_SIZE + 54, top: (TITLE_SIZE - 136) / 2 + 10, fontFamily: WORDMARK, fontWeight: 700, fontSize: 136, color: INK,
          letterSpacing: -6, lineHeight: 1, whiteSpace: 'nowrap', clipPath: `inset(${(1 - g) * 100}% 0 0 0)`, transform: `translateY(${(1 - g) * 40}px)`}}>
          GongJ<span style={{color: LIME_DIM}}>!</span>ng<span style={{color: LIME_DIM}}>{steps % 10 < 7 ? '?' : '!'}</span>
        </span>
      </div>
      {exit > 0 ? null : <div style={{position: 'absolute', left: RULE.left, top: RULE.y - 4, width: RULE.width, height: 8, background: LIME, transform: `scaleX(${rule})`, transformOrigin: '0 50%'}} />}
      <div style={{position: 'absolute', left: 0, right: 0, top: RULE.y + 36, display: 'flex', justifyContent: 'center', alignItems: 'center', fontFamily: SILK, fontWeight: 700, fontSize: 52, gap: 26,
        transform: `translateY(${-up * 60}px)`, opacity: 1 - up}}>
        <span style={{color: INK3, opacity: t > 26 ? 1 : 0}}>*//</span>
        <Typed text="看见，再求证。" at={30} cps={22} style={{fontFamily: PIXEL, fontSize: 60, color: INK}} sound={exit === 0} />
        <span style={{color: INK3, opacity: t > 26 ? 1 : 0}}>{'>>'}</span>
      </div>
    </>
  );
};

// ---------------------------------------------------------------- NameWall
const ROWS = [
  {lead: '////////////', word: '帧', color: INK, font: SC},
  {lead: '>>>>>>>>>>>>', word: '寻', color: LIME_DIM, font: SC},
  {lead: '[[[[[[[[[[[[', word: 'GongJ!ng?', color: INK, font: WORDMARK},
];
const WALL_AT = 86;
const HOLE_AT = 116;
const FILL_AT = 134;
const DRAIN_AT = 168;
const TITLE_AT = 185; // the title lands on bar 4

const NameWall: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cols = Math.ceil(1920 / (24 * 0.62));
  const rows = Math.ceil(1080 / 24);
  const mask = useMemo(() => textMask('帧寻', cols, rows, SC, 0.6), [cols, rows]);
  const paint = useCallback((c: number, r: number, tick: number) => {
    const typed = (frame - WALL_AT - r * 0.6) * 9;
    if (c > typed) return null;
    const drop = frame < DRAIN_AT ? 0 : Math.pow(Math.max(0, frame - DRAIN_AT - hash(c, 4) * 14) / 6, 2);
    const src = Math.floor(r - drop);
    if (src < 0) return null;
    if (mask[r]?.[c]) {
      if (frame < HOLE_AT || hash(c, r, 9) > easeOut((frame - HOLE_AT) / 12)) return frame < HOLE_AT ? INK : null;
      if (frame >= TITLE_AT + 4) return null;
      return hash(c, r, 11) < easeOut((frame - FILL_AT) / 14) ? LIME_DIM : null;
    }
    if (mask[src]?.[c]) return null;
    return hash(c, src, tick) < 0.9 ? INK : INK2;
  }, [mask, frame]);
  return (
    <Fill>
      {frame < WALL_AT + 46 ? (
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
                <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 108, color: LINE2, letterSpacing: -4}}>{leadShown}</span>
                <span style={{fontFamily: row.font, fontWeight: 900, fontSize: row.font === WORDMARK ? 120 : 150, color: row.color, lineHeight: 1}}>
                  {settled ? row.word : Array.from(row.word).map((ch, j) => (hash(i, j, frame) < 0.5 ? ch : '#')).join('')}
                </span>
              </div>
            );
          })}
        </AbsoluteFill>
      ) : null}
      {frame >= TITLE_AT - 20 ? <Sculpture phase={1} scale={1.05} y={-0.5} pose={() => ({spread: 1 - easeOut((frame - TITLE_AT + 20) / 70)})} /> : null}
      <CharField cell={24} set="han" fps={15} paint={paint} />
      <Sfx name="glitch" at={WALL_AT} volume={0.3} />
      <Sfx name="swish" at={DRAIN_AT - 20} volume={0.4} />
      <Sfx name="impact" at={TITLE_AT + 8} volume={0.55} />
      {frame >= TITLE_AT ? (
        <div style={{position: 'absolute', inset: 0, opacity: clamp01((frame - TITLE_AT) / 6)}}>
          <NameLockup t={frame - TITLE_AT} />
        </div>
      ) : null}
      <Glyphs count={frame > TITLE_AT ? 14 : 8} seed={11} opacity={0.7} />
    </Fill>
  );
};

export const OPENING = {Boot, Stream, NameWall};
