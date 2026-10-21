import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BG, BLUE, CharField, clamp01, CONSOLE, DIM, DISPLAY, easeOut, Fill, Glyphs, hash, LIME, MONO, PIXEL, PixelCursor, pop, SC, Sfx, SILK, stepped, Typed, WHITE, WORDMARK} from './kit';
import {NameLockup, RULE, textMask} from './Opening';

// The PV after the name (10–60 s). Scenes hand over through shapes (see transitions.tsx) or share
// an element across the change: the lockup's rule drops and splits into the evidence columns; the
// 每秒 card is pushed off by the blue 读一帧 panel, a + opens out of it and grows until its lime
// fills the frame for 证据 >; the slogan folds into a line that the closing lockup rises from.
// Type: Noto Sans SC Black for the big words, a Chinese pixel face for captions and labels, a
// terminal face for code and timecodes, the site's Unbounded for Latin display.

const OLIVE = '#7E8C3C';
const MUTED = '#8B9171';

const Label: React.FC<{children: React.ReactNode; color?: string; ink?: string; style?: React.CSSProperties}> = ({children, color = LIME, ink = BG, style}) => (
  <span style={{fontFamily: CONSOLE, background: color, color: ink, padding: '0 14px', lineHeight: 1.1, ...style}}>{children}</span>
);

const Caption: React.FC<{mark: string; markColor?: string; text: string; at: number; size?: number; style?: React.CSSProperties}> = ({mark, markColor = LIME, text, at, size = 60, style}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{fontFamily: PIXEL, fontSize: size, color: WHITE, display: 'flex', gap: 22, alignItems: 'center', ...style}}>
      <span style={{fontFamily: SILK, fontWeight: 700, color: markColor, fontSize: size * 0.8, opacity: frame >= at - 4 ? 1 : 0}}>{mark}</span>
      <Typed text={text} at={at} />
    </div>
  );
};

// ---------------------------------------------------------------- 三路证据 (from the lockup's rule)
const LANES = [
  {word: '画面', mark: '◆', color: BLUE},
  {word: '原声', mark: '|||', color: LIME},
  {word: '画面文字', mark: '[ ]', color: WHITE},
];
const FLOOR = 1010; // the rule drops to here and the columns rise from it

const Evidence: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const drop = easeOut((frame - 22) / 18); // the rule falls…
  const split = easeOut((frame - 36) / 14); // …widens and splits into three
  const ruleY = RULE.y + (FLOOR - RULE.y) * drop;
  const paint = useCallback((c: number, r: number, tick: number, cols: number, rows: number) => {
    const third = Math.floor(cols / 3);
    const lane = Math.min(2, Math.floor(c / third));
    const inLane = c % third > 4 && c % third < third - 4;
    if (!inLane) return null;
    const level = easeOut((frame - 44 - lane * 12) / 34) * 0.6 + Math.sin(tick * 0.7 + c * 0.9) * 0.02 + hash(c, tick) * 0.04;
    const fromBottom = FLOOR / 1080 - r / rows;
    if (fromBottom < 0) return null;
    if (fromBottom > level) return hash(c, r, tick) < 0.02 ? DIM : null;
    return hash(c, r, tick) < 0.75 ? LANES[lane].color : DIM;
  }, [frame]);
  return (
    <Fill>
      <CharField cell={20} set="code" fps={15} paint={paint} style={{opacity: 0.85}} />
      {frame < 40 ? <NameLockup t={400} exit={clamp01(frame / 22)} /> : null}
      {/* the rule: one line, then three floors under the columns */}
      {[0, 1, 2].map((i) => {
        const from = {l: RULE.left + (RULE.width / 3) * i, w: RULE.width / 3};
        const to = {l: 640 * i + 48, w: 640 - 96};
        return <div key={i} style={{position: 'absolute', top: ruleY - 3, height: 6, background: LIME,
          left: from.l + (to.l - from.l) * split, width: from.w + (to.w - from.w) * split + (1 - split)}} />;
      })}
      <Sfx name="whoosh" at={20} volume={0.4} rate={0.8} />
      {LANES.map((lane, i) => {
        const at = 56 + i * 14;
        const k = pop(frame, at, fps);
        return (
          <React.Fragment key={i}>
            <Sfx name="soft" at={at} volume={0.5} />
            <div style={{position: 'absolute', left: 640 * i, width: 640, top: 150, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18,
              opacity: frame >= at ? 1 : 0, transform: `translateY(${(1 - k) * 60}px)`}}>
              <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 44, color: lane.color, transform: `rotate(${(1 - k) * 90}deg)`}}>{lane.mark}</span>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: lane.word.length > 2 ? 120 : 150, color: WHITE, lineHeight: 1.25, whiteSpace: 'nowrap', background: BG,
                padding: '0 22px', clipPath: `inset(0 ${(1 - clamp01(k)) * 100}% 0 0)`}}>{lane.word}</span>
            </div>
          </React.Fragment>
        );
      })}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 150, display: 'flex', justifyContent: 'center'}}>
        <div style={{background: BG, padding: '8px 28px'}}><Caption mark=">>>" text="每一句回答，都有出处" at={124} size={72} /></div>
      </div>
      <Glyphs count={10} seed={21} opacity={0.8} />
    </Fill>
  );
};

// ---------------------------------------------------------------- a hand clicks; timecodes pop
const CLICKS = [
  {x: 420, y: 330, tc: '01:12.4', word: '卡点', color: LIME},
  {x: 1180, y: 250, tc: '03:05.0', word: '回看', color: BLUE},
  {x: 760, y: 640, tc: '04:47.8', word: '证据', color: WHITE},
  {x: 1460, y: 620, tc: '06:30.2', word: '///', color: LIME},
];
export const LAST_CLICK = CLICKS[CLICKS.length - 1];

const Clicks: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const at = (i: number) => 26 + i * 38;
  const leg = Math.min(CLICKS.length - 1, Math.max(0, Math.floor((frame - 8) / 38)));
  const from = leg === 0 ? {x: 960, y: 1100} : CLICKS[leg - 1];
  const to = CLICKS[leg];
  const k = easeOut((frame - (at(leg) - 18)) / 16);
  const press = clamp01(1 - Math.abs(frame - at(leg)) / 4);
  const grid = useCallback((c: number, r: number) => (c % 8 === 0 && r % 4 === 0 ? '#22261A' : null), []);
  return (
    <Fill>
      <CharField cell={22} set="marks" fps={6} paint={grid} />
      {CLICKS.map((click, i) => {
        const t = frame - at(i);
        const sounds = <><Sfx name="click" at={at(i)} volume={0.6} /><Sfx name="pop" at={at(i) + 3} volume={0.35} /></>;
        if (t < 0) return <React.Fragment key={i}>{sounds}</React.Fragment>;
        const s = pop(frame, at(i), fps, 260);
        const ring = clamp01(t / 22);
        return (
          <React.Fragment key={i}>
            {sounds}
            {ring < 1 ? Array.from({length: 8}, (_, j) => {
              const a = (j / 8) * Math.PI * 2;
              const d = 30 + easeOut(ring) * 130;
              return <span key={j} style={{position: 'absolute', left: click.x + Math.cos(a) * d - 14, top: click.y + Math.sin(a) * d - 20, fontFamily: MONO,
                fontWeight: 800, fontSize: 34, color: LIME, opacity: 1 - ring, transform: `rotate(${t * 9}deg)`}}>+</span>;
            }) : null}
            <div style={{position: 'absolute', left: click.x + 40, top: click.y - 130, transform: `scale(${s})`, transformOrigin: '0 100%',
              display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start'}}>
              <Label style={{fontSize: 60}}>{click.tc}</Label>
              <span style={{fontFamily: PIXEL, fontSize: 96, color: BG, background: click.color, padding: '0 18px', lineHeight: 1.15,
                clipPath: `inset(0 ${(1 - easeOut((t - 3) / 8)) * 100}% 0 0)`}}>{click.word}</span>
            </div>
          </React.Fragment>
        );
      })}
      <PixelCursor x={from.x + (to.x - from.x) * k} y={from.y + (to.y - from.y) * k} hand size={7} press={press} />
      <Caption mark="//" markColor={BLUE} text="点一下，就跳到那一秒" at={180} style={{position: 'absolute', left: 92, bottom: 80}} />
      <Glyphs count={8} seed={31} opacity={0.75} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 截图提问
// A software window (drawn as a wireframe) is scanned, dragged into the question box and sent;
// the answer names the step and the moment in the video.
const Window: React.FC<{w: number; h: number}> = ({w, h}) => (
  <svg width={w} height={h} viewBox="0 0 760 470">
    <rect x="1" y="1" width="758" height="468" rx="10" fill="#14170F" stroke="#3A3F2C" strokeWidth="2" />
    <rect x="1" y="1" width="758" height="40" rx="10" fill="#1E2217" />
    {[24, 46, 68].map((x, i) => <circle key={x} cx={x} cy="21" r="7" fill={['#3A3F2C', '#3A3F2C', LIME][i]} />)}
    <rect x="16" y="56" width="150" height="398" rx="6" fill="#1A1D14" />
    {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x="30" y={74 + i * 34} width={i === 2 ? 110 : 90 + (i % 2) * 20} height="14" rx="4" fill={i === 2 ? BLUE : '#2C3123'} />)}
    {[0, 1, 2, 3, 4].map((i) => <rect key={i} x={186 + i * 74} y="58" width="62" height="30" rx="5" fill={i === 3 ? LIME : '#2C3123'} />)}
    <rect x="186" y="104" width="556" height="350" rx="6" fill="#0F110B" stroke="#2C3123" />
    {Array.from({length: 7}, (_, i) => <line key={i} x1="186" x2="742" y1={104 + (i + 1) * 44} y2={104 + (i + 1) * 44} stroke="#1D2116" />)}
    <rect x="300" y="190" width="240" height="150" rx="8" fill="none" stroke={BLUE} strokeWidth="3" strokeDasharray="10 8" />
  </svg>
);

const Screenshot: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = pop(frame, 0, fps, 160);
  const scan = clamp01((frame - 26) / 34);
  const drag = easeOut((frame - 76) / 30); // into the box
  const sent = pop(frame, 138, fps, 200);
  const box = {x: 520, y: 880, w: 880, h: 96};
  // the window shrinks into a thumbnail at the left of the box
  const win = {x: 170 + (box.x + 18 - 170) * drag, y: 230 + (box.y + 12 - 230) * drag, s: 1 - drag * (1 - 72 / 470)};
  const hand = frame < 76 ? {x: 560 + (1 - easeOut((frame - 56) / 18)) * 300, y: 470 + (1 - easeOut((frame - 56) / 18)) * 300}
    : frame < 116 ? {x: 560 + (box.x + 80 - 560) * drag, y: 470 + (box.y + 40 - 470) * drag}
    : {x: box.x + 80 + (box.w - 150) * easeOut((frame - 116) / 18), y: box.y + 40};
  const pressing = (frame >= 70 && frame < 108) || Math.abs(frame - 136) < 4;
  return (
    <Fill>
      <Sfx name="whoosh" volume={0.35} />
      <Sfx name="glitch" at={26} volume={0.25} />
      <Sfx name="soft" at={72} volume={0.5} />
      <Sfx name="pop" at={106} volume={0.4} />
      <Sfx name="click" at={136} volume={0.6} />
      <Sfx name="ping" at={150} volume={0.3} />
      <Caption mark="//" text="卡住了？发张截图" at={8} size={72} style={{position: 'absolute', left: 92, top: 84}} />
      {/* the question box */}
      <div style={{position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h, borderRadius: 48, border: `3px solid ${frame > 100 ? LIME : '#3A3F2C'}`,
        background: '#14170F', transform: `translateY(${(1 - pop(frame, 40, fps)) * 200}px)`}}>
        <span style={{position: 'absolute', left: 150, top: 24, fontFamily: PIXEL, fontSize: 48, color: MUTED}}>{frame > 136 ? '' : '我卡在哪一步？'}</span>
        <span style={{position: 'absolute', right: 14, top: 12, width: 72, height: 72, borderRadius: 36, background: LIME, color: BG, display: 'grid', placeItems: 'center',
          fontFamily: SILK, fontWeight: 700, fontSize: 40, transform: `scale(${1 - clamp01(1 - Math.abs(frame - 136) / 4) * 0.15})`}}>{'>'}</span>
      </div>
      {frame < 140 ? (
        <div style={{position: 'absolute', left: win.x, top: win.y, transform: `scale(${win.s * (0.6 + enter * 0.4)}) rotate(${(1 - drag) * -3}deg)`, transformOrigin: '0 0',
          opacity: clamp01(enter * 2)}}>
          <Window w={760} h={470} />
          {scan > 0 && scan < 1 ? <div style={{position: 'absolute', left: 0, right: 0, top: scan * 470, height: 4, background: LIME, boxShadow: `0 0 0 2px ${BG}`}} /> : null}
        </div>
      ) : null}
      {/* the sent question (thumbnail) and the answer */}
      {frame >= 138 ? (
        <>
          <div style={{position: 'absolute', right: 160, top: 210, transform: `scale(${sent})`, transformOrigin: '100% 0'}}>
            <Window w={760 * 0.32} h={470 * 0.32} />
          </div>
          <div style={{position: 'absolute', left: 170, top: 400, width: 1400, transform: `translateY(${(1 - pop(frame, 150, fps)) * 80}px)`, opacity: frame >= 150 ? 1 : 0,
            display: 'flex', flexDirection: 'column', gap: 22}}>
            <div style={{display: 'flex', gap: 18, alignItems: 'center'}}>
              <Label style={{fontSize: 56}}>03:05</Label>
              <Label color={BLUE} ink={WHITE} style={{fontSize: 48, fontFamily: PIXEL, padding: '4px 14px'}}>◆ 画面</Label>
            </div>
            <div style={{fontFamily: PIXEL, fontSize: 84, color: WHITE, lineHeight: 1.3}}>
              <Typed text="你在第 3 步：下一步点「导出」" at={158} />
            </div>
          </div>
        </>
      ) : null}
      <PixelCursor x={hand.x} y={hand.y} hand={pressing} size={6} press={pressing ? 1 : 0} />
      <Glyphs count={8} seed={35} opacity={0.75} />
    </Fill>
  );
};

// ---------------------------------------------------------------- giant type, handed card to card
const PLUS = (s: number, deg: number) => {
  // a + as a path at the frame centre, `s` its arm length
  const a = s * 0.16;
  const pts = [[-a, -s], [a, -s], [a, -a], [s, -a], [s, a], [a, a], [a, s], [-a, s], [-a, a], [-s, a], [-s, -a], [-a, -a]];
  const r = (deg * Math.PI) / 180;
  return `M${pts.map(([x, y]) => `${(960 + x * Math.cos(r) - y * Math.sin(r)).toFixed(1)} ${(540 + x * Math.sin(r) + y * Math.cos(r)).toFixed(1)}`).join('L')}Z`;
};

const Giant: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const a = pop(frame, 0, fps, 200); // 每秒 in
  const panel = pop(frame, 62, fps, 150); // the blue panel pushes it out
  const open = easeOut((frame - 128) / 22); // a dark + opens in the blue
  const grow = Math.pow(clamp01((frame - 188) / 22), 2.4); // the lime + grows to fill the frame
  const proof = pop(frame, 214, fps, 200);
  return (
    <Fill>
      <Sfx name="hit" volume={0.35} />
      <Sfx name="whoosh" at={62} volume={0.5} />
      <Sfx name="whoosh" at={128} volume={0.45} rate={0.8} />
      <Sfx name="swish" at={180} volume={0.22} />
      <Sfx name="impact" at={214} volume={0.35} />
      {/* 每秒 */}
      <div style={{position: 'absolute', left: -60 + (1 - a) * -900 - panel * 1300, top: -170, fontFamily: SC, fontWeight: 900, fontSize: 760, color: WHITE, lineHeight: 1, whiteSpace: 'nowrap'}}>每秒</div>
      <div style={{position: 'absolute', left: 90 - panel * 1300, bottom: 90}}><Label style={{fontSize: 72, fontFamily: SILK, fontWeight: 700}}>{'>>> 01'}</Label></div>
      {/* the blue panel with 读一帧 */}
      <div style={{position: 'absolute', inset: 0, transform: `translateX(${(1 - panel) * 1920}px)`}}>
        <div style={{position: 'absolute', inset: 0, background: BLUE}} />
        <div style={{position: 'absolute', right: -140 - (1 - panel) * 300, top: 120, fontFamily: SC, fontWeight: 900, fontSize: 640, color: WHITE, lineHeight: 1, whiteSpace: 'nowrap'}}>读一帧</div>
        <div style={{position: 'absolute', left: 90, top: 90, fontFamily: SILK, fontWeight: 700, fontSize: 64, color: BG}}>||| 02</div>
      </div>
      {/* a + opens out of the blue (dark inside) with a lime + turning in it; then the lime + grows over everything */}
      {frame >= 128 ? (
        <svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
          <path d={PLUS(60 + open * 1500, 45 * (1 - open))} fill={BG} />
          <path d={PLUS((230 + grow * 9000) * easeOut((frame - 140) / 14), frame * 1.6)} fill={LIME} />
        </svg>
      ) : null}
      {/* 证据 > on the lime */}
      {frame >= 210 ? (
        <>
          <div style={{position: 'absolute', left: 80, top: 150, fontFamily: SC, fontWeight: 900, fontSize: 600, color: BG, lineHeight: 1, whiteSpace: 'nowrap',
            transform: `translateX(${(1 - proof) * -700}px)`}}>证据<span style={{fontFamily: MONO, color: BLUE}}>{' >'}</span></div>
          <div style={{position: 'absolute', right: 90, top: 90, fontFamily: SILK, fontWeight: 700, fontSize: 64, color: BG, opacity: proof}}>◆ 03</div>
        </>
      ) : null}
      <Glyphs count={8} seed={41} />
    </Fill>
  );
};

// ---------------------------------------------------------------- star burst, 看到哪，问到哪
const Burst: React.FC = () => {
  const frame = useCurrentFrame();
  const texture = useCallback((c: number, r: number, tick: number, cols: number) => {
    const dir = r % 2 ? 1 : -1;
    const shifted = (c + dir * tick * 2 + cols * 8) % 11;
    if (shifted > 7) return null;
    return hash(r, 3) < 0.3 ? '#2E3423' : '#1D2116';
  }, []);
  const bursts = [4, 96];
  return (
    <Fill>
      <CharField cell={46} set="帧" fps={12} paint={texture} />
      {bursts.map((b) => <Sfx key={b} name="sparkle" at={b} volume={0.45} />)}
      {bursts.flatMap((start, b) => frame < start ? [] : Array.from({length: 70}, (_, i) => {
        const t = (frame - start) / 60;
        const a = hash(i, b, 1) * Math.PI * 2;
        const speed = 400 + hash(i, b, 2) * 1000;
        const d = speed * (1 - Math.exp(-3.2 * t));
        const fade = clamp01(1.5 - t * 0.9);
        const size = 26 + hash(i, b, 3) * 70;
        return (
          <span key={`${b}-${i}`} style={{position: 'absolute', left: 960 + Math.cos(a) * d * 1.3, top: 540 + Math.sin(a) * d * 0.8, fontFamily: MONO, fontWeight: 800,
            fontSize: size, color: hash(i, b, 4) < 0.8 ? LIME : WHITE, opacity: fade, lineHeight: 1,
            transform: `translate(-50%, -50%) rotate(${t * (hash(i, b, 5) - 0.5) * 900}deg)`}}>*</span>
        );
      }))}
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 26}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 168, color: WHITE, background: BG, padding: '4px 40px', lineHeight: 1.1,
          clipPath: `inset(0 ${(1 - easeOut((frame - 10) / 16)) * 100}% 0 0)`}}>看到哪，问到哪</div>
        <div style={{background: BG, padding: '4px 18px', opacity: frame > 40 ? 1 : 0, display: 'flex', gap: 18, alignItems: 'center'}}>
          <Caption mark="<<<" text="视频停在哪一秒，就问那一秒" at={44} size={48} />
        </div>
      </AbsoluteFill>
      <Glyphs count={10} seed={51} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 猜 × 证据
export const VERSUS_X = {x: 960, y: 470};

const Versus: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const guess = pop(frame, 0, fps, 220);
  const strike = easeOut((frame - 30) / 10);
  const proof = pop(frame, 48, fps, 200);
  return (
    <Fill>
      <Sfx name="hit" at={30} volume={0.4} />
      <Sfx name="whoosh" at={48} volume={0.45} />
      <div style={{position: 'absolute', right: 1920 - VERSUS_X.x + 140, top: VERSUS_X.y - 200, fontFamily: SC, fontWeight: 900, fontSize: 380, lineHeight: 1,
        color: frame > 36 ? '#3A3D33' : WHITE, transform: `scale(${guess})`}}>
        猜
        <div style={{position: 'absolute', left: -30, right: -30, top: '52%', height: 26, background: LIME, transform: `scaleX(${strike}) rotate(-8deg)`, transformOrigin: '0 50%'}} />
      </div>
      <div style={{position: 'absolute', left: VERSUS_X.x - 100, top: VERSUS_X.y - 100, width: 200, height: 200, display: 'grid', placeItems: 'center',
        fontFamily: MONO, fontWeight: 800, fontSize: 220, color: BLUE, transform: `rotate(${frame * 4}deg) scale(${pop(frame, 6, fps)})`, lineHeight: 1}}>×</div>
      <div style={{position: 'absolute', left: VERSUS_X.x + 140, top: VERSUS_X.y - 160, fontFamily: SC, fontWeight: 900, fontSize: 300, color: LIME, lineHeight: 1,
        opacity: frame >= 48 ? 1 : 0, transform: `translateX(${(1 - proof) * 300}px)`, whiteSpace: 'nowrap'}}>
        证据<span style={{fontFamily: MONO, color: WHITE}}>{' >'}</span>
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 170, display: 'flex', justifyContent: 'center'}}>
        <Caption mark="//" text="不靠猜：每个结论标着时间和出处" at={84} />
      </div>
      <Glyphs count={10} seed={61} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 170 秒 → 80 秒
const Speed: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const run = easeOut((frame - 30) / 70);
  const secs = Math.round(170 - 90 * run);
  const enter = pop(frame, 0, fps);
  const done = frame > 100;
  return (
    <Fill>
      {Array.from({length: 9}, (_, i) => <Sfx key={i} name="soft" at={30 + Math.round((i / 9) * 50)} volume={0.3} rate={1 + i * 0.04} />)}
      <Sfx name="ping" at={100} volume={0.4} />
      <div style={{position: 'absolute', left: 170, top: 180, transform: `translateX(${(1 - enter) * -200}px)`}}>
        <Caption mark="▲" text="导入一个软件教程" at={4} size={72} />
      </div>
      <div style={{position: 'absolute', left: 160, top: 300, display: 'flex', alignItems: 'baseline', gap: 36}}>
        <span style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 380, color: done ? LIME : WHITE, lineHeight: 1, letterSpacing: -10,
          fontVariantNumeric: 'tabular-nums', transform: `scale(${done ? 1 + (1 - pop(frame, 100, fps, 260)) * 0.15 : 1})`, transformOrigin: '0 100%'}}>{secs}</span>
        <span style={{fontFamily: PIXEL, fontSize: 120, color: WHITE}}>秒</span>
        <span style={{fontFamily: CONSOLE, fontSize: 120, color: '#4A5040', textDecoration: 'line-through', opacity: done ? 1 : 0}}>170</span>
      </div>
      {/* the bar shortens with it */}
      <div style={{position: 'absolute', left: 170, top: 780, height: 34, width: 1580 * (secs / 170), background: done ? LIME : WHITE}} />
      <div style={{position: 'absolute', left: 170, top: 780, height: 34, width: 1580, border: '2px solid #3A3F2C', boxSizing: 'border-box'}} />
      <Caption mark="//" markColor={BLUE} text="文字识别提速，导入快一倍多" at={112} style={{position: 'absolute', left: 170, top: 850}} />
      <Glyphs count={10} seed={65} />
    </Fill>
  );
};

// ---------------------------------------------------------------- symbol flood
const Flood: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const paint = useCallback((c: number, r: number, tick: number, cols: number) => {
    const band = Math.floor(r / 3);
    const dir = band % 2 ? 1 : -1;
    const speed = 3 + (band % 3) * 2;
    const x = (c + dir * tick * speed + cols * 10) % 40;
    const cover = clamp01(frame / 18) * 40; // bands fill in
    if (x > cover * (0.5 + hash(band) * 0.5)) return null;
    return [BLUE, LIME, WHITE, OLIVE][band % 4];
  }, [frame]);
  const k = pop(frame, 14, fps, 220);
  return (
    <Fill>
      <Sfx name="glitch" volume={0.4} />
      <CharField cell={30} set={'<>+*|◆'} fps={24} paint={paint} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{fontFamily: PIXEL, fontSize: 120, color: WHITE, background: BG, padding: '14px 48px', display: 'flex', gap: 36, alignItems: 'center',
          transform: `scale(${k})`}}>
          <span>画面</span><span style={{fontFamily: SILK, fontWeight: 700, color: LIME}}>+</span><span>原声</span><span style={{fontFamily: SILK, fontWeight: 700, color: LIME}}>+</span><span>文字</span>
        </div>
      </AbsoluteFill>
      <Glyphs count={6} seed={71} />
    </Fill>
  );
};

// ---------------------------------------------------------------- the snake in digits
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
  const {fps} = useVideoConfig();
  const grid = useImageGrid('mascot.png', 104, 64);
  const reveal = easeOut(frame / 40);
  const at = useCallback((c: number, r: number, tick: number) => {
    if (!grid) return 0;
    const wave = Math.round(Math.sin(tick * 0.5 + r * 0.25) * 0.8); // the body breathes, row by row
    return grid[r - 2]?.[c - 6 - wave] ?? 0;
  }, [grid]);
  const paint = useCallback((c: number, r: number, tick: number) => {
    const cell = at(c, r, tick);
    if (!cell) return hash(c, r) < 0.02 && hash(c, r, tick) < 0.5 ? '#1F2318' : null;
    if (cell >= 3 || hash(c, r, 5) > reveal) return null; // the eyes are drawn solid, below
    return cell === 2 ? '#C9CFB6' : hash(c, r, tick) < 0.85 ? '#8A9178' : '#5E6552';
  }, [at, reveal]);
  // The eyes in solid blocks, opening once the body is drawn.
  const eyes = useCallback((c: number, r: number, tick: number) => {
    const cell = at(c, r, tick);
    if (cell < 3 || frame < 34) return null;
    const blink = frame % 130 > 121; // a blink now and then
    return blink ? null : cell === 3 ? WHITE : LIME;
  }, [at, frame]);
  return (
    <Fill>
      <Sfx name="soft" at={34} volume={0.5} />
      <CharField cell={16} set="digits" fps={12} paint={paint} />
      <CharField cell={16} set="█" fps={12} paint={eyes} />
      <div style={{position: 'absolute', left: 1080, top: 330, display: 'flex', flexDirection: 'column', gap: 30}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 132, color: WHITE, lineHeight: 1, display: 'flex', gap: 26, alignItems: 'center',
          clipPath: `inset(0 ${(1 - easeOut((frame - 36) / 14)) * 100}% 0 0)`}}>
          <span style={{fontFamily: MONO, color: LIME}}>*</span>视频理解<span style={{fontFamily: MONO, color: BLUE}}>{'>>'}</span>
        </div>
        <div style={{fontFamily: PIXEL, fontSize: 48, color: MUTED}}>
          <Typed text="小蛇陪你一帧一帧看完" at={60} />
        </div>
        <div style={{display: 'flex', gap: 16}}>
          {['软件教程', '课程', '科普'].map((w, i) => (
            <React.Fragment key={w}>
              <Sfx name="pop" at={120 + i * 8} volume={0.3} />
              <Label color={i === 0 ? LIME : '#262A1E'} ink={i === 0 ? BG : WHITE} style={{fontFamily: PIXEL, fontSize: 48, padding: '6px 14px',
                transform: `scale(${pop(frame, 120 + i * 8, fps, 260)})`, display: 'inline-block'}}>{w}</Label>
            </React.Fragment>
          ))}
        </div>
      </div>
      <Glyphs count={10} seed={81} />
    </Fill>
  );
};

// ---------------------------------------------------------------- the wall, then the list
const WALL = ['B站', '抖音', '小红书', '快手', '视频号', '本地上传', '截图提问', '慢放回看', '笔记长图', '证据标签', '原声转写', '画面文字',
  '关键帧', '时间轴', '卡点分析', '推荐问题', 'Tab 补全', '手机适配', '附图提问', '导出预览'];
const LIST = ['B站 · 抖音 · 小红书 · 快手 · 视频号', '本地上传，一样能看', '截图提问：我卡在哪一步', '慢放回看，逐帧对照', '笔记一键存成长图'];
const COLLAPSE_AT = 130;

const Wall: React.FC = () => {
  const frame = useCurrentFrame();
  const collapse = easeOut((frame - COLLAPSE_AT) / 24);
  const cols = 5;
  return (
    <Fill>
      <Sfx name="swish" at={COLLAPSE_AT - 16} volume={0.35} />
      <div style={{position: 'absolute', inset: 0, opacity: 1 - collapse * 0.85}}>
        {Array.from({length: 9 * cols}, (_, i) => {
          const col = i % cols;
          const row = Math.floor(i / cols);
          const word = WALL[(i * 7 + row) % WALL.length];
          const speed = col % 2 ? 7 : 4.5; // columns scroll at two speeds, in opposite directions
          const y = (((row * 140 + (col % 2 ? -1 : 1) * frame * speed) % 1260) + 1260) % 1260 - 140;
          const lit = hash(i, Math.floor(frame / 8)) < 0.12;
          return (
            <div key={i} style={{position: 'absolute', left: 60 + col * 370, top: y, width: 340, fontFamily: PIXEL, fontSize: 72, whiteSpace: 'nowrap',
              color: lit ? BG : '#3F4435', background: lit ? LIME : 'transparent', padding: '0 10px',
              transform: `translateY(${collapse * (540 - y) * 0.6}px) scale(${1 - collapse * 0.4})`}}>{word}</div>
          );
        })}
      </div>
      <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 300, gap: 22}}>
        {LIST.map((line, i) => {
          const at = COLLAPSE_AT + 22 + i * 16;
          const on = frame >= at;
          const current = Math.min(LIST.length - 1, Math.floor((frame - COLLAPSE_AT - 22) / 16)) === i;
          return (
            <div key={i} style={{display: 'flex', gap: 28, alignItems: 'center', opacity: on ? 1 : 0, transform: `translateX(${(1 - easeOut((frame - at) / 8)) * -80}px)`}}>
              <Sfx name="soft" at={at} volume={0.45} />
              <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 48, color: current ? LIME : BLUE, width: 60}}>◆</span>
              <span style={{fontFamily: PIXEL, fontSize: 84, color: current ? BG : WHITE, background: current ? LIME : BG, padding: '0 18px', lineHeight: 1.2}}>{line}</span>
            </div>
          );
        })}
      </AbsoluteFill>
      <Glyphs count={10} seed={91} />
    </Fill>
  );
};

// ---------------------------------------------------------------- slogan, folding into the lockup
const Mark: React.FC<{size: number}> = ({size}) => (
  <svg width={size} height={size * 48 / 44} viewBox="14 8 44 48">
    <path fill={WHITE} d="M38.5 12.5c8.7 0 14.5 4.7 14.5 11.2 0 5.8-4.9 9.3-11.5 10.7-5.3 1.1-8.6 3.5-8.6 7.2 0 4.6 4.9 7.6 10.4 9.2-8.4 3.3-17.5.4-21.4-5.7-5.2-8.2-1.1-17.7 8.8-21.4 3.2-1.2 5.3-2.6 5.3-5.6 0-3.6 2.7-6.1 6.5-6.1Z" />
    <ellipse cx="37" cy="22.5" rx="3.8" ry="5.8" fill={BG} />
    <circle cx="46" cy="20" r="3.2" fill={LIME} />
  </svg>
);

const FOLD_AT = 250; // the slogan folds into a line…
const LOCK_AT = 290; // …and the lockup rises out of it
const LINE_Y = 640;

const Finale: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const a = pop(frame, 0, fps, 200);
  const b = pop(frame, 26, fps, 200);
  const c = pop(frame, 80, fps);
  const fold = easeOut((frame - FOLD_AT) / 20);
  const squash = (y: number) => `translateY(${(LINE_Y - y) * fold}px) scaleY(${1 - fold})`;
  const t = frame - LOCK_AT;
  const rise = easeOut(t / 24);
  const out = clamp01((frame - (durationInFrames - 36)) / 36); // fade to black at the very end
  const mask = useMemo(() => textMask('帧寻', Math.ceil(1920 / (26 * 0.62)), Math.ceil(1080 / 26), SC, 0.62), []);
  const dots = useCallback((col: number, r: number, tick: number) => {
    if (mask[r]?.[col]) return null;
    return hash(col, r) < 0.05 ? (hash(col, r, tick) < 0.5 ? '#23271B' : '#1E2336') : null;
  }, [mask]);
  const steps = stepped(frame, 60, 12);
  const line = easeOut((frame - FOLD_AT - 6) / 18);
  return (
    <Fill>
      <Sfx name="hit" volume={0.35} />
      <Sfx name="hit" at={26} volume={0.35} />
      <Sfx name="riser" at={LOCK_AT - 170} startFrom={Math.round(7 * fps)} volume={0.25} />
      <Sfx name="whoosh" at={FOLD_AT} volume={0.5} rate={0.9} />
      <Sfx name="swell" at={LOCK_AT - 10} volume={0.45} />
      {frame >= LOCK_AT ? <CharField cell={26} set="marks" fps={8} paint={dots} /> : null}
      {frame < LOCK_AT ? (
        <>
          <div style={{position: 'absolute', left: 110, top: 120, fontFamily: SC, fontWeight: 900, fontSize: 280, color: WHITE, lineHeight: 1,
            transform: `translateX(${(1 - a) * -700}px) ${squash(260)}`}}>
            <span style={{fontFamily: MONO, color: BLUE}}>*//</span>看见
          </div>
          <div style={{position: 'absolute', right: 110, top: 420, fontFamily: SC, fontWeight: 900, fontSize: 280, color: LIME, lineHeight: 1, opacity: frame >= 26 ? 1 : 0,
            transform: `translateX(${(1 - b) * 700}px) ${squash(560)}`}}>再求证</div>
          <div style={{position: 'absolute', left: 300, top: 470, fontFamily: MONO, fontWeight: 800, fontSize: 240, color: BLUE, lineHeight: 1, opacity: frame > 50 ? 1 : 0,
            transform: `rotate(${(frame - 50) * 3}deg) scale(${pop(frame, 50, fps) * (1 - fold)})`}}>+</div>
          <div style={{position: 'absolute', left: 0, right: 0, bottom: 110, display: 'flex', justifyContent: 'center', opacity: frame >= 80 ? 1 : 0,
            transform: `translateY(${(1 - c) * 60}px) ${squash(930)}`}}>
            <div style={{fontFamily: SILK, fontWeight: 700, fontSize: 72, color: LIME, display: 'flex', gap: 24, alignItems: 'center'}}>
              {'{'}<Typed text="回到原片那一刻" at={86} style={{fontFamily: PIXEL, fontSize: 84, color: WHITE}} />{'}>'}
            </div>
          </div>
        </>
      ) : null}
      {/* the line everything folds into; the lockup rises from it */}
      {frame >= FOLD_AT ? <div style={{position: 'absolute', top: LINE_Y - 3, height: 6, background: LIME, left: 960 - 620 * line, width: 1240 * line}} /> : null}
      {frame >= LOCK_AT ? (
        <>
          <div style={{position: 'absolute', left: 0, right: 0, top: LINE_Y - 330, height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 50, transform: `translateY(${(1 - rise) * 330}px)`}}>
              <div style={{transform: `scale(${pop(t, 10, fps)})`}}><Mark size={190} /></div>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: 230, color: WHITE, lineHeight: 1}}>帧寻</span>
              <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 124, color: WHITE, letterSpacing: -5, lineHeight: 1}}>
                GongJ<span style={{color: LIME}}>!</span>ng<span style={{color: LIME}}>{steps % 10 < 7 ? '?' : '!'}</span>
              </span>
            </div>
          </div>
          <div style={{position: 'absolute', left: 0, right: 0, top: LINE_Y + 40, display: 'flex', justifyContent: 'center', gap: 40, alignItems: 'center'}}>
            <span style={{fontFamily: PIXEL, fontSize: 60, color: WHITE}}><Typed text="看见，再求证。" at={LOCK_AT + 30} cps={20} /></span>
            <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 48, color: DIM, opacity: t > 60 ? 1 : 0}}>|||</span>
            <span style={{fontFamily: DISPLAY, fontWeight: 700, fontSize: 44, color: LIME}}><Typed text="linyi.work/ZhenXun" at={LOCK_AT + 66} cps={34} caret={WHITE} /></span>
          </div>
        </>
      ) : null}
      <Glyphs count={frame >= LOCK_AT ? 16 : 12} seed={101} opacity={0.85} />
      <AbsoluteFill style={{background: BG, opacity: out}} />
    </Fill>
  );
};

export const REST = {Evidence, Clicks, Screenshot, Giant, Burst, Versus, Speed, Flood, Snake, Wall, Finale};
