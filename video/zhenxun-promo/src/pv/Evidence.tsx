import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {clamp01, CONSOLE, easeOut, Fill, Glyphs, hash, Head, INK, INK2, INK3, LIME, LINE, LINE2, PIXEL, pop, SC, Sfx, SILK, SURFACE, Typed} from './kit';
import {Topo} from './Contour';
import {Crawler, NameLockup, RULE, snakeX, SNAKE_AT} from './Opening';
import {Sculpture} from './Sculpture';

// 01 三路证据 — what one frame gives up, each shown as a small working model rather than a word:
//   画面      a frame whose picture is painted in pixel by pixel as a scan runs down it, then a
//             detection box snaps onto what matters in it
//   原声      a cassette in 2.5D, its reels turning, a sound wave coming off it and turning into words
//   画面文字   a frame lying flat on the floor; the words printed on it lift off, one by one, and line
//             up in the air above it
// It opens from the name: the title leaves upward, the lockup's lime rule drops and splits into
// three floors, one under each model, and the snake crawls on out of the frame.

const COLS = [340, 960, 1580]; // column centres
const BOX = {w: 440, h: 300, top: 330};
const FLOOR = 760;
const marker = (k = 1): React.CSSProperties => ({backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundRepeat: 'no-repeat',
  backgroundSize: `${clamp01(k) * 100}% 38%`, backgroundPosition: '0 88%'});

// ---------------------------------------------------------------- 画面: a pixel picture, scanned
const PW = 24;
const PH = 15;
const PX = 17;
const pixel = (x: number, y: number) => {
  if ((x - 18) ** 2 + (y - 3.5) ** 2 < 6.5) return LIME; // the sun
  if (y >= 12) return LINE2; // the ground
  if (y > 12 - (5 - Math.abs(x - 7)) * 1.3) return INK; // the near peak
  if (y > 12 - (4 - Math.abs(x - 14) * 0.7) * 1.4) return INK3; // the far one
  if (y === 2 && x > 3 && x < 8 && x !== 6) return LINE; // a cloud
  return null;
};
const Picture: React.FC<{t: number}> = ({t}) => {
  const scan = clamp01(t / 46) * PH;
  const box = easeOut((t - 54) / 12);
  const cells: React.ReactNode[] = [];
  for (let y = 0; y < PH; y += 1) {
    for (let x = 0; x < PW; x += 1) {
      const c = pixel(x, y);
      if (!c || y > scan - (x / PW) * 0.6) continue;
      cells.push(<rect key={`${x}-${y}`} x={x * PX} y={y * PX} width={PX - 1} height={PX - 1} fill={c} />);
    }
  }
  const W = PW * PX;
  const H = PH * PX;
  // the detection box: from the whole picture onto the near peak and the sun
  const bx = 0 + (40 - 0) * box;
  const by = 0 + (20 - 0) * box;
  const bw = W + (W - 60 - W) * box;
  const bh = H + (H - 40 - H) * box;
  return (
    <svg width={W + 20} height={H + 20} viewBox={`-10 -10 ${W + 20} ${H + 20}`} style={{overflow: 'visible'}}>
      <rect x={-6} y={-6} width={W + 12} height={H + 12} rx={8} fill={SURFACE} stroke={LINE2} strokeWidth={2} />
      {cells}
      {t < 50 ? <rect x={-6} y={scan * PX - 2} width={W + 12} height={3} fill={INK} /> : null}
      {t > 54 ? (
        <g stroke={INK} strokeWidth={4} fill="none">
          <path d={`M${bx} ${by + 22}V${by}H${bx + 22}M${bx + bw - 22} ${by}H${bx + bw}V${by + 22}M${bx + bw} ${by + bh - 22}V${by + bh}H${bx + bw - 22}M${bx + 22} ${by + bh}H${bx}V${by + bh - 22}`} />
        </g>
      ) : null}
    </svg>
  );
};

// ---------------------------------------------------------------- 原声: a cassette in 2.5D, and a wave off it
const Reel: React.FC<{cx: number; cy: number; turn: number; r?: number}> = ({cx, cy, turn, r = 34}) => (
  <g transform={`translate(${cx} ${cy}) rotate(${turn})`}>
    <circle r={r} fill={SURFACE} stroke={INK} strokeWidth={4} />
    <circle r={r * 0.36} fill={INK} />
    {[0, 60, 120, 180, 240, 300].map((a) => <rect key={a} x={-3} y={-r * 0.95} width={6} height={r * 0.42} fill={INK} transform={`rotate(${a})`} />)}
  </g>
);
const Cassette: React.FC<{t: number}> = ({t}) => {
  const {fps} = useVideoConfig();
  const turn = t * 7;
  const playing = t > 10;
  return (
    <div style={{position: 'relative', width: BOX.w, height: BOX.h}}>
      <div style={{position: 'absolute', left: 0, top: 30, perspective: 900}}>
        <svg width={300} height={200} viewBox="-20 -20 320 220" style={{transform: `rotateY(${-22 + Math.sin(t / 30) * 3}deg) rotateX(14deg)`, overflow: 'visible'}}>
          {/* the body's depth (2.5D): a darker slab offset under it */}
          <rect x={10} y={12} width={280} height={170} rx={14} fill={INK2} />
          <rect x={0} y={0} width={280} height={170} rx={14} fill={INK} />
          <rect x={18} y={16} width={244} height={104} rx={8} fill={LIME} />
          <text x={34} y={46} fontFamily={PIXEL} fontSize={26} fill={INK}>原声 · A</text>
          <rect x={64} y={60} width={152} height={50} rx={24} fill={INK} />
          <Reel cx={98} cy={85} turn={turn} r={20} />
          <Reel cx={182} cy={85} turn={turn * 0.8} r={20} />
          <path d="M60 170L76 138H204L220 170" fill={INK2} />
          {[96, 140, 184].map((x) => <circle key={x} cx={x} cy={154} r={5} fill={INK} />)}
        </svg>
      </div>
      {/* the wave coming off it */}
      <svg width={180} height={200} style={{position: 'absolute', left: 300, top: 40}}>
        {Array.from({length: 11}, (_, i) => {
          const h = playing ? 18 + Math.abs(Math.sin(t / 5 + i * 0.9) * Math.sin(t / 13 + i)) * 130 * pop(t, 10 + i * 2, fps, 200) : 4;
          return <rect key={i} x={i * 16} y={100 - h / 2} width={9} height={h} rx={4} fill={i % 3 === 1 ? LIME : INK} />;
        })}
      </svg>
    </div>
  );
};

// ---------------------------------------------------------------- 画面文字: a frame flat on the floor, its words lifting off
const WORDS = ['文', '件', '→', '导', '出'];
const Lifted: React.FC<{t: number}> = ({t}) => {
  return (
    <div style={{position: 'relative', width: BOX.w, height: BOX.h}}>
      <div style={{position: 'absolute', left: 30, top: 120, perspective: 700}}>
        <div style={{width: 380, height: 230, background: SURFACE, border: `2px solid ${LINE2}`, borderRadius: 10, transform: 'rotateX(64deg) rotateZ(-8deg)',
          transformOrigin: '50% 70%', boxShadow: '0 30px 40px rgba(26,26,26,0.08)', padding: 22, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 12}}>
          <div style={{height: 10, width: 200, background: LINE}} />
          <div style={{display: 'flex', gap: 10, fontFamily: SC, fontWeight: 900, fontSize: 52, color: INK}}>
            {WORDS.map((w, i) => <span key={i} style={{opacity: t > 30 + i * 9 ? 0.12 : 1}}>{w}</span>)}
          </div>
          <div style={{height: 10, width: 260, background: LINE}} />
          <div style={{height: 10, width: 160, background: LINE}} />
        </div>
      </div>
      {/* each word rises out of the frame and takes its place in the line above */}
      {WORDS.map((w, i) => {
        const k = easeOut((t - 30 - i * 9) / 22);
        if (k <= 0) return null;
        const from = {x: 88 + i * 62, y: 186};
        const to = {x: 60 + i * 66, y: 0};
        const x = from.x + (to.x - from.x) * k;
        const y = from.y + (to.y - from.y) * k - Math.sin(k * Math.PI) * 50;
        return (
          <span key={i} style={{position: 'absolute', left: x, top: y, fontFamily: PIXEL, fontSize: 72, color: INK, lineHeight: 1,
            transform: `scale(${0.6 + 0.4 * k}) rotate(${(1 - k) * (hash(i) - 0.5) * 60}deg)`, ...(k >= 1 ? marker() : {})}}>{w}</span>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- the scene
const LANES = [
  {word: '画面', mark: '◆', note: '关键帧 #0042', Model: Picture},
  {word: '原声', mark: '|||', note: '转写 12 句', Model: Cassette},
  {word: '画面文字', mark: '[ ]', note: '识别 36 段', Model: Lifted},
];

export const Evidence: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const drop = easeOut((frame - 22) / 18);
  const split = easeOut((frame - 36) / 14);
  const ruleY = RULE.y + (FLOOR - RULE.y) * drop;
  return (
    <Fill>
      <Topo opacity={0.3 * clamp01((frame - 20) / 30)} turn={0.3} />
      {frame < 44 ? <Sculpture phase={11} scale={1.05} y={-0.5} style={{opacity: 1 - clamp01((frame - 16) / 28)}} pose={() => ({spread: easeOut(frame / 36)})} /> : null}
      {frame < 40 ? <NameLockup t={400} exit={clamp01(frame / 22)} /> : null}
      {[0, 1, 2].map((i) => {
        const from = {l: RULE.left + (RULE.width / 3) * i, w: RULE.width / 3};
        const to = {l: COLS[i] - 260, w: 520};
        return <div key={i} style={{position: 'absolute', top: ruleY - 4, height: 8, background: LIME,
          left: from.l + (to.l - from.l) * split, width: from.w + (to.w - from.w) * split}} />;
      })}
      <Sfx name="whoosh" at={20} volume={0.4} rate={0.8} />
      {frame >= 40 ? <Head n="01" title="三路证据" sub="一帧里能读出的三样东西" at={44} /> : null}
      {LANES.map((lane, i) => {
        const at = 50 + i * 12;
        const k = pop(frame, at, fps);
        const t = frame - at - 6;
        return (
          <React.Fragment key={i}>
            <Sfx name="pop" at={at} volume={0.35} />
            <div style={{position: 'absolute', left: COLS[i] - BOX.w / 2, top: BOX.top, width: BOX.w, height: BOX.h, display: 'flex', alignItems: 'center', justifyContent: 'center',
              opacity: frame >= at ? 1 : 0, transform: `translateY(${(1 - k) * 80}px) scale(${0.85 + 0.15 * k})`}}>
              <lane.Model t={t} />
            </div>
            <div style={{position: 'absolute', left: COLS[i] - 300, width: 600, top: FLOOR + 26, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
              opacity: frame >= at + 10 ? 1 : 0, transform: `translateY(${(1 - pop(frame, at + 10, fps)) * 40}px)`}}>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: lane.word.length > 2 ? 84 : 96, color: INK, lineHeight: 1.1}}>
                <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 40, color: INK3, marginRight: 16}}>{lane.mark}</span>{lane.word}
              </span>
              <span style={{fontFamily: CONSOLE, fontSize: 40, color: INK2}}><Typed text={lane.note} at={at + 70} sound={false} /></span>
            </div>
          </React.Fragment>
        );
      })}
      <Sfx name="click" at={60 + 54} volume={0.4} />
      <Sfx name="glitch" at={72} volume={0.18} />
      {Array.from({length: 5}, (_, i) => <Sfx key={i} name="soft" at={98 + i * 9} volume={0.3} rate={1 + i * 0.05} />)}
      {/* the snake keeps crawling, then hurries off to the right */}
      {frame < 110 ? <Crawler x={snakeX(600 + frame) + frame * frame * 0.15} time={(600 + frame - SNAKE_AT) / fps * (1 + frame / 60)} /> : null}
      <Glyphs count={8} seed={21} opacity={0.5} />
    </Fill>
  );
};
