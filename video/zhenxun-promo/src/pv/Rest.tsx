import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {BG, BLUE, CharField, clamp01, DIM, easeOut, Fill, Glyphs, hash, LIME, MONO, PixelCursor, SC, stepped, Typed, WHITE, WORDMARK} from './kit';
import {textMask} from './Opening';

// The PV after the name (10–60 s), scene by scene, hard cuts between them and no flashes:
//   10–15  三路证据: three columns of characters rise — 画面 / 原声 / 画面文字
//   15–20  a pixel hand clicks; each click pops a timecode and a word block (卡点 / 回看 / 证据 / ///)
//   20–24  giant cropped type: 每秒 / 读一帧 / + / 证据 >
//   24–29  a burst of lime stars over a 帧 texture: 看到哪，问到哪
//   29–33  猜 struck out, 证据 > instead
//   33–36  bands of symbols flood past
//   36–42  the snake drawn in digits: * 视频理解 >>
//   42–49  a wall of platforms and features, then the list it comes down to
//   49–54  the slogan: *//看见 再求证 + { 回到原片那一刻 }>
//   54–60  the lockup: snake, 帧寻 GongJ!ng?, the address

const OLIVE = '#7E8C3C';
const MUTED = '#8B9171';

const Label: React.FC<{children: React.ReactNode; color?: string; ink?: string; style?: React.CSSProperties}> = ({children, color = LIME, ink = BG, style}) => (
  <span style={{fontFamily: MONO, fontWeight: 800, background: color, color: ink, padding: '2px 12px', ...style}}>{children}</span>
);

/** Slides in from `from` px in 12-step judder, starting at `at`. */
const useJudder = (at: number, frames = 14) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = clamp01((stepped(frame - at, fps, 15) * (fps / 15)) / frames);
  return {k: easeOut(k), on: frame >= at};
};

// ---------------------------------------------------------------- 10–15 三路证据
const LANES = [
  {word: '画面', mark: '◆', color: BLUE},
  {word: '原声', mark: '|||', color: LIME},
  {word: '画面文字', mark: '[ ]', color: WHITE},
];

const Evidence: React.FC = () => {
  const frame = useCurrentFrame();
  const paint = useCallback((c: number, r: number, tick: number, cols: number, rows: number) => {
    const lane = Math.floor((c / cols) * 3);
    const inLane = c % Math.floor(cols / 3) > 4 && c % Math.floor(cols / 3) < Math.floor(cols / 3) - 4;
    if (!inLane) return null;
    const level = easeOut((frame - 10 - lane * 30) / 70) * 0.62 + Math.sin(tick * 0.7 + c * 0.9) * 0.02 + hash(c, tick) * 0.04;
    const fromBottom = 1 - r / rows;
    if (fromBottom > level) return hash(c, r, tick) < 0.02 ? DIM : null;
    return hash(c, r, tick) < 0.75 ? LANES[lane].color : DIM;
  }, [frame]);
  return (
    <Fill>
      <CharField cell={20} set="code" fps={15} paint={paint} style={{opacity: 0.85}} />
      <AbsoluteFill style={{flexDirection: 'row'}}>
        {LANES.map((lane, i) => {
          const at = 18 + i * 30;
          const k = easeOut((frame - at) / 16);
          return (
            <div key={i} style={{flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 150, gap: 18, opacity: frame >= at ? 1 : 0}}>
              <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 44, color: lane.color}}>{lane.mark}</span>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: lane.word.length > 2 ? 120 : 150, color: WHITE, lineHeight: 1.25, whiteSpace: 'nowrap', background: BG, padding: '0 22px',
                clipPath: `inset(0 ${(1 - k) * 100}% 0 0)`}}>{lane.word}</span>
            </div>
          );
        })}
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 120, display: 'flex', justifyContent: 'center'}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 64, color: WHITE, background: BG, padding: '6px 26px', display: 'flex', gap: 24, alignItems: 'center'}}>
          <span style={{fontFamily: MONO, color: LIME}}>{'>>>'}</span>
          <Typed text="每一句回答，都有出处" at={150} cps={16} />
        </div>
      </div>
      <Glyphs count={10} seed={21} opacity={0.8} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 15–20 clicks pop timecodes
const CLICKS = [
  {x: 420, y: 330, tc: '01:12.4', word: '卡点', color: LIME},
  {x: 1180, y: 250, tc: '03:05.0', word: '回看', color: BLUE},
  {x: 760, y: 640, tc: '04:47.8', word: '证据', color: WHITE},
  {x: 1460, y: 620, tc: '06:30.2', word: '///', color: LIME},
];

const Clicks: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const at = (i: number) => 34 + i * 52;
  // The hand glides from target to target (eased), presses on arrival.
  const leg = Math.min(CLICKS.length - 1, Math.max(0, Math.floor((frame - 10) / 52)));
  const from = leg === 0 ? {x: 960, y: 1000} : CLICKS[leg - 1];
  const to = CLICKS[leg];
  const k = easeOut((frame - (at(leg) - 24)) / 22);
  const hx = from.x + (to.x - from.x) * k;
  const hy = from.y + (to.y - from.y) * k;
  const press = clamp01(1 - Math.abs(frame - at(leg)) / 5);
  const grid = useCallback((c: number, r: number) => (c % 8 === 0 && r % 4 === 0 ? '#22261A' : null), []);
  return (
    <Fill>
      <CharField cell={22} set="marks" fps={6} paint={grid} />
      {CLICKS.map((click, i) => {
        if (frame < at(i)) return null;
        const t = frame - at(i);
        const pop = stepped(t, fps, 15) < 1 ? 1.25 : 1; // one judder frame big, then settle
        const ring = clamp01(t / 26);
        return (
          <React.Fragment key={i}>
            {ring < 1 ? Array.from({length: 8}, (_, j) => {
              const a = (j / 8) * Math.PI * 2;
              const d = 30 + easeOut(ring) * 120;
              return <span key={j} style={{position: 'absolute', left: click.x + Math.cos(a) * d - 14, top: click.y + Math.sin(a) * d - 20, fontFamily: MONO,
                fontWeight: 800, fontSize: 34, color: LIME, opacity: 1 - ring, transform: `rotate(${t * 9}deg)`}}>+</span>;
            }) : null}
            <div style={{position: 'absolute', left: click.x + 40, top: click.y - 120, transform: `scale(${pop})`, transformOrigin: '0 100%',
              display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-start'}}>
              <Label style={{fontSize: 46}}>{click.tc}</Label>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: 92, color: click.color === WHITE ? BG : BG, background: click.color, padding: '0 18px', lineHeight: 1.15,
                transform: `translateX(${(1 - easeOut((t - 4) / 12)) * -60}px)`, opacity: t > 3 ? 1 : 0}}>{click.word}</span>
            </div>
          </React.Fragment>
        );
      })}
      <PixelCursor x={hx} y={hy} hand size={7} press={press} />
      <div style={{position: 'absolute', left: 92, bottom: 80, fontFamily: SC, fontWeight: 900, fontSize: 58, color: WHITE, display: 'flex', gap: 22}}>
        <span style={{fontFamily: MONO, color: BLUE}}>//</span>
        <Typed text="点一下，就跳到那一秒" at={210} cps={16} />
      </div>
      <Glyphs count={8} seed={31} opacity={0.75} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 20–24 giant cropped type
const Giant: React.FC = () => {
  const frame = useCurrentFrame();
  const card = Math.min(3, Math.floor(frame / 60));
  const t = frame - card * 60;
  const {k} = useJudder(card * 60, 10);
  if (card === 0) {
    return (
      <Fill>
        <div style={{position: 'absolute', left: -60 + (1 - k) * -500, top: -170, fontFamily: SC, fontWeight: 900, fontSize: 760, color: WHITE, lineHeight: 1, whiteSpace: 'nowrap'}}>每秒</div>
        <div style={{position: 'absolute', right: 90, bottom: 90}}><Label style={{fontSize: 54}}>{'>>> 01'}</Label></div>
        <Glyphs count={6} seed={41} />
      </Fill>
    );
  }
  if (card === 1) {
    return (
      <Fill>
        <div style={{position: 'absolute', inset: 0, background: BLUE, clipPath: `inset(0 0 0 ${(1 - k) * 100}%)`}} />
        <div style={{position: 'absolute', right: -140 + (1 - k) * -400, top: 120, fontFamily: SC, fontWeight: 900, fontSize: 640, color: WHITE, lineHeight: 1, whiteSpace: 'nowrap'}}>读一帧</div>
        <div style={{position: 'absolute', left: 90, top: 90, fontFamily: MONO, fontWeight: 800, fontSize: 60, color: BG}}>|||</div>
        <Glyphs count={6} seed={42} />
      </Fill>
    );
  }
  if (card === 2) {
    return (
      <Fill>
        <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontFamily: MONO, fontWeight: 800, fontSize: 1100, color: LIME, lineHeight: 0.7, transform: `rotate(${stepped(t, 60, 12) * 7.5}deg) scale(${0.4 + k * 0.6})`}}>+</div>
        </AbsoluteFill>
        <Glyphs count={10} seed={43} />
      </Fill>
    );
  }
  return (
    <Fill>
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: '68%', background: LIME, clipPath: `inset(0 ${(1 - k) * 100}% 0 0)`}} />
      <div style={{position: 'absolute', left: 60, top: 140, fontFamily: SC, fontWeight: 900, fontSize: 600, color: BG, lineHeight: 1, whiteSpace: 'nowrap',
        transform: `translateX(${(1 - k) * -300}px)`}}>证据<span style={{fontFamily: MONO, color: BLUE}}>{' >'}</span></div>
      <Glyphs count={6} seed={44} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 24–29 star burst, 看到哪，问到哪
const Burst: React.FC = () => {
  const frame = useCurrentFrame();
  const texture = useCallback((c: number, r: number, tick: number, cols: number) => {
    const dir = r % 2 ? 1 : -1;
    const shifted = (c + dir * tick + cols * 4) % 11;
    if (shifted > 7) return null;
    return hash(r, 3) < 0.3 ? '#2E3423' : '#1D2116';
  }, []);
  const bursts = [8, 120];
  return (
    <Fill>
      <CharField cell={46} set="帧" fps={10} paint={texture} />
      {bursts.flatMap((start, b) => frame < start ? [] : Array.from({length: 70}, (_, i) => {
        const t = (frame - start) / 60;
        const a = hash(i, b, 1) * Math.PI * 2;
        const speed = 300 + hash(i, b, 2) * 900;
        const d = speed * (1 - Math.exp(-2.4 * t));
        const fade = clamp01(1.6 - t * 0.7);
        const size = 26 + hash(i, b, 3) * 70;
        return (
          <span key={`${b}-${i}`} style={{position: 'absolute', left: 960 + Math.cos(a) * d * 1.3, top: 540 + Math.sin(a) * d * 0.8, fontFamily: MONO, fontWeight: 800,
            fontSize: size, color: hash(i, b, 4) < 0.8 ? LIME : WHITE, opacity: fade, lineHeight: 1,
            transform: `translate(-50%, -50%) rotate(${t * (hash(i, b, 5) - 0.5) * 900}deg)`}}>*</span>
        );
      }))}
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 26}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 168, color: WHITE, background: BG, padding: '4px 40px', lineHeight: 1.1,
          clipPath: `inset(0 ${(1 - easeOut((frame - 20) / 22)) * 100}% 0 0)`}}>看到哪，问到哪</div>
        <div style={{fontFamily: MONO, fontWeight: 800, fontSize: 44, color: LIME, background: BG, padding: '2px 16px', opacity: frame > 60 ? 1 : 0}}>
          {'<<< '}<span style={{fontFamily: SC, color: WHITE}}>{frame > 60 ? '视频暂停在哪一秒，就问那一秒' .slice(0, Math.floor((frame - 60) / 3.5)) : ''}</span>{' >>>'}
        </div>
      </AbsoluteFill>
      <Glyphs count={10} seed={51} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 29–33 猜 vs 证据
const Versus: React.FC = () => {
  const frame = useCurrentFrame();
  const strike = easeOut((frame - 40) / 14);
  const right = useJudder(70, 12);
  return (
    <Fill>
      <AbsoluteFill style={{flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 70, paddingBottom: 120}}>
        <div style={{position: 'relative', fontFamily: SC, fontWeight: 900, fontSize: 380, color: frame > 46 ? '#3A3D33' : WHITE, lineHeight: 1}}>
          猜
          <div style={{position: 'absolute', left: -30, right: -30, top: '52%', height: 26, background: LIME, transform: `scaleX(${strike}) rotate(-8deg)`, transformOrigin: '0 50%'}} />
        </div>
        <div style={{fontFamily: MONO, fontWeight: 800, fontSize: 200, color: BLUE, transform: `rotate(${frame * 3}deg)`, lineHeight: 1}}>×</div>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 300, color: LIME, lineHeight: 1, opacity: right.on ? 1 : 0, transform: `translateX(${(1 - right.k) * 200}px)`}}>
          证据<span style={{fontFamily: MONO, color: WHITE}}>{' >'}</span>
        </div>
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 150, textAlign: 'center', fontFamily: SC, fontWeight: 900, fontSize: 56, color: WHITE}}>
        <Typed text="不靠猜：每个结论标着时间和出处" at={100} cps={18} />
      </div>
      <Glyphs count={10} seed={61} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 33–36 symbol flood
const Flood: React.FC = () => {
  const frame = useCurrentFrame();
  const paint = useCallback((c: number, r: number, tick: number, cols: number, rows: number) => {
    const band = Math.floor(r / 3);
    const dir = band % 2 ? 1 : -1;
    const speed = 2 + (band % 3) * 2;
    const x = (c + dir * tick * speed + cols * 10) % 40;
    const cover = clamp01(frame / 30) * 40; // bands fill in
    if (x > cover * (0.5 + hash(band) * 0.5)) return null;
    return [BLUE, LIME, WHITE, OLIVE][band % 4];
  }, [frame]);
  return (
    <Fill>
      <CharField cell={30} set={'<>+*|◆'} fps={20} paint={paint} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 110, color: WHITE, background: BG, padding: '10px 48px', display: 'flex', gap: 36, alignItems: 'center'}}>
          <span>画面</span><span style={{fontFamily: MONO, color: LIME}}>+</span><span>原声</span><span style={{fontFamily: MONO, color: LIME}}>+</span><span>文字</span>
        </div>
      </AbsoluteFill>
      <Glyphs count={6} seed={71} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 36–42 the snake in digits
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
  const grid = useImageGrid('mascot.png', 104, 64);
  const reveal = easeOut(frame / 80);
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
    if (cell < 3 || frame < 50) return null;
    const blink = frame % 150 > 140; // a blink now and then
    return blink ? null : cell === 3 ? WHITE : LIME;
  }, [at, frame]);
  return (
    <Fill>
      <CharField cell={16} set="digits" fps={12} paint={paint} />
      <CharField cell={16} set="█" fps={12} paint={eyes} />
      <div style={{position: 'absolute', left: 1080, top: 330, display: 'flex', flexDirection: 'column', gap: 30}}>
        <div style={{fontFamily: SC, fontWeight: 900, fontSize: 132, color: WHITE, lineHeight: 1, display: 'flex', gap: 26, alignItems: 'center',
          clipPath: `inset(0 ${(1 - easeOut((frame - 60) / 20)) * 100}% 0 0)`}}>
          <span style={{fontFamily: MONO, color: LIME}}>*</span>视频理解<span style={{fontFamily: MONO, color: BLUE}}>{'>>'}</span>
        </div>
        <div style={{fontFamily: SC, fontWeight: 500, fontSize: 46, color: MUTED}}>
          <Typed text="小蛇陪你一帧一帧看完" at={110} cps={14} />
        </div>
        <div style={{display: 'flex', gap: 16, opacity: frame > 200 ? 1 : 0}}>
          {['软件教程', '课程', '科普'].map((w, i) => (
            <Label key={w} color={i === 0 ? LIME : '#262A1E'} ink={i === 0 ? BG : WHITE} style={{fontFamily: SC, fontWeight: 900, fontSize: 40,
              opacity: frame > 200 + i * 10 ? 1 : 0}}>{w}</Label>
          ))}
        </div>
      </div>
      <Glyphs count={10} seed={81} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 42–49 the wall, then the list
const WALL = ['B站', '抖音', '小红书', '快手', '视频号', '本地上传', '截图提问', '慢放回看', '笔记长图', '证据标签', '原声转写', '画面文字',
  '关键帧', '时间轴', '卡点分析', '推荐问题', 'Tab 补全', '手机适配', '附图提问', '导出预览'];
const LIST = ['B站 · 抖音 · 小红书 · 快手 · 视频号', '本地上传，一样能看', '截图提问：我卡在哪一步', '慢放回看，逐帧对照', '笔记一键存成长图'];

const Wall: React.FC = () => {
  const frame = useCurrentFrame();
  const collapse = easeOut((frame - 200) / 30);
  const scroll = frame * 1.6;
  const cols = 5;
  return (
    <Fill>
      <div style={{position: 'absolute', inset: 0, opacity: 1 - collapse * 0.85}}>
        {Array.from({length: 9 * cols}, (_, i) => {
          const col = i % cols;
          const row = Math.floor(i / cols);
          const word = WALL[(i * 7 + row) % WALL.length];
          const y = ((row * 140 - scroll * (col % 2 ? 1 : 0.7)) % 1260 + 1260) % 1260 - 140;
          const lit = hash(i, Math.floor(frame / 12)) < 0.12;
          return (
            <div key={i} style={{position: 'absolute', left: 60 + col * 370, top: y, width: 340, fontFamily: SC, fontWeight: 900, fontSize: 64, whiteSpace: 'nowrap',
              color: lit ? BG : '#3F4435', background: lit ? LIME : 'transparent', padding: '0 10px',
              transform: `translateY(${collapse * (540 - y) * 0.6}px) scale(${1 - collapse * 0.4})`}}>{word}</div>
          );
        })}
      </div>
      <AbsoluteFill style={{justifyContent: 'center', paddingLeft: 300, gap: 22}}>
        {LIST.map((line, i) => {
          const at = 225 + i * 22;
          const on = frame >= at;
          const current = Math.floor((frame - 225) / 22) === i || (i === LIST.length - 1 && frame >= 225 + LIST.length * 22);
          return (
            <div key={i} style={{display: 'flex', gap: 28, alignItems: 'center', opacity: on ? 1 : 0, transform: `translateX(${(1 - easeOut((frame - at) / 10)) * -80}px)`}}>
              <span style={{fontFamily: MONO, fontWeight: 800, fontSize: 48, color: current ? LIME : BLUE, width: 60}}>◆</span>
              <span style={{fontFamily: SC, fontWeight: 900, fontSize: 74, color: current ? BG : WHITE, background: current ? LIME : BG, padding: '0 18px'}}>{line}</span>
            </div>
          );
        })}
      </AbsoluteFill>
      <Glyphs count={10} seed={91} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 49–54 the slogan
const Slogan: React.FC = () => {
  const frame = useCurrentFrame();
  const a = useJudder(0, 12);
  const b = useJudder(36, 12);
  const c = useJudder(130, 12);
  return (
    <Fill>
      <div style={{position: 'absolute', left: 110, top: 120, fontFamily: SC, fontWeight: 900, fontSize: 280, color: WHITE, lineHeight: 1,
        transform: `translateX(${(1 - a.k) * -400}px)`}}>
        <span style={{fontFamily: MONO, color: BLUE}}>*//</span>看见
      </div>
      <div style={{position: 'absolute', right: 110, top: 420, fontFamily: SC, fontWeight: 900, fontSize: 280, color: LIME, lineHeight: 1, opacity: b.on ? 1 : 0,
        transform: `translateX(${(1 - b.k) * 400}px)`}}>再求证</div>
      <div style={{position: 'absolute', left: 300, top: 470, fontFamily: MONO, fontWeight: 800, fontSize: 240, color: BLUE, lineHeight: 1, opacity: frame > 80 ? 1 : 0,
        transform: `rotate(${(frame - 80) * 2.5}deg)`}}>+</div>
      <div style={{position: 'absolute', left: 0, right: 0, bottom: 110, display: 'flex', justifyContent: 'center', opacity: c.on ? 1 : 0, transform: `translateY(${(1 - c.k) * 60}px)`}}>
        <div style={{fontFamily: MONO, fontWeight: 800, fontSize: 76, color: LIME, display: 'flex', gap: 24, alignItems: 'center'}}>
          {'{'}<span style={{fontFamily: SC, fontWeight: 900, color: WHITE}}>回到原片那一刻</span>{'}>'}
        </div>
      </div>
      <Glyphs count={12} seed={101} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 54–60 lockup
const Mark: React.FC<{size: number}> = ({size}) => (
  <svg width={size} height={size * 48 / 44} viewBox="14 8 44 48">
    <path fill={WHITE} d="M38.5 12.5c8.7 0 14.5 4.7 14.5 11.2 0 5.8-4.9 9.3-11.5 10.7-5.3 1.1-8.6 3.5-8.6 7.2 0 4.6 4.9 7.6 10.4 9.2-8.4 3.3-17.5.4-21.4-5.7-5.2-8.2-1.1-17.7 8.8-21.4 3.2-1.2 5.3-2.6 5.3-5.6 0-3.6 2.7-6.1 6.5-6.1Z" />
    <ellipse cx="37" cy="22.5" rx="3.8" ry="5.8" fill={BG} />
    <circle cx="46" cy="20" r="3.2" fill={LIME} />
  </svg>
);

const Lockup: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = stepped(frame, 60, 12);
  const a = easeOut(frame / 20);
  const b = easeOut((frame - 12) / 20);
  const out = clamp01((frame - (360 - 36)) / 36); // fade to black at the very end
  const mask = useMemo(() => textMask('帧寻', Math.ceil(1920 / (26 * 0.62)), Math.ceil(1080 / 26), SC, 0.7), []);
  const dots = useCallback((c: number, r: number, tick: number) => {
    if (mask[r]?.[c]) return null;
    return hash(c, r) < 0.05 ? (hash(c, r, tick) < 0.5 ? '#23271B' : '#1E2336') : null;
  }, [mask]);
  return (
    <Fill>
      <CharField cell={26} set="marks" fps={8} paint={dots} />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 34}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 50}}>
          <div style={{transform: `scale(${0.6 + a * 0.4})`, opacity: a}}><Mark size={190} /></div>
          <span style={{fontFamily: SC, fontWeight: 900, fontSize: 230, color: WHITE, lineHeight: 1, clipPath: `inset(0 ${(1 - a) * 100}% 0 0)`}}>帧寻</span>
          <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 124, color: WHITE, letterSpacing: -5, lineHeight: 1, clipPath: `inset(${(1 - b) * 100}% 0 0 0)`}}>
            GongJ<span style={{color: LIME}}>!</span>ng<span style={{color: LIME}}>{steps % 10 < 7 ? '?' : '!'}</span>
          </span>
        </div>
        <div style={{width: 1240, height: 6, background: LIME, transform: `scaleX(${easeOut((frame - 20) / 22)})`, transformOrigin: '0 50%'}} />
        <div style={{display: 'flex', gap: 40, alignItems: 'center', fontFamily: MONO, fontWeight: 800, fontSize: 50}}>
          <span style={{fontFamily: SC, fontWeight: 900, color: WHITE}}><Typed text="看见，再求证。" at={34} cps={14} /></span>
          <span style={{color: DIM}}>|||</span>
          <span style={{color: LIME}}><Typed text="linyi.work/ZhenXun" at={80} cps={30} caret={WHITE} /></span>
        </div>
      </AbsoluteFill>
      <Glyphs count={16} seed={111} opacity={0.85} />
      <AbsoluteFill style={{background: BG, opacity: out}} />
    </Fill>
  );
};

// ---------------------------------------------------------------- 10–60 s
export const SCENES: [React.FC, number][] = [
  [Evidence, 300], [Clicks, 300], [Giant, 240], [Burst, 300], [Versus, 240],
  [Flood, 180], [Snake, 360], [Wall, 420], [Slogan, 300], [Lockup, 360],
];
export const REST_FRAMES = SCENES.reduce((n, [, d]) => n + d, 0);

export const Rest: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{background: BG}}>
      {SCENES.map(([Scene, d], i) => {
        const seq = <Sequence key={i} from={from} durationInFrames={d}><Scene /></Sequence>;
        from += d;
        return seq;
      })}
    </AbsoluteFill>
  );
};
