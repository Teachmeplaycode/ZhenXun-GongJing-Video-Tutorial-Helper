import React, {useMemo} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp01, CONSOLE, DISPLAY, easeOut, Fill, Glyphs, hash, Index, INK, INK2, INK3, LIME, LINE, LINE2, MONO, NIGHT, PIXEL, pop, Rule, SC, Sfx, SILK, stepped,
  textWidth, Typed, WORDMARK} from './kit';
import {Contour} from './Contour';
import {FLOOR_VIEW, floorSlat, project, Sculpture, SHEETS} from './Sculpture';
import {Bars} from './transitions';
import {Glitch} from './Glitch';

// The first ten seconds — cut into the deck on its own — as one continuous shot, ending on the name:
//   0    the site's contour loader builds its terrain, the camera easing in, the reads ticking off
//   128  staggered, glitching bars pull across it and uncover…
//   140  …the sculpture's slats standing on the floor as a timeline, rolling in height; a read runs
//        along them, each slat rising and turning as it is read (the site's timeline hover)
//   262  the last slat read lifts off, turns flat to the camera, comes to the centre and grows until
//        it fills the frame
//   316  帧 / 寻 / GongJ!ng? fly in across it from the left
//   372  the floor of tiles flips over to night, wave by wave; the tiles under 帧寻 flip back in lime
//   470  the tiles shatter and fall away onto the lockup: the sculpture, 帧寻 GongJ!ng?, the slogan

/** Cells covered by `text` drawn big in the middle of a cols×rows grid (true = inside a stroke).
 *  `aspect` is a cell's width over its height (character cells are 0.62; tiles are square). */
export function textMask(text: string, cols: number, rows: number, font: string, scale = 0.8, aspect = 0.62): boolean[][] {
  if (typeof document === 'undefined') return [];
  const canvas = document.createElement('canvas');
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext('2d')!;
  const stretch = 1 / aspect;
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

const CARD = '#F0EDE8'; // a slat's face (--sculpture-light)
const BARS_AT = 128;
const READ_AT = 140;
const SWEEP = [176, 256]; // the read runs along the timeline
const HEAD = [0.2, 0.72];
const LIFT_AT = 262; // the last slat read leaves the row
const FILL_AT = 300; // …and fills the frame
const ROWS_AT = 316;
const FLIP_AT = 372;
const LIME_AT = 426;
const SHATTER_AT = 470;
const LOCK_AT = 470;

// ---------------------------------------------------------------- 0: the contour loader
const READS = [{at: 20, word: '画面'}, {at: 50, word: '原声'}, {at: 80, word: '文字'}];
const Boot: React.FC<{frame: number}> = ({frame}) => {
  const {fps} = useVideoConfig();
  const t = clamp01(frame / 124);
  const progress = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
  const level = Math.min(42, Math.ceil(progress * 42));
  const head = pop(frame, 0, fps, 200);
  return (
    <Fill>
      <Contour progress={progress} yaw={0.6 + frame * 0.0016} scale={0.56 + 0.1 * easeOut(frame / 150)} cy={600} />
      <div style={{position: 'absolute', left: 96, top: 82, display: 'flex', alignItems: 'flex-end', gap: 22, transform: `translateY(${(1 - head) * -40}px)`, opacity: clamp01(head * 2)}}>
        <Index n="00" size={150} />
        <div style={{display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: 8}}>
          <span style={{fontFamily: PIXEL, fontSize: 48, color: INK}}>逐帧读取</span>
          <span style={{fontFamily: CONSOLE, fontSize: 34, color: INK2}}>{'>( 帧 )={<'}</span>
        </div>
      </div>
      <Rule x={96} y={250} w={520} k={easeOut(frame / 30)} />
      <div style={{position: 'absolute', left: 96, top: 282, display: 'flex', flexDirection: 'column', gap: 12, background: 'rgba(245,243,239,0.85)', padding: '6px 10px 6px 0'}}>
        {READS.map((r, i) => {
          const done = frame > r.at + 34;
          return frame >= r.at ? (
            <div key={i} style={{display: 'flex', gap: 16, alignItems: 'center', fontFamily: CONSOLE, fontSize: 40, color: INK}}>
              <span style={{width: 12, height: 12, background: done ? LIME : INK3}} />
              <span style={{fontFamily: PIXEL, fontSize: 48}}>{r.word}</span>
              <span style={{color: INK3}}>{'.'.repeat(Math.min(12, Math.floor((frame - r.at) / 3)))}</span>
              <span style={{color: done ? INK : INK3}}>{done ? 'ok' : `${Math.min(99, (frame - r.at) * 3)}%`}</span>
            </div>
          ) : null;
        })}
      </div>
      <div style={{position: 'absolute', right: 110, top: 300, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, fontFamily: CONSOLE, fontSize: 30}}>
        {Array.from({length: 9}, (_, i) => {
          const n = level - i;
          return n > 0 ? <span key={i} style={{color: i === 0 ? INK : INK3, opacity: 1 - i * 0.1}}>L{String(n).padStart(2, '0')} {i === 0 ? '◆' : '—'}</span> : null;
        })}
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 92, display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: 12}}>
        <span style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 120, color: INK, letterSpacing: -4, fontVariantNumeric: 'tabular-nums', background: 'rgba(245,243,239,0.8)', padding: '0 16px'}}>
          {String(Math.round(progress * 100)).padStart(3, '0')}
        </span>
        <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 40, color: INK2}}>%</span>
      </div>
      <Rule x={660} y={1006} w={600} k={1} color={LINE} thick={4} />
      <Rule x={660} y={1006} w={600} k={progress} color={INK} thick={4} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 140: the floor timeline, read slat by slat
const head = (frame: number) => HEAD[0] + (HEAD[1] - HEAD[0]) * easeOut(clamp01((frame - SWEEP[0]) / (SWEEP[1] - SWEEP[0])) ** 0.9);
const LAST = Math.round((HEAD[1] * SHEETS) / 3) * 3;

const Read: React.FC<{frame: number}> = ({frame}) => {
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const h = frame >= SWEEP[0] ? head(frame) : -1;
  const rise = (u: number) => easeOut((frame - READ_AT - u * 30) / 22);
  return (
    <Fill>
      <Sculpture view={FLOOR_VIEW} phase={0}
        pose={(i, u) => {
          const f = floorSlat(u, time, h);
          if (i % 3 !== 0 || (i === LAST && frame >= LIFT_AT)) return {size: 0}; // every third slat: a deck with air between the cards
          return {to: {...f, sy: f.sy * Math.max(0.02, rise(u))}, mix: 1};
        }} />
      <div style={{position: 'absolute', left: 96, top: 82, display: 'flex', alignItems: 'flex-end', gap: 22}}>
        <Index n="00" size={150} />
        <div style={{display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: 8}}>
          <span style={{fontFamily: PIXEL, fontSize: 48, color: INK}}>逐帧读取</span>
          <span style={{fontFamily: CONSOLE, fontSize: 34, color: INK2}}>帧 {String(Math.max(0, Math.round(h * 3600))).padStart(4, '0')} / 3600</span>
        </div>
      </div>
      <Rule x={96} y={250} w={520} k={1} />
      {/* a reading marker riding above the slat being read */}
      {h >= 0 && frame < LIFT_AT ? (() => {
        const f = floorSlat(h, time, h);
        const p = project({x: f.x, y: f.y + 3.4 * f.sy + 1.5, z: f.z}, FLOOR_VIEW);
        return (
          <div style={{position: 'absolute', left: p.x - 50, top: p.y - 100, width: 100, textAlign: 'center', fontFamily: CONSOLE, fontSize: 40, color: INK}}>
            <div style={{background: LIME, padding: '0 6px'}}>{String(Math.round(h * 3600)).padStart(4, '0')}</div>
            <div style={{width: 2, height: 46, background: INK, margin: '0 auto'}} />
          </div>
        );
      })() : null}
    </Fill>
  );
};

// ---------------------------------------------------------------- 262: the last slat comes up and fills the frame
const FlyCard: React.FC<{frame: number}> = ({frame}) => {
  const {fps} = useVideoConfig();
  const f = floorSlat(HEAD[1], LIFT_AT / fps, HEAD[1]);
  const start = project({x: f.x, y: f.y, z: f.z}, FLOOR_VIEW);
  const w0 = 3.2 * start.unit;
  const h0 = 6.8 * f.sy * start.unit;
  const k = easeOut((frame - LIFT_AT) / (FILL_AT - LIFT_AT));
  const grow = Math.pow(clamp01((frame - FILL_AT + 14) / 22), 2);
  // to the centre, turned flat and landscape, then grown past the edges
  const cx = start.x + (960 - start.x) * k;
  const cy = start.y + (540 - start.y) * k - Math.sin(k * Math.PI) * 120;
  const w = w0 + (h0 * 1.4 - w0) * k;
  const h = h0 + (w0 * 1.4 - h0) * k;
  const scale = 1 + grow * (2300 / Math.max(1, Math.min(w, h)) - 1);
  return (
    <AbsoluteFill style={{perspective: 1400}}>
      <div style={{position: 'absolute', left: cx - w / 2, top: cy - h / 2, width: w, height: h, background: CARD,
        boxShadow: `0 ${30 * (1 - grow)}px ${60 * (1 - grow)}px rgba(26,26,26,${0.18 * (1 - grow)}), inset 0 0 0 ${2 * (1 - grow)}px ${LINE2}`,
        transform: `rotateY(${-48 * (1 - k)}deg) rotateZ(${90 * k}deg) scale(${scale})`, transformOrigin: '50% 50%'}}>
        <span style={{position: 'absolute', left: 10, top: 6, fontFamily: CONSOLE, fontSize: 18, color: INK3, opacity: 1 - grow}}>{String(((LAST * 3600) / SHEETS) | 0).padStart(4, '0')}</span>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 316: the name flies in over the card
const ROWS = [
  {lead: '////////////', word: '帧', font: SC, size: 150},
  {lead: '>>>>>>>>>>>>', word: '寻', font: SC, size: 150},
  {lead: '[[[[[[[[[[[[', word: 'GongJ!ng?', font: WORDMARK, size: 120},
];
const Rows: React.FC<{frame: number}> = ({frame}) => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 150, gap: 26}}>
      {ROWS.map((row, i) => {
        const start = ROWS_AT + i * 8;
        const k = pop(frame, start, fps, 230);
        const out = Math.pow(clamp01((frame - FLIP_AT + 6 - i * 4) / 20), 2);
        const steps = stepped(frame - start, 60, 20);
        const settled = frame - start > 10;
        return (
          <div key={i} style={{display: 'flex', alignItems: 'center', gap: 34, opacity: frame >= start ? 1 : 0,
            transform: `translateX(${(1 - k) * -1500 + out * 2200}px) skewX(${(1 - k) * -18 + out * -18}deg)`}}>
            <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 108, color: LINE2, letterSpacing: -4}}>{row.lead.slice(0, Math.max(0, Math.min(12, steps * 3)))}</span>
            <span style={{fontFamily: row.font, fontWeight: 900, fontSize: row.size, color: INK, lineHeight: 1, ...(i === 0 ? {color: LIME, textShadow: `6px 6px 0 ${INK}`} : {})}}>
              {settled ? row.word : Array.from(row.word).map((ch, j) => (hash(i, j, frame) < 0.5 ? ch : '#')).join('')}
            </span>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- 372: the tile floor flips to night, 帧寻 back in lime, then shatters
const TILE = 60;
const TCOLS = 1920 / TILE;
const TROWS = 1080 / TILE;
const Tiles: React.FC<{frame: number}> = ({frame}) => {
  const mask = useMemo(() => textMask('帧寻', TCOLS, TROWS, SC, 0.8, 1), []);
  const tiles: React.ReactNode[] = [];
  for (let r = 0; r < TROWS; r += 1) {
    for (let c = 0; c < TCOLS; c += 1) {
      const inName = mask[r]?.[c];
      const delay = ((c + r * 0.6) / (TCOLS + TROWS * 0.6)) * 34 + hash(c, r) * 6;
      const a1 = easeOut((frame - FLIP_AT - delay) / 12) * 180; // paper → night
      const back = inName ? easeOut((frame - LIME_AT - hash(c, r, 2) * 14 - Math.abs(c - TCOLS / 2) * 0.6) / 12) * 180 : 0; // night → lime
      const angle = a1 + back;
      // the shatter: from the centre out, each tile kicked toward the camera and falling
      const dx = c + 0.5 - TCOLS / 2;
      const dy = r + 0.5 - TROWS / 2;
      const s = Math.max(0, (frame - SHATTER_AT - Math.hypot(dx, dy) * 0.9 - hash(c, r, 3) * 5) / 60);
      if (s > 1.2) continue;
      const vx = dx * 26 + (hash(c, r, 4) - 0.5) * 300;
      const vy = dy * 18 - 260 - hash(c, r, 5) * 200;
      const tx = vx * s;
      const ty = vy * s + 1400 * s * s;
      const tz = 900 * s;
      const spin = (hash(c, r, 6) - 0.5) * 720 * s;
      const front = angle > 270 ? LIME : CARD; // the face seen at 0° (paper) and again at 360° (lime)
      tiles.push(
        <div key={`${r}-${c}`} style={{position: 'absolute', left: c * TILE, top: r * TILE, width: TILE + 0.6, height: TILE + 0.6, transformStyle: 'preserve-3d',
          transform: `translate3d(${tx}px, ${ty}px, ${tz}px) rotateX(${spin}deg) rotateY(${angle}deg) rotateZ(${spin * 0.5}deg)`, opacity: s > 0 ? 1 - clamp01((s - 0.7) / 0.5) : 1}}>
          <div style={{position: 'absolute', inset: 0, background: front, backfaceVisibility: 'hidden', boxShadow: angle > 270 ? 'inset 0 0 0 1px #B5DB3C' : `inset 0 0 0 0.5px ${LINE}`}} />
          <div style={{position: 'absolute', inset: 0, background: NIGHT, backfaceVisibility: 'hidden', transform: 'rotateY(180deg)', boxShadow: 'inset 0 0 0 0.5px #222624'}} />
        </div>,
      );
    }
  }
  return <AbsoluteFill style={{perspective: 1800, perspectiveOrigin: '50% 45%'}}>{tiles}</AbsoluteFill>;
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

/** 帧寻 GongJ!ng?, the rule and the slogan. 帧 in lime, lifted off the paper by an ink shadow. */
export const NameLockup: React.FC<{t: number; exit?: number}> = ({t, exit = 0}) => {
  const {fps} = useVideoConfig();
  const ZX = zxCenter();
  const settle = pop(t, 0, fps, 140);
  const g = easeOut((t - 10) / 16);
  const rule = easeOut((t - 14) / 18);
  const steps = stepped(t, 60, 12);
  const up = easeOut(exit);
  return (
    <>
      <div style={{position: 'absolute', left: 0, right: 0, top: TITLE_Y - TITLE_SIZE / 2, height: TITLE_SIZE,
        transform: `translateY(${-up * 120}px)`, clipPath: exit > 0 ? `inset(-400px 0 ${up * 100}% 0)` : undefined}}>
        <span style={{position: 'absolute', left: ZX.x - TITLE_SIZE, width: TITLE_SIZE * 2, textAlign: 'center', fontFamily: SC, fontWeight: 900, fontSize: TITLE_SIZE,
          color: INK, lineHeight: `${TITLE_SIZE}px`, whiteSpace: 'nowrap', transform: `translateY(${(1 - settle) * 140}px) scale(${0.8 + 0.2 * settle})`, opacity: clamp01(settle * 2)}}>
          <span style={{color: LIME, textShadow: `7px 7px 0 ${INK}`}}>帧</span>寻
        </span>
        <span style={{position: 'absolute', left: ZX.x + TITLE_SIZE + 54, top: (TITLE_SIZE - 136) / 2 + 10, fontFamily: WORDMARK, fontWeight: 700, fontSize: 136, color: INK,
          letterSpacing: -6, lineHeight: 1, whiteSpace: 'nowrap', clipPath: `inset(${(1 - g) * 100}% 0 0 0)`, transform: `translateY(${(1 - g) * 40}px)`}}>
          GongJ<span style={{color: '#9CC229'}}>!</span>ng<span style={{color: '#9CC229'}}>{steps % 10 < 7 ? '?' : '!'}</span>
        </span>
      </div>
      {exit > 0 ? null : <div style={{position: 'absolute', left: RULE.left, top: RULE.y - 4, width: RULE.width, height: 8, background: LIME, transform: `scaleX(${rule})`, transformOrigin: '0 50%'}} />}
      <div style={{position: 'absolute', left: 0, right: 0, top: RULE.y + 36, display: 'flex', justifyContent: 'center', alignItems: 'center', fontFamily: SILK, fontWeight: 700, fontSize: 52, gap: 26,
        transform: `translateY(${-up * 60}px)`, opacity: 1 - up}}>
        <span style={{color: INK3, opacity: t > 22 ? 1 : 0}}>*//</span>
        <Typed text="看见，再求证。" at={26} cps={22} style={{fontFamily: PIXEL, fontSize: 60, color: INK}} sound={exit === 0} />
        <span style={{color: INK3, opacity: t > 22 ? 1 : 0}}>{'>>'}</span>
      </div>
    </>
  );
};

const Lockup: React.FC<{frame: number}> = ({frame}) => {
  const t = frame - LOCK_AT;
  return (
    <Fill>
      {/* the sculpture is simply there, whole, rising a little into place (no scatter: it shouldn't glitter) */}
      {/* one burst of the homepage's model glitch, once it has settled */}
      <Glitch frame={t} starts={[62]} id="lock">
        <Sculpture phase={1} scale={1.05} y={-0.5 - 1.2 * (1 - easeOut((t + 6) / 40))} style={{opacity: clamp01((t + 6) / 24)}} />
      </Glitch>
      <NameLockup t={t - 8} />
      <Glyphs count={12} seed={11} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- the whole opening, one shot
const Opening: React.FC = () => {
  const frame = useCurrentFrame();
  const bars = clamp01((frame - BARS_AT) / 40);
  return (
    <AbsoluteFill>
      {frame >= SHATTER_AT - 2 ? <Lockup frame={frame} /> : null}
      {frame < SHATTER_AT + 80 ? (
        <AbsoluteFill>
          {frame < FILL_AT + 20 ? (
            frame < BARS_AT ? <Boot frame={frame} /> : (
              <Bars p={bars} tint={LIME} seed={4} old={bars < 1 ? <Boot frame={frame} /> : undefined}>
                <Read frame={frame} />
              </Bars>
            )
          ) : frame < FLIP_AT + 60 ? <AbsoluteFill style={{background: CARD}} /> : null}
          {frame >= LIFT_AT && frame < FLIP_AT + 60 ? <FlyCard frame={frame} /> : null}
          {frame >= ROWS_AT && frame < FLIP_AT + 40 ? <Rows frame={frame} /> : null}
          {frame >= FLIP_AT ? <Tiles frame={frame} /> : null}
        </AbsoluteFill>
      ) : null}
      {/* sound */}
      {Array.from({length: 12}, (_, i) => <Sfx key={`b${i}`} name="soft" at={6 + i * 10} volume={0.16} rate={0.9 + i * 0.03} />)}
      {READS.map((r, i) => <Sfx key={`r${i}`} name="key" at={r.at} volume={0.3} />)}
      <Sfx name="glitch" at={BARS_AT} volume={0.35} />
      <Sfx name="whoosh" at={BARS_AT + 2} volume={0.45} />
      {Array.from({length: 16}, (_, i) => <Sfx key={`h${i}`} name="soft" at={SWEEP[0] + i * 5} volume={0.22} rate={1 + i * 0.02} />)}
      <Sfx name="swish" at={LIFT_AT} volume={0.4} />
      <Sfx name="whoosh" at={ROWS_AT} volume={0.35} rate={1.2} />
      <Sfx name="whoosh" at={ROWS_AT + 8} volume={0.3} rate={1.3} />
      <Sfx name="whoosh" at={ROWS_AT + 16} volume={0.3} rate={1.4} />
      {Array.from({length: 10}, (_, i) => <Sfx key={`f${i}`} name="click" at={FLIP_AT + i * 4} volume={0.18} rate={0.9 + i * 0.04} />)}
      <Sfx name="pop" at={LIME_AT} volume={0.45} />
      <Sfx name="sparkle" at={LIME_AT + 4} volume={0.25} />
      <Sfx name="hit" at={SHATTER_AT} volume={0.4} />
      <Sfx name="impact" at={SHATTER_AT + 4} volume={0.5} />
      <Glyphs count={8} seed={3} opacity={frame < SHATTER_AT ? 0.5 : 0} />
    </AbsoluteFill>
  );
};

export const OPENING = {Opening};
