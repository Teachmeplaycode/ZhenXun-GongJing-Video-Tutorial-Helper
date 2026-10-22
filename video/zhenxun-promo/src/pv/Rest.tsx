import React, {useCallback, useEffect, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Blob, CharField, clamp01, CONSOLE, CREAM, DARK, DISPLAY, easeOut, Fill, Glyphs, hash, Head, INK, INK2, INK3, LIME, LIME_DIM, LINE, LINE2, MONO, NIGHT, PAPER, PIXEL, PixelCursor, pop, Rule,
  SC, Sfx, SILK, stepped, SURFACE, textWidth, Typed, useTone, WORDMARK} from './kit';
import {Topo} from './Contour';
import {Sculpture} from './Sculpture';

// The PV from the click scene on (about 23–60 s). From the click to the slogan it runs on the night
// side (warm black, cream, lime; GSAP-like grainy colour shapes), and the slogan folds into a line
// that opens back onto paper for the closing lockup. Scenes hand
// over through shapes (see transitions.tsx) or share an element across the change: the lockup's
// rule drops and splits into the evidence columns; 每秒 is pushed off by an ink panel carrying
// 读一帧, a + opens out of it and grows until its lime fills the frame for 证据 >; the slogan folds
// into a line that the closing lockup rises from. Each section carries an outline index and a
// hairline title, like the UI of a game's field manual; a survey map of the loader's terrain lies
// faintly under some of them.

/** Lime as a highlighter stroke under ink text (lime text alone is too pale on paper). */
const marker = (k = 1): React.CSSProperties => ({backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundRepeat: 'no-repeat',
  backgroundSize: `${clamp01(k) * 100}% 38%`, backgroundPosition: '0 88%'});
/** On the night side lime text is bright enough by itself (a highlighter under cream would muddy it). */
const nightMarker = (k = 1): React.CSSProperties => (k > 0.5 ? {color: LIME} : {});
/** Inside a night scene: the same colour names, night values. */
const night = () => ({INK: DARK.fg, INK2: DARK.fg2, INK3: DARK.fg3, LINE: DARK.line, LINE2: DARK.line2, PAPER: DARK.bg, SURFACE: '#17191A', LIME_DIM: LIME, marker: nightMarker});

const Caption: React.FC<{mark: string; text: string; at: number; size?: number; style?: React.CSSProperties}> = ({mark, text, at, size = 60, style}) => {
  const frame = useCurrentFrame();
  const tone = useTone();
  return (
    <div style={{fontFamily: PIXEL, fontSize: size, color: tone.fg, display: 'flex', gap: 22, alignItems: 'center', ...style}}>
      <span style={{fontFamily: SILK, fontWeight: 700, color: tone.fg3, fontSize: size * 0.8, opacity: frame >= at - 4 ? 1 : 0}}>{mark}</span>
      <Typed text={text} at={at} />
    </div>
  );
};

// ---------------------------------------------------------------- 03 a hand clicks; timecodes pop
const CLICKS = [
  {x: 420, y: 360, tc: '01:12.4', word: '卡点'},
  {x: 1180, y: 300, tc: '03:05.0', word: '回看'},
  {x: 760, y: 680, tc: '04:47.8', word: '证据'},
  {x: 1460, y: 660, tc: '06:30.2', word: '///'},
];
export const LAST_CLICK = CLICKS[CLICKS.length - 1];

const Clicks: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const {fps} = useVideoConfig();
  const at = (i: number) => 26 + i * 38;
  const leg = Math.min(CLICKS.length - 1, Math.max(0, Math.floor((frame - 8) / 38)));
  const from = leg === 0 ? {x: 960, y: 1100} : CLICKS[leg - 1];
  const to = CLICKS[leg];
  const k = easeOut((frame - (at(leg) - 18)) / 16);
  const press = clamp01(1 - Math.abs(frame - at(leg)) / 4);
  return (
    <Fill dark>
      <Blob x={1700} y={180} r={150} turn={frame * 0.6} opacity={0.9} />
      <Head n="03" title="一点回看" sub="时间点 → 原片" />
      {/* a timeline across the bottom; each click marks its place on it */}
      <Rule x={160} y={930} w={1600} k={easeOut(frame / 24)} color={LINE2} thick={3} />
      {CLICKS.map((click, i) => {
        const t = frame - at(i);
        const sounds = <><Sfx name="click" at={at(i)} volume={0.6} /><Sfx name="pop" at={at(i) + 3} volume={0.35} /></>;
        if (t < 0) return <React.Fragment key={i}>{sounds}</React.Fragment>;
        const s = pop(frame, at(i), fps, 260);
        const ring = clamp01(t / 22);
        const tx = 160 + [0.18, 0.47, 0.73, 1][i] * 1600 - 1;
        return (
          <React.Fragment key={i}>
            {sounds}
            {ring < 1 ? <svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
              <circle cx={click.x} cy={click.y} r={20 + easeOut(ring) * 120} fill="none" stroke={INK} strokeWidth={2.5} opacity={1 - ring} />
              <circle cx={click.x} cy={click.y} r={10 + easeOut(ring) * 60} fill="none" stroke={LIME_DIM} strokeWidth={6} opacity={1 - ring} />
            </svg> : null}
            {/* the mark on the timeline and the leader up to it */}
            <div style={{position: 'absolute', left: tx, top: 912, width: 3, height: 38, background: INK, transform: `scaleY(${s})`}} />
            <svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
              <path d={`M${click.x} ${click.y + 30}L${click.x} ${click.y + 30 + (900 - click.y - 30) * easeOut(t / 14)}`} stroke={LINE2} strokeWidth={2} strokeDasharray="6 8" />
            </svg>
            <div style={{position: 'absolute', left: click.x + 36, top: click.y - 150, transform: `scale(${s})`, transformOrigin: '0 100%', display: 'flex', flexDirection: 'column', gap: 4}}>
              <span style={{fontFamily: CONSOLE, fontSize: 56, color: INK2}}>{click.tc}</span>
              <span style={{fontFamily: click.word === '///' ? SILK : SC, fontWeight: 900, fontSize: 104, color: INK, lineHeight: 1.1, ...marker(easeOut((t - 4) / 10))}}>{click.word}</span>
            </div>
          </React.Fragment>
        );
      })}
      <PixelCursor x={from.x + (to.x - from.x) * k} y={from.y + (to.y - from.y) * k} hand size={7} press={press} />
      <Caption mark="//" text="点一下，就跳到那一秒" at={180} style={{position: 'absolute', left: 160, top: 960}} size={48} />
      <Glyphs count={8} seed={31} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 04 截图提问
// The site's own look: white panels, hairline borders, a lime button.
const Window: React.FC<{w: number; h: number}> = ({w, h}) => {
  const tone = useTone();
  const INK = tone.fg;
  const LINE = tone.line2;
  const LINE2 = tone.fg3;
  const SURFACE = tone.dark ? '#17191A' : '#FFFFFF';
  return (
  <svg width={w} height={h} viewBox="0 0 760 470">
    <rect x="1" y="1" width="758" height="468" rx="10" fill={SURFACE} stroke={LINE2} strokeWidth="2" />
    <path d="M1 41H759" stroke={LINE} strokeWidth="2" />
    {[24, 46, 68].map((x, i) => <circle key={x} cx={x} cy="21" r="7" fill={i === 2 ? LIME : LINE} />)}
    <rect x="16" y="56" width="150" height="398" rx="6" fill={tone.dark ? '#1D2021' : '#FAF8F5'} />
    {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x="30" y={74 + i * 34} width={i === 2 ? 110 : 90 + (i % 2) * 20} height="12" rx="4" fill={i === 2 ? INK : LINE} />)}
    {[0, 1, 2, 3, 4].map((i) => <rect key={i} x={186 + i * 74} y="58" width="62" height="30" rx="5" fill={i === 3 ? LIME : tone.dark ? '#1D2021' : '#FAF8F5'} stroke={i === 3 ? 'none' : LINE} />)}
    <rect x="186" y="104" width="556" height="350" rx="6" fill={tone.dark ? '#1D2021' : '#FAF8F5'} stroke={LINE} />
    {Array.from({length: 7}, (_, i) => <line key={i} x1="186" x2="742" y1={104 + (i + 1) * 44} y2={104 + (i + 1) * 44} stroke={LINE} />)}
    <rect x="300" y="190" width="240" height="150" rx="8" fill="none" stroke={INK} strokeWidth="3" strokeDasharray="10 8" />
  </svg>
  );
};

const Screenshot: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const {fps} = useVideoConfig();
  const enter = pop(frame, 0, fps, 160);
  const scan = clamp01((frame - 26) / 34);
  const drag = easeOut((frame - 76) / 30);
  const sent = pop(frame, 138, fps, 200);
  const box = {x: 520, y: 880, w: 880, h: 96};
  const win = {x: 170 + (box.x + 18 - 170) * drag, y: 300 + (box.y + 12 - 300) * drag, s: 1 - drag * (1 - 72 / 470)};
  const hand = frame < 76 ? {x: 560 + (1 - easeOut((frame - 56) / 18)) * 300, y: 540 + (1 - easeOut((frame - 56) / 18)) * 300}
    : frame < 116 ? {x: 560 + (box.x + 80 - 560) * drag, y: 540 + (box.y + 40 - 540) * drag}
    : {x: box.x + 80 + (box.w - 150) * easeOut((frame - 116) / 18), y: box.y + 40};
  const pressing = (frame >= 70 && frame < 108) || Math.abs(frame - 136) < 4;
  return (
    <Fill dark>
      <Sfx name="whoosh" volume={0.35} />
      <Sfx name="glitch" at={26} volume={0.2} />
      <Sfx name="soft" at={72} volume={0.5} />
      <Sfx name="pop" at={106} volume={0.4} />
      <Sfx name="click" at={136} volume={0.6} />
      <Sfx name="ping" at={150} volume={0.3} />
      <Head n="04" title="卡住了？发张截图" sub="截图 → 第几步" />
      <div style={{position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h, borderRadius: 48, border: `2px solid ${frame > 100 ? INK : LINE2}`,
        background: SURFACE, transform: `translateY(${(1 - pop(frame, 40, fps)) * 200}px)`}}>
        <span style={{position: 'absolute', left: 150, top: 24, fontFamily: PIXEL, fontSize: 48, color: INK3}}>{frame > 136 ? '' : '我卡在哪一步？'}</span>
        <span style={{position: 'absolute', right: 12, top: 10, width: 72, height: 72, borderRadius: 36, background: LIME, color: NIGHT, display: 'grid', placeItems: 'center',
          fontFamily: SILK, fontWeight: 700, fontSize: 40, transform: `scale(${1 - clamp01(1 - Math.abs(frame - 136) / 4) * 0.15})`}}>{'>'}</span>
      </div>
      {frame < 140 ? (
        <div style={{position: 'absolute', left: win.x, top: win.y, transform: `scale(${win.s * (0.6 + enter * 0.4)}) rotate(${(1 - drag) * -3}deg)`, transformOrigin: '0 0',
          opacity: clamp01(enter * 2), filter: `drop-shadow(0 18px 30px rgba(26,26,26,${0.12 * (1 - drag)}))`}}>
          <Window w={760} h={470} />
          {scan > 0 && scan < 1 ? <div style={{position: 'absolute', left: -20, right: -20, top: scan * 470, height: 3, background: INK}} /> : null}
        </div>
      ) : null}
      {frame >= 138 ? (
        <>
          <div style={{position: 'absolute', right: 160, top: 300, transform: `scale(${sent})`, transformOrigin: '100% 0'}}>
            <Window w={760 * 0.36} h={470 * 0.36} />
          </div>
          <div style={{position: 'absolute', left: 170, top: 420, width: 1300, transform: `translateY(${(1 - pop(frame, 150, fps)) * 80}px)`, opacity: frame >= 150 ? 1 : 0,
            display: 'flex', flexDirection: 'column', gap: 18}}>
            <div style={{display: 'flex', gap: 22, alignItems: 'center', fontFamily: CONSOLE, fontSize: 52, color: INK2}}>
              <span style={{...marker(), color: INK}}>03:05</span><span style={{fontFamily: PIXEL, fontSize: 44}}>◆ 画面</span>
            </div>
            <div style={{fontFamily: PIXEL, fontSize: 84, color: INK, lineHeight: 1.3}}>
              <Typed text="你在第 3 步：下一步点「导出」" at={158} />
            </div>
          </div>
        </>
      ) : null}
      <PixelCursor x={hand.x} y={hand.y} hand={pressing} size={6} press={pressing ? 1 : 0} />
      <Glyphs count={8} seed={35} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- giant type, handed card to card
const PLUS = (s: number, deg: number) => {
  const a = s * 0.16;
  const pts = [[-a, -s], [a, -s], [a, -a], [s, -a], [s, a], [a, a], [a, s], [-a, s], [-a, a], [-s, a], [-s, -a], [-a, -a]];
  const r = (deg * Math.PI) / 180;
  return `M${pts.map(([x, y]) => `${(960 + x * Math.cos(r) - y * Math.sin(r)).toFixed(1)} ${(540 + x * Math.sin(r) + y * Math.cos(r)).toFixed(1)}`).join('L')}Z`;
};

const Giant: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const {fps} = useVideoConfig();
  const a = pop(frame, 0, fps, 200);
  const panel = pop(frame, 82, fps, 150);
  const open = easeOut((frame - 138) / 22);
  const grow = Math.pow(clamp01((frame - 196) / 26), 2.4);
  const proof = pop(frame, 250, fps, 200);
  return (
    <Fill dark>
      <Sfx name="hit" at={26} volume={0.35} />
      <Sfx name="whoosh" at={78} volume={0.5} />
      <Sfx name="whoosh" at={136} volume={0.45} rate={0.8} />
      <Sfx name="swish" at={190} volume={0.22} />
      <Sfx name="impact" at={250} volume={0.45} />
      <div style={{position: 'absolute', left: -60 + (1 - a) * -900 - panel * 1300, top: -170, fontFamily: SC, fontWeight: 900, fontSize: 760, color: INK, lineHeight: 1, whiteSpace: 'nowrap'}}>每秒</div>
      <div style={{position: 'absolute', left: 96 - panel * 1300, bottom: 96, fontFamily: SILK, fontWeight: 700, fontSize: 64, color: INK2}}>{'>>> 01'}</div>
      {/* the ink panel with 读一帧 */}
      <div style={{position: 'absolute', inset: 0, transform: `translateX(${(1 - panel) * 1920}px)`}}>
        <div style={{position: 'absolute', inset: 0, background: INK}} />
        <div style={{position: 'absolute', right: -140 - (1 - panel) * 300, top: 120, fontFamily: SC, fontWeight: 900, fontSize: 640, color: PAPER, lineHeight: 1, whiteSpace: 'nowrap'}}>读一帧</div>
        <div style={{position: 'absolute', left: 96, top: 96, fontFamily: SILK, fontWeight: 700, fontSize: 64, color: NIGHT}}>||| 02</div>
      </div>
      {frame >= 138 ? (
        <svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
          <path d={PLUS(60 + open * 1500, 45 * (1 - open))} fill={PAPER} />
          <path d={PLUS((230 + grow * 9000) * easeOut((frame - 150) / 14), frame * 1.6)} fill={LIME} />
        </svg>
      ) : null}
      {frame >= 244 ? (
        <>
          <div style={{position: 'absolute', left: 80, top: 150, fontFamily: SC, fontWeight: 900, fontSize: 600, color: NIGHT, lineHeight: 1, whiteSpace: 'nowrap',
            transform: `translateX(${(1 - proof) * -700}px)`}}>证据<span style={{fontFamily: MONO}}>{' >'}</span></div>
          <div style={{position: 'absolute', right: 96, top: 96, fontFamily: SILK, fontWeight: 700, fontSize: 64, color: NIGHT, opacity: proof}}>◆ 03</div>
        </>
      ) : null}
      <Glyphs count={8} seed={41} opacity={0.7} />
    </Fill>
  );
};

// ---------------------------------------------------------------- star burst, 看到哪，问到哪
const Burst: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const texture = useCallback((c: number, r: number, tick: number, cols: number) => {
    const dir = r % 2 ? 1 : -1;
    const shifted = (c + dir * tick * 2 + cols * 8) % 11;
    if (shifted > 7) return null;
    return hash(r, 3) < 0.3 ? LINE2 : LINE;
  }, []);
  const bursts = [4, 96];
  return (
    <Fill grid={false} dark>
      <CharField cell={46} set="帧" fps={12} paint={texture} />
      {bursts.map((b) => <Sfx key={b} name="sparkle" at={b} volume={0.28} />)}
      {bursts.flatMap((start, b) => frame < start ? [] : Array.from({length: 70}, (_, i) => {
        const t = (frame - start) / 60;
        const a = hash(i, b, 1) * Math.PI * 2;
        const speed = 400 + hash(i, b, 2) * 1000;
        const d = speed * (1 - Math.exp(-3.2 * t));
        const fade = clamp01(1.5 - t * 0.9);
        const size = 26 + hash(i, b, 3) * 70;
        return (
          <span key={`${b}-${i}`} style={{position: 'absolute', left: 960 + Math.cos(a) * d * 1.3, top: 540 + Math.sin(a) * d * 0.8, fontFamily: MONO, fontWeight: 800,
            fontSize: size, color: hash(i, b, 4) < 0.55 ? LIME_DIM : INK, opacity: fade, lineHeight: 1,
            transform: `translate(-50%, -50%) rotate(${t * (hash(i, b, 5) - 0.5) * 900}deg)`}}>*</span>
        );
      }))}
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 26}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 168, color: INK, background: PAPER, padding: '4px 40px', lineHeight: 1.1,
          clipPath: `inset(0 ${(1 - easeOut((frame - 10) / 16)) * 100}% 0 0)`}}>看到哪，问到哪</div>
        <div style={{background: PAPER, padding: '4px 18px', opacity: frame > 40 ? 1 : 0}}>
          <Caption mark="<<<" text="视频停在哪一秒，就问那一秒" at={44} size={48} />
        </div>
      </AbsoluteFill>
      <Glyphs count={10} seed={51} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 猜 × 证据
const GAP = 50;
const proofWidth = () => textWidth('证据', `900 300px ${SC}`) + textWidth(' >', `800 300px ${MONO}`);
export const versusX = () => {
  const total = 380 + GAP + 200 + GAP + proofWidth();
  return {x: 960 - total / 2 + 380 + GAP + 100, y: 470};
};

const Versus: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const {fps} = useVideoConfig();
  const guess = pop(frame, 0, fps, 220);
  const strike = easeOut((frame - 30) / 10);
  const proof = pop(frame, 48, fps, 200);
  const X = versusX();
  return (
    <Fill dark>
      <Topo opacity={0.18} turn={1.2} scale={1.3} />
      <Blob x={260} y={880} r={190} turn={-frame * 0.5} opacity={0.85} />
      <Sfx name="hit" at={30} volume={0.4} />
      <Sfx name="whoosh" at={48} volume={0.45} />
      <div style={{position: 'absolute', right: 1920 - X.x + 100 + GAP, top: X.y - 200, fontFamily: SC, fontWeight: 900, fontSize: 380, lineHeight: 1,
        color: frame > 36 ? LINE2 : INK, transform: `scale(${guess})`}}>
        猜
        <div style={{position: 'absolute', left: -30, right: -30, top: '52%', height: 22, background: INK, transform: `scaleX(${strike}) rotate(-8deg)`, transformOrigin: '0 50%'}} />
      </div>
      <div style={{position: 'absolute', left: X.x - 100, top: X.y - 100, width: 200, height: 200, display: 'grid', placeItems: 'center',
        fontFamily: MONO, fontWeight: 800, fontSize: 220, color: LIME_DIM, transform: `rotate(${frame * 4}deg) scale(${pop(frame, 6, fps)})`, lineHeight: 1}}>×</div>
      <div style={{position: 'absolute', left: X.x + 100 + GAP, top: X.y - 160, fontFamily: SC, fontWeight: 900, fontSize: 300, color: INK, lineHeight: 1,
        opacity: frame >= 48 ? 1 : 0, transform: `translateX(${(1 - proof) * 300}px)`, whiteSpace: 'nowrap', ...marker(easeOut((frame - 58) / 14))}}>
        证据<span style={{fontFamily: MONO}}>{' >'}</span>
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 170, display: 'flex', justifyContent: 'center'}}>
        <Caption mark="//" text="不靠猜：每个结论标着时间和出处" at={84} />
      </div>
      <Glyphs count={8} seed={61} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 05 170 秒 → 80 秒
const Speed: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const {fps} = useVideoConfig();
  const run = easeOut((frame - 30) / 70);
  const secs = Math.round(170 - 90 * run);
  const done = frame > 100;
  return (
    <Fill dark>
      <Topo opacity={0.18} turn={2.1} />
      {Array.from({length: 9}, (_, i) => <Sfx key={i} name="soft" at={30 + Math.round((i / 9) * 50)} volume={0.3} rate={1 + i * 0.04} />)}
      <Sfx name="ping" at={100} volume={0.4} />
      <Head n="05" title="导入一个软件教程" sub="文字识别提速" />
      <div style={{position: 'absolute', left: 0, right: 0, top: 300, display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: 36}}>
        <span style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 380, color: INK, lineHeight: 1, letterSpacing: -10, fontVariantNumeric: 'tabular-nums',
          transform: `scale(${done ? 1 + (1 - pop(frame, 100, fps, 260)) * 0.15 : 1})`, transformOrigin: '50% 100%', ...(done ? marker(easeOut((frame - 100) / 12)) : {})}}>{secs}</span>
        <span style={{fontFamily: PIXEL, fontSize: 120, color: INK}}>秒</span>
        <span style={{fontFamily: CONSOLE, fontSize: 120, color: LINE2, textDecoration: 'line-through', opacity: done ? 1 : 0}}>170</span>
      </div>
      <div style={{position: 'absolute', left: 170, top: 780, height: 30, width: 1580 * (secs / 170), background: done ? LIME : INK}} />
      <div style={{position: 'absolute', left: 170, top: 780, height: 30, width: 1580, border: `2px solid ${LINE2}`, boxSizing: 'border-box'}} />
      {Array.from({length: 18}, (_, i) => <div key={i} style={{position: 'absolute', left: 170 + i * (1580 / 17), top: 822, width: 2, height: i % 5 === 0 ? 18 : 9, background: INK3}} />)}
      <div style={{position: 'absolute', left: 0, right: 0, top: 870, display: 'flex', justifyContent: 'center'}}>
        <Caption mark="//" text="导入快一倍多" at={112} />
      </div>
      <Glyphs count={8} seed={65} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 06 the snake in digits
type Cell = 0 | 1 | 2 | 3 | 4; // empty, body, sheen, white eye, lime eye

const useImageGrid = (src: string, cols: number, rows: number) => {
  const [handle] = useState(() => delayRender(`image ${src}`));
  const [grid, setGrid] = useState<Cell[][] | null>(null);
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = cols;
      canvas.height = rows;
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(img, 0, 0, cols, rows);
      const d = ctx.getImageData(0, 0, cols, rows).data;
      setGrid(Array.from({length: rows}, (_, r) => Array.from({length: cols}, (_, c) => {
        const [R, G, B, A] = [d[(r * cols + c) * 4], d[(r * cols + c) * 4 + 1], d[(r * cols + c) * 4 + 2], d[(r * cols + c) * 4 + 3]];
        if (A < 110) return 0;
        if (R > 190 && G > 190 && B > 180) return 3;
        if (G > 150 && B < 140) return 4;
        return R + G + B > 120 ? 2 : 1;
      })));
      continueRender(handle);
    };
    img.onerror = () => continueRender(handle);
    img.src = staticFile(src);
  }, [src, cols, rows, handle]);
  return grid;
};

const Snake: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const {fps} = useVideoConfig();
  const grid = useImageGrid('mascot.png', 104, 64);
  const reveal = easeOut(frame / 40);
  const at = useCallback((c: number, r: number, tick: number) => {
    if (!grid) return 0;
    const wave = Math.round(Math.sin(tick * 0.5 + r * 0.25) * 0.8);
    return grid[r - 2]?.[c - 6 - wave] ?? 0;
  }, [grid]);
  const paint = useCallback((c: number, r: number, tick: number) => {
    const cell = at(c, r, tick);
    if (!cell) return null;
    if (cell >= 3 || hash(c, r, 5) > reveal) return null;
    return cell === 2 ? INK3 : hash(c, r, tick) < 0.85 ? INK : INK2;
  }, [at, reveal]);
  const eyes = useCallback((c: number, r: number, tick: number) => {
    const cell = at(c, r, tick);
    if (cell < 3 || frame < 34) return null;
    return frame % 130 > 121 ? null : cell === 3 ? CREAM : LIME;
  }, [at, frame]);
  return (
    <Fill dark>
      <Sfx name="soft" at={34} volume={0.5} />
      <CharField cell={16} set="digits" fps={12} paint={paint} />
      <CharField cell={16} set="█" fps={12} paint={eyes} />
      <Head n="06" title="小蛇" sub="陪你看完每一帧" x={1080} y={150} />
      <div style={{position: 'absolute', left: 1080, top: 400, display: 'flex', flexDirection: 'column', gap: 30}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 132, color: INK, lineHeight: 1, display: 'flex', gap: 26, alignItems: 'center',
          clipPath: `inset(0 ${(1 - easeOut((frame - 36) / 14)) * 100}% 0 0)`}}>
          <span style={{fontFamily: MONO, color: LIME_DIM}}>*</span><span style={marker(easeOut((frame - 50) / 14))}>视频理解</span><span style={{fontFamily: MONO, color: INK3}}>{'>>'}</span>
        </div>
        <div style={{fontFamily: PIXEL, fontSize: 48, color: INK2}}>
          <Typed text="软件教程 · 课程 · 科普" at={60} />
        </div>
      </div>
      <Glyphs count={8} seed={81} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 07 the wall, then the list
const WALL = ['B站', '抖音', '小红书', '快手', '视频号', '本地上传', '截图提问', '慢放回看', '笔记长图', '证据标签', '原声转写', '画面文字',
  '关键帧', '时间轴', '卡点分析', '推荐问题', 'Tab 补全', '手机适配', '附图提问', '导出预览'];
const LIST = ['B站 · 抖音 · 小红书 · 快手 · 视频号', '本地上传，一样能看', '截图提问：我卡在哪一步', '慢放回看，逐帧对照', '笔记一键存成长图'];
const COLLAPSE_AT = 80;

const Wall: React.FC = () => {
  const frame = useCurrentFrame();
  const {INK, INK2, INK3, LINE, LINE2, PAPER, SURFACE, LIME_DIM, marker} = night(); // the night side
  const collapse = easeOut((frame - COLLAPSE_AT) / 24);
  const cols = 5;
  return (
    <Fill dark>
      <Sfx name="swish" at={COLLAPSE_AT - 16} volume={0.35} />
      <Blob x={1640} y={820} r={220} turn={frame * 0.4} opacity={0.85 * clamp01((frame - COLLAPSE_AT) / 20)} />
      <div style={{position: 'absolute', inset: 0, opacity: 1 - collapse * 0.85}}>
        {Array.from({length: 9 * cols}, (_, i) => {
          const col = i % cols;
          const row = Math.floor(i / cols);
          const word = WALL[(i * 7 + row) % WALL.length];
          const speed = col % 2 ? 7 : 4.5;
          const y = (((row * 140 + (col % 2 ? -1 : 1) * frame * speed) % 1260) + 1260) % 1260 - 140;
          const lit = hash(i, Math.floor(frame / 8)) < 0.12;
          return (
            <div key={i} style={{position: 'absolute', left: 60 + col * 370, top: y, width: 340, fontFamily: PIXEL, fontSize: 72, whiteSpace: 'nowrap',
              color: lit ? INK : LINE2, ...(lit ? marker() : {}), transform: `translateY(${collapse * (540 - y) * 0.6}px) scale(${1 - collapse * 0.4})`}}>{word}</div>
          );
        })}
      </div>
      {frame >= COLLAPSE_AT ? <Head n="07" title="能看什么" sub="平台 · 功能" at={COLLAPSE_AT} /> : null}
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        <div style={{display: 'flex', flexDirection: 'column', gap: 22, paddingTop: 80}}>
          {LIST.map((line, i) => {
            const at = COLLAPSE_AT + 22 + i * 16;
            const on = frame >= at;
            const current = Math.min(LIST.length - 1, Math.floor((frame - COLLAPSE_AT - 22) / 16)) === i;
            return (
              <div key={i} style={{display: 'flex', gap: 28, alignItems: 'center', opacity: on ? 1 : 0, transform: `translateX(${(1 - easeOut((frame - at) / 8)) * -80}px)`}}>
                <Sfx name="soft" at={at} volume={0.45} />
                <span style={{fontFamily: CONSOLE, fontSize: 48, color: current ? INK : INK3, width: 60}}>0{i + 1}</span>
                <span style={{fontFamily: PIXEL, fontSize: 84, color: INK, lineHeight: 1.2, ...(current ? marker(easeOut((frame - at) / 8)) : {})}}>{line}</span>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
      <Glyphs count={8} seed={91} opacity={0.6} />
    </Fill>
  );
};

// ---------------------------------------------------------------- slogan, folding into the lockup
const Mark: React.FC<{size: number}> = ({size}) => (
  <svg width={size} height={size * 48 / 44} viewBox="14 8 44 48">
    <path fill={INK} d="M38.5 12.5c8.7 0 14.5 4.7 14.5 11.2 0 5.8-4.9 9.3-11.5 10.7-5.3 1.1-8.6 3.5-8.6 7.2 0 4.6 4.9 7.6 10.4 9.2-8.4 3.3-17.5.4-21.4-5.7-5.2-8.2-1.1-17.7 8.8-21.4 3.2-1.2 5.3-2.6 5.3-5.6 0-3.6 2.7-6.1 6.5-6.1Z" />
    <ellipse cx="37" cy="22.5" rx="3.8" ry="5.8" fill={SURFACE} />
    <circle cx="46" cy="20" r="3.2" fill={LIME} />
  </svg>
);

const FOLD_AT = 200; // the slogan folds into a line…
const OPEN = [222, 250]; // …which opens out into paper…
const LOCK_AT = 240; // …and the lockup rises from it
const LINE_Y = 640;

const Finale: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const a = pop(frame, 0, fps, 200);
  const b = pop(frame, 60, fps, 200);
  const c = pop(frame, 110, fps);
  const fold = easeOut((frame - FOLD_AT) / 20);
  const squash = (y: number) => `translateY(${(LINE_Y - y) * fold}px) scaleY(${1 - fold})`;
  const t = frame - LOCK_AT;
  const rise = easeOut(t / 24);
  const open = easeOut((frame - OPEN[0]) / (OPEN[1] - OPEN[0]));
  const out = clamp01((frame - (durationInFrames - 36)) / 36);
  const steps = stepped(frame, 60, 12);
  const line = easeOut((frame - FOLD_AT - 6) / 16);
  const N = night();
  return (
    <Fill dark>
      <Sfx name="hit" at={20} volume={0.35} />
      <Sfx name="hit" at={60} volume={0.35} />
      <Sfx name="riser" at={LOCK_AT - 150} startFrom={Math.round(7.4 * fps)} volume={0.25} />
      <Sfx name="whoosh" at={FOLD_AT} volume={0.5} rate={0.9} />
      <Sfx name="swish" at={OPEN[0] - 6} volume={0.4} />
      <Sfx name="swell" at={LOCK_AT - 6} volume={0.5} />
      <Blob x={1620} y={250} r={200} turn={frame * 0.5} opacity={0.85 * (1 - fold)} />
      {/* the slogan, on the night side */}
      {frame < OPEN[1] ? (
        <>
          <div style={{position: 'absolute', left: 110, top: 120, fontFamily: SC, fontWeight: 900, fontSize: 280, color: N.INK, lineHeight: 1,
            transform: `translateX(${(1 - a) * -700}px) ${squash(260)}`}}>
            <span style={{fontFamily: MONO, color: N.INK3}}>*//</span>看见
          </div>
          <div style={{position: 'absolute', right: 110, top: 420, fontFamily: SC, fontWeight: 900, fontSize: 280, color: LIME, lineHeight: 1, opacity: frame >= 60 ? 1 : 0,
            transform: `translateX(${(1 - b) * 700}px) ${squash(560)}`}}>再求证</div>
          <div style={{position: 'absolute', left: 300, top: 470, fontFamily: MONO, fontWeight: 800, fontSize: 240, color: LIME, lineHeight: 1, opacity: frame > 80 ? 1 : 0,
            transform: `rotate(${(frame - 80) * 3}deg) scale(${pop(frame, 80, fps) * (1 - fold)})`}}>+</div>
          <div style={{position: 'absolute', left: 0, right: 0, bottom: 110, display: 'flex', justifyContent: 'center', opacity: frame >= 110 ? 1 : 0,
            transform: `translateY(${(1 - c) * 60}px) ${squash(930)}`}}>
            <div style={{fontFamily: SILK, fontWeight: 700, fontSize: 72, color: N.INK3, display: 'flex', gap: 24, alignItems: 'center'}}>
              {'{'}<Typed text="回到原片那一刻" at={116} style={{fontFamily: PIXEL, fontSize: 84, color: N.INK}} />{'}>'}
            </div>
          </div>
        </>
      ) : null}
      {/* the line opens out into paper: the night ends, the day theme comes back for the name */}
      {frame >= OPEN[0] ? (
        <div style={{position: 'absolute', left: 0, right: 0, top: LINE_Y - (LINE_Y + 10) * open, bottom: (1080 - LINE_Y) - (1080 - LINE_Y + 10) * open, background: PAPER}} />
      ) : null}
      {frame >= FOLD_AT ? <div style={{position: 'absolute', top: LINE_Y - 4, height: 8, background: LIME, left: 960 - 620 * line, width: 1240 * line}} /> : null}
      {frame >= LOCK_AT - 10 ? (
        <AbsoluteFill style={{clipPath: `inset(${LINE_Y - (LINE_Y + 10) * open}px 0 ${(1080 - LINE_Y) - (1080 - LINE_Y + 10) * open}px 0)`}}>
          <Sculpture phase={20} scale={1.1} y={-1} pose={() => ({spread: 1 - easeOut((frame - LOCK_AT + 10) / 60)})} />
        </AbsoluteFill>
      ) : null}
      {frame >= LOCK_AT ? (
        <>
          <div style={{position: 'absolute', left: 0, right: 0, top: LINE_Y - 330, height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 50, transform: `translateY(${(1 - rise) * 330}px)`}}>
              <div style={{transform: `scale(${pop(t, 10, fps)})`}}><Mark size={190} /></div>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: 230, color: INK, lineHeight: 1}}><span style={{color: LIME, textShadow: `6px 6px 0 ${INK}`}}>帧</span>寻</span>
              <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 124, color: INK, letterSpacing: -5, lineHeight: 1}}>
                GongJ<span style={{color: '#9CC229'}}>!</span>ng<span style={{color: '#9CC229'}}>{steps % 10 < 7 ? '?' : '!'}</span>
              </span>
            </div>
          </div>
          <div style={{position: 'absolute', left: 0, right: 0, top: LINE_Y + 40, display: 'flex', justifyContent: 'center', gap: 40, alignItems: 'center'}}>
            <span style={{fontFamily: PIXEL, fontSize: 60, color: INK}}><Typed text="看见，再求证。" at={LOCK_AT + 26} cps={22} /></span>
            <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 48, color: LINE2, opacity: t > 50 ? 1 : 0}}>|||</span>
            <span style={{fontFamily: DISPLAY, fontWeight: 700, fontSize: 44, color: INK}}><Typed text="linyi.work/ZhenXun" at={LOCK_AT + 54} cps={34} /></span>
          </div>
        </>
      ) : null}
      <Glyphs count={10} seed={101} opacity={0.6} />
      <AbsoluteFill style={{background: PAPER, opacity: out}} />
    </Fill>
  );
};

export const REST = {Clicks, Screenshot, Giant, Burst, Versus, Speed, Snake, Wall, Finale};
