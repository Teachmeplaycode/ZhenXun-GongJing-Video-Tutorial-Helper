import React, {useCallback, useMemo} from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {BG, BLUE, CharField, clamp01, DIM, easeOut, Fill, Glyphs, hash, LIME, MONO, PixelCursor, SC, stepped, Typed, WHITE, WORDMARK} from './kit';

// The first ten seconds — cut into the deck on its own — ending on the name:
//   0.0–2.5  a code greeting:  >( 帧 )=  →  >( 帧, 画面 )={<  … 原声 / 文字 / 证据, a pixel cursor below
//   2.5–5.0  a character field, a big 帧 in blue blocks, a frame counter and a timecode running
//   5.0–7.5  rows slide in and snap: 帧 / 寻 / GongJ!ng?, then 帧寻 cut out of a lime character wall
//   7.5–10   the name: 帧寻 GongJ!ng?, 看见，再求证。

/** Cells covered by `text` drawn big in the middle of a cols×rows grid (true = inside a stroke). */
export function textMask(text: string, cols: number, rows: number, font: string, scale = 0.8): boolean[][] {
  if (typeof document === 'undefined') return [];
  const canvas = document.createElement('canvas');
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#fff';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = `900 ${Math.floor(rows * scale)}px ${font}`;
  const fit = Math.min(1, (cols * 0.92) / ctx.measureText(text).width);
  ctx.font = `900 ${Math.floor(rows * scale * fit)}px ${font}`;
  ctx.fillText(text, cols / 2, rows / 2 + rows * 0.03);
  const data = ctx.getImageData(0, 0, cols, rows).data;
  return Array.from({length: rows}, (_, r) => Array.from({length: cols}, (_, c) => data[(r * cols + c) * 4 + 3] > 110));
}

const WORDS = ['', '画面', '原声', '文字', '证据'];

const Greeting: React.FC = () => {
  const frame = useCurrentFrame();
  const word = WORDS[Math.min(WORDS.length - 1, Math.floor(Math.max(0, frame - 28) / 24) + (frame >= 28 ? 1 : 0))];
  const since = frame < 28 ? frame : (frame - 28) % 24;
  // Each new word arrives scrambled for a few frames, then settles.
  const scramble = since < 6 && word ? Array.from(word).map((_, i) => '帧寻画面原声文字证据回看'[Math.floor(hash(i, frame) * 12)]).join('') : word;
  const shown = word ? `, ${scramble}` : '';
  const tail = word ? ' )={<' : ' )=';
  const width = (word ? 2 + word.length * 1.0 : 0) * 120 + 520;
  const cursorX = 960 - 300 + width * 0.62 + Math.sin(frame / 9) * 6;
  const bars = useCallback((c: number, r: number, tick: number, cols: number, rows: number) => {
    // The reference's ragged code bars: a band in the lower third, runs of blue and lime.
    if (r < rows * 0.62 || r > rows * 0.82) return null;
    const run = Math.floor((c + tick * (r % 2 ? 2 : -1)) / 7);
    const on = hash(run, r) < 0.55;
    if (!on) return hash(c, r, tick) < 0.06 ? DIM : null;
    return hash(run, r, 3) < 0.45 ? BLUE : hash(run, r, 4) < 0.5 ? LIME : WHITE;
  }, []);
  return (
    <Fill>
      <CharField cell={20} set="code" fps={15} paint={bars} style={{opacity: 0.9}} />
      <div style={{position: 'absolute', left: 92, top: 70, fontFamily: MONO, fontWeight: 700, fontSize: 24, color: BG, background: LIME, padding: '2px 10px'}}>// ---[ + ]</div>
      <div style={{position: 'absolute', right: 96, bottom: 74, fontFamily: MONO, fontSize: 24, color: '#8B9171'}}>const 帧寻 = {'{'}</div>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingBottom: 260}}>
        <div style={{fontFamily: MONO, fontWeight: 800, fontSize: 132, color: BLUE, whiteSpace: 'nowrap', letterSpacing: -2}}>
          {'>('}
          <span style={{fontFamily: SC, fontWeight: 900, color: LIME}}> 帧{shown}</span>
          {tail}
        </div>
      </AbsoluteFill>
      <PixelCursor x={cursorX} y={430 + Math.cos(frame / 11) * 5} size={6} />
      <Glyphs count={10} seed={2} opacity={0.75} />
    </Fill>
  );
};

const Stream: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cols = Math.ceil(1920 / (22 * 0.62));
  const rows = Math.ceil(1080 / 22);
  const mask = useMemo(() => textMask('帧', cols, rows, SC, 0.86), [cols, rows]);
  const grow = easeOut(frame / 40); // the glyph fills in
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
  return (
    <Fill>
      <CharField cell={22} set="code" fps={20} paint={paint} />
      <div style={{position: 'absolute', right: 120, top: 92, fontFamily: MONO, fontWeight: 800, fontSize: 40, color: WHITE, background: BG, padding: '4px 14px'}}>
        t = "<span style={{color: LIME}}>{tc}</span>"
      </div>
      <div style={{position: 'absolute', left: 120, bottom: 96, fontFamily: MONO, fontWeight: 800, fontSize: 40, color: WHITE, background: BG, padding: '4px 14px'}}>
        帧 = <span style={{color: BLUE}}>{n}</span> / 3600
      </div>
      <Glyphs count={8} seed={5} opacity={0.8} />
    </Fill>
  );
};

const ROWS = [
  {lead: '////////////', word: '帧', color: BLUE, font: SC},
  {lead: '>>>>>>>>>>>>', word: '寻', color: LIME, font: SC},
  {lead: '[[[[[[[[[[[[', word: 'GongJ!ng?', color: WHITE, font: WORDMARK},
];

const Assemble: React.FC = () => {
  const frame = useCurrentFrame();
  const cols = Math.ceil(1920 / (24 * 0.62));
  const rows = Math.ceil(1080 / 24);
  const mask = useMemo(() => textMask('帧寻', cols, rows, SC, 0.62), [cols, rows]);
  const wall = frame >= 92;
  const reveal = easeOut((frame - 100) / 26);
  const paint = useCallback((c: number, r: number, tick: number) => {
    if (mask[r]?.[c]) return hash(c, r, 9) < reveal ? null : LIME; // the name cut out of the wall
    return hash(c, r, tick) < 0.92 ? LIME : '#7E8C3C';
  }, [mask, reveal]);
  if (wall) {
    return (
      <Fill>
        <CharField cell={24} set="han" fps={15} paint={paint} />
        <Glyphs count={8} seed={8} opacity={0.6} />
      </Fill>
    );
  }
  return (
    <Fill>
      <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 150, gap: 26}}>
        {ROWS.map((row, i) => {
          const start = 6 + i * 12;
          const k = clamp01((frame - start) / 14);
          const steps = stepped(frame - start, 60, 15);
          const leadShown = row.lead.slice(0, Math.max(0, Math.min(row.lead.length, steps * 3)));
          const x = (1 - easeOut(k)) * (i % 2 ? 340 : -340); // rows come from alternate sides
          const settled = frame - start > 16;
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 34, transform: `translateX(${x}px)`, opacity: k > 0 ? 1 : 0}}>
              <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 108, color: row.color, letterSpacing: -4}}>{leadShown}</span>
              <span style={{fontFamily: row.font, fontWeight: 900, fontSize: row.font === WORDMARK ? 120 : 150, color: row.color, lineHeight: 1,
                transform: settled ? 'none' : `translate(${(hash(i, frame) - 0.5) * 30}px, ${(hash(i, frame, 1) - 0.5) * 18}px)`}}>
                {settled ? row.word : Array.from(row.word).map((ch, j) => (hash(i, j, frame) < 0.5 ? ch : '#')).join('')}
              </span>
            </div>
          );
        })}
      </AbsoluteFill>
      <Glyphs count={10} seed={11} opacity={0.8} />
    </Fill>
  );
};

const Name: React.FC = () => {
  const frame = useCurrentFrame();
  const a = easeOut(frame / 18);
  const b = easeOut((frame - 10) / 20);
  const steps = stepped(frame, 60, 12);
  const dots = useCallback((c: number, r: number, tick: number) => (hash(c, r) < 0.035 ? (hash(c, r, tick) < 0.5 ? '#2A2E20' : '#22283F') : null), []);
  return (
    <Fill>
      <CharField cell={26} set="marks" fps={8} paint={dots} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 30, paddingBottom: 40}}>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 54}}>
          <span style={{fontFamily: SC, fontWeight: 900, fontSize: 290, color: WHITE, lineHeight: 1,
            clipPath: `inset(0 ${(1 - a) * 100}% 0 0)`, transform: `translateY(${(1 - a) * 40}px)`}}>帧寻</span>
          <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 150, color: WHITE, letterSpacing: -6, lineHeight: 1,
            clipPath: `inset(${(1 - b) * 100}% 0 0 0)`}}>
            GongJ<span style={{color: LIME}}>!</span>ng<span style={{color: LIME}}>{steps % 10 < 7 ? '?' : '!'}</span>
          </span>
        </div>
        <div style={{width: 1120, height: 6, background: LIME, transform: `scaleX(${easeOut((frame - 18) / 20)})`, transformOrigin: '0 50%'}} />
        <div style={{fontFamily: MONO, fontWeight: 800, fontSize: 52, color: LIME, display: 'flex', gap: 26, alignItems: 'center'}}>
          <span style={{color: BLUE}}>*//</span>
          <Typed text="看见，再求证。" at={30} cps={14} style={{fontFamily: SC, fontWeight: 900, color: WHITE}} />
          <span style={{color: BLUE}}>{'>>'}</span>
        </div>
      </AbsoluteFill>
      <Glyphs count={16} seed={13} opacity={0.85} />
    </Fill>
  );
};

export const Opening: React.FC = () => (
  <AbsoluteFill style={{background: BG}}>
    <Sequence durationInFrames={150}><Greeting /></Sequence>
    <Sequence from={150} durationInFrames={150}><Stream /></Sequence>
    <Sequence from={300} durationInFrames={150}><Assemble /></Sequence>
    <Sequence from={450} durationInFrames={150}><Name /></Sequence>
  </AbsoluteFill>
);
