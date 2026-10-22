import React from 'react';
import {AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import askRec from '../../public/rec/ask.json';
import docsRec from '../../public/rec/docs.json';
import evidenceRec from '../../public/rec/evidence.json';
import gifRec from '../../public/rec/gif.json';
import historyRec from '../../public/rec/history.json';
import homeRec from '../../public/rec/home.json';
import importRec from '../../public/rec/import.json';
import notesRec from '../../public/rec/notes.json';
import phoneRec from '../../public/rec/phone.json';
import profileRec from '../../public/rec/profile.json';
import replayRec from '../../public/rec/replay.json';
import shotRec from '../../public/rec/screenshot.json';
import tabRec from '../../public/rec/tab.json';
import timelineRec from '../../public/rec/timeline.json';
import {Key, Track} from '../camera';
import {Shot} from '../Shot';
import {Contour} from '../pv/Contour';
import {clamp01, CONSOLE, DISPLAY, easeOut, Fill, INK, INK2, INK3, LIME, LINE, LINE2, PAPER, PIXEL, SC, Sfx, SILK, stepped, Typed, WORDMARK} from '../pv/kit';
import {Sculpture} from '../pv/Sculpture';
import {follow, markAt} from './follow';

// The feature reel: every feature of the live site, from the real recordings, set in a field-manual
// layout (after the Arknights: Endfield UI — outline index numerals, hairlines, a survey grid) and
// moved only by graphic means: panels sliding on a conveyor, a lime bar wiping between them, titles
// rising line by line out of masks, a rail along the bottom that runs the whole film with a marker
// riding from section to section. No filters, no glitch, no stock transitions.

const FPS = 60;
const OVER = 26; // frames a hand-over between sections takes
const T = (r: unknown) => r as Track;
type Ev = {t: number; type: string; label?: string};
const evs = (r: Track) => r.track as Ev[];
const first = (r: Track, type: string, after = 0) => evs(r).find((e) => e.type === type && e.t >= after)?.t ?? after;
const lastBefore = (r: Track, type: string, before: number) => [...evs(r)].reverse().find((e) => e.type === type && e.t < before)?.t ?? before;
const end = (r: Track) => evs(r)[evs(r).length - 1].t;

type Seg = {name: string; rec: Track; from: number; to: number; rate?: number; zoom?: number; extra?: Key[]; fast?: boolean};
type Section = {n: string; title: [string, string]; note: string; source: string; segs: Seg[]; phone?: boolean; flip?: boolean};
const answer = (t: number, zoom = 1.7): Key => ({t, zoom, x: 1950, y: 640});

const HOME = T(homeRec), IMPORT = T(importRec), ASK = T(askRec), EVID = T(evidenceRec), TL = T(timelineRec), REPLAY = T(replayRec);
const SHOT = T(shotRec), GIF = T(gifRec), TAB = T(tabRec), NOTES = T(notesRec), PHONE = T(phoneRec), HIST = T(historyRec), PROF = T(profileRec), DOCS = T(docsRec);
const READY = markAt(IMPORT, 'ready'), ANALYSING = markAt(IMPORT, 'analysing');
const ASKED = markAt(ASK, 'asked'), CITES = markAt(ASK, 'cites'), PLAYING = markAt(EVID, 'playing');
const REPLAYED = markAt(REPLAY, 'replay'), ATTACHED = markAt(SHOT, 'attached'), COMPLETED = markAt(TAB, 'completed');
const STUDIO = markAt(GIF, 'studio'), MAKING = markAt(GIF, 'making'), MADE = markAt(GIF, 'made');
const NOTES_DONE = markAt(NOTES, 'notes'), PHONE_NOTES = markAt(PHONE, 'notes');
const PHONE_MAKE = PHONE_NOTES ? lastBefore(PHONE, 'click', PHONE_NOTES) + 0.3 : 0;
const HOME_IN = first(HOME, 'ready') + 0.8;

const SECTIONS: Section[] = [
  {n: '01', title: ['贴一个', '教程链接'], note: '它就开始逐帧读：画面、原声、画面文字', source: '实机 · Excel VLOOKUP 教程', segs: [
    {name: 'import', rec: IMPORT, from: first(IMPORT, 'click') - 0.3, to: ANALYSING + 0.3, rate: 2.2, zoom: 2.6},
    {name: 'import', rec: IMPORT, from: ANALYSING + 0.3, to: READY + 0.3, rate: Math.max(2, (READY - ANALYSING) / 3), zoom: 1.3, fast: true},
    {name: 'import', rec: IMPORT, from: READY + 0.3, to: READY + 2.8, rate: 1.2, zoom: 1.6},
  ]},
  {n: '02', title: ['看到哪', '问到哪'], note: '用自己的话问，回答先给结论', source: '实机 · 提问', flip: true, segs: [
    {name: 'ask', rec: ASK, from: lastBefore(ASK, 'click', ASKED) - 0.3, to: ASKED + 0.5, rate: 2.2, zoom: 2.4},
    {name: 'ask', rec: ASK, from: ASKED + 0.5, to: CITES - 1.4, rate: Math.max(2, (CITES - ASKED) / 3.5), zoom: 1.7, fast: true, extra: [answer(ASKED + 2), answer(CITES - 2, 1.9)]},
  ]},
  {n: '03', title: ['每句回答', '都有出处'], note: '打开时间标签，点一下就回到原片那一刻', source: '实机 · 证据回看', segs: [
    {name: 'ask', rec: ASK, from: CITES - 1.4, to: end(ASK) + 0.6, rate: 1.3, zoom: 2.1, extra: [answer(CITES + 0.3, 2.1)]},
    {name: 'evidence', rec: EVID, from: PLAYING - 0.5, to: PLAYING + 4.5, rate: 1.2, zoom: 2.2, extra: [{t: PLAYING, zoom: 1.9, x: 3200, y: 420}]},
  ]},
  {n: '04', title: ['时间轴上', '一帧一帧'], note: '划过薄片就能看清每一帧', source: '实机 · 时间轴', flip: true, segs: [
    {name: 'timeline', rec: TL, from: first(TL, 'click', 7) + 0.6, to: end(TL) + 1, rate: 1.7, zoom: 1.9},
  ]},
  {n: '05', title: ['拖一段', '逐帧慢放'], note: '看不清的动作，拉开来一帧帧看', source: '实机 · 慢放', segs: [
    {name: 'replay', rec: REPLAY, from: REPLAYED - 4.5, to: end(REPLAY) + 0.4, rate: 1.9, zoom: 2, extra: [{t: REPLAYED + 1.5, zoom: 1.7, x: 1900, y: 900}]},
  ]},
  {n: '06', title: ['卡住了', '发张截图'], note: '不用描述，它告诉你在第几步', source: '实机 · 截图提问', flip: true, segs: [
    {name: 'screenshot', rec: SHOT, from: ATTACHED - 1.4, to: end(SHOT) + 0.4, rate: 1.9, zoom: 2.2, extra: [answer(ATTACHED + 4, 1.6), answer(end(SHOT), 1.8)]},
  ]},
  {n: '07', title: ['一句话', '截成表情包'], note: '选一段、调帧率宽度，生成 GIF', source: '实机 · 奶龙的宿命对视', segs: [
    {name: 'gif', rec: GIF, from: first(GIF, 'key') - 0.3, to: STUDIO + 0.5, rate: 2, zoom: 2.4},
    {name: 'gif', rec: GIF, from: STUDIO + 0.5, to: MAKING + 0.2, rate: 1.7, zoom: 1.7, extra: [{t: STUDIO + 1, zoom: 1.5, x: 1900, y: 900}]},
    {name: 'gif', rec: GIF, from: MAKING + 0.2, to: MADE, rate: Math.max(1, (MADE - MAKING) / 1.2), zoom: 1.5, fast: MADE - MAKING > 3},
    {name: 'gif', rec: GIF, from: MADE, to: end(GIF) + 0.4, rate: 1.2, zoom: 1.7, extra: [{t: MADE + 0.5, zoom: 1.6, x: 1900, y: 1200}]},
  ]},
  {n: '08', title: ['Tab', '补全提问'], note: '打几个字，灰字补全剩下的问题', source: '实机 · 输入框', flip: true, segs: [
    {name: 'tab', rec: TAB, from: first(TAB, 'key') - 0.4, to: COMPLETED + 2, rate: 1.8, zoom: 2.8},
  ]},
  {n: '09', title: ['笔记', '按章节整理'], note: '要点、公式、配图和思维导图', source: '实机 · 工作台 · 笔记', segs: [
    {name: 'notes', rec: NOTES, from: 12.6, to: NOTES_DONE, rate: Math.max(2, (NOTES_DONE - 12.6) / 2.2), zoom: 1.6, fast: true,
      extra: [{t: 14, zoom: 1.7, x: 3250, y: 760}, {t: NOTES_DONE - 0.5, zoom: 1.7, x: 3250, y: 760}]},
    {name: 'notes', rec: NOTES, from: NOTES_DONE, to: NOTES_DONE + 10, rate: 1.7, zoom: 1.5,
      extra: [{t: NOTES_DONE + 0.3, zoom: 1.7, x: 3250, y: 760}, {t: NOTES_DONE + 3.4, zoom: 1.15, x: 1920, y: 1080}, {t: NOTES_DONE + 10, zoom: 1.25, x: 1920, y: 1000}]},
  ]},
  {n: '10', title: ['手机上', '也一样好用'], note: '大图选帧，笔记存成一张长图', source: '实机 · 手机', phone: true, flip: true, segs: PHONE_NOTES ? [
    {name: 'phone', rec: PHONE, from: first(PHONE, 'ready') + 1, to: PHONE_MAKE, rate: 2.4},
    {name: 'phone', rec: PHONE, from: PHONE_MAKE, to: PHONE_NOTES, rate: Math.max(2, (PHONE_NOTES - PHONE_MAKE) / 1.2), fast: true},
    {name: 'phone', rec: PHONE, from: PHONE_NOTES, to: end(PHONE) + 5.5, rate: 1.8},
  ] : [{name: 'phone', rec: PHONE, from: first(PHONE, 'ready') + 1, to: end(PHONE), rate: 2.6}]},
  {n: '11', title: ['历史·我的', '和文档'], note: '会话都留着，账号各管各的', source: '实机 · 历史 / 我的 / 文档', segs: [
    {name: 'history', rec: HIST, from: first(HIST, 'click') - 0.4, to: end(HIST) + 1.4, rate: 1.4, zoom: 1.6},
    {name: 'profile', rec: PROF, from: first(PROF, 'click') - 0.4, to: end(PROF) + 1.4, rate: 1.4, zoom: 1.6},
    {name: 'docs', rec: DOCS, from: first(DOCS, 'click') - 0.4, to: end(DOCS) + 1, rate: 1.6, zoom: 1.4},
  ]},
];

const segFrames = (s: Seg) => Math.round(((s.to - s.from) / (s.rate ?? 1)) * FPS);
const secFrames = (s: Section) => s.segs.reduce((n, g) => n + segFrames(g), 0);
const INTRO = 330;
const OUTRO = 300;
const STARTS = SECTIONS.reduce<number[]>((a, s, i) => [...a, i === 0 ? INTRO : a[i - 1] + secFrames(SECTIONS[i - 1])], []);
const OUTRO_AT = STARTS[STARTS.length - 1] + secFrames(SECTIONS[SECTIONS.length - 1]);
export const REEL_FRAMES = OUTRO_AT + OUTRO;

const ease = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
const MARK = (k = 1): React.CSSProperties => ({backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundRepeat: 'no-repeat',
  backgroundSize: `${clamp01(k) * 100}% 36%`, backgroundPosition: '0 90%'});

/** A line of text rising into place out of its own mask (and dropping out again on `out`). */
const Rise: React.FC<{k: number; out?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({k, out = 0, children, style}) => (
  <div style={{overflow: 'hidden', paddingBottom: '0.08em', ...style}}>
    <div style={{transform: `translateY(${(1 - ease(clamp01(k))) * 110 - ease(clamp01(out)) * 110}%)`}}>{children}</div>
  </div>
);

/** A child given its own frame count (a segment's), as Shot reads useCurrentFrame. */
const Clock: React.FC<{frame: number; children: React.ReactNode}> = ({frame, children}) => {
  const now = useCurrentFrame();
  return <Sequence from={now - frame} layout="none">{children}</Sequence>;
};

/** Which segment plays at a section's local frame, and the frame within it. */
const segAt = (sec: Section, local: number) => {
  let at = 0;
  for (const s of sec.segs) {
    const d = segFrames(s);
    if (local < at + d || s === sec.segs[sec.segs.length - 1]) return {seg: s, local: Math.max(0, local - at)};
    at += d;
  }
  return {seg: sec.segs[0], local: 0};
};

const PANEL = {w: 1104, h: 621};

/** The recording in a framed panel: hairline frame, a source tab, corner ticks, a running timecode. */
const Panel: React.FC<{sec: Section; local: number}> = ({sec, local}) => {
  const {seg, local: l} = segAt(sec, local);
  const keys = follow(seg.rec, seg.from, seg.to, {zoom: seg.zoom ?? 2, extra: seg.extra});
  const t = seg.from + (l / FPS) * (seg.rate ?? 1);
  const fast = seg.fast ? Math.round((seg.rate ?? 1) * 10) / 10 : 0;
  const tick = (x: number, y: number) => <path key={`${x}-${y}`} d={`M${x - 10} ${y}H${x + 10}M${x} ${y - 10}V${y + 10}`} stroke={INK} strokeWidth={2} />;
  return (
    <div style={{position: 'relative', width: PANEL.w, height: PANEL.h}}>
      <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: PAPER, boxShadow: '0 30px 70px rgba(26,26,26,0.16)'}}>
        <div style={{width: 1920, height: 1080, transform: `scale(${PANEL.w / 1920})`, transformOrigin: '0 0'}}>
          <Clock frame={l}><Shot name={seg.name} rec={seg.rec} from={seg.from} rate={seg.rate ?? 1} keys={keys} /></Clock>
        </div>
      </div>
      <div style={{position: 'absolute', inset: 0, border: `2px solid ${INK}`, pointerEvents: 'none'}} />
      <svg width={PANEL.w + 60} height={PANEL.h + 60} style={{position: 'absolute', left: -30, top: -30, overflow: 'visible'}}>
        {tick(0, 0)}{tick(PANEL.w + 60, 0)}{tick(0, PANEL.h + 60)}{tick(PANEL.w + 60, PANEL.h + 60)}
      </svg>
      <div style={{position: 'absolute', left: 0, top: -46, display: 'flex', gap: 10, alignItems: 'center'}}>
        <span style={{fontFamily: CONSOLE, fontSize: 30, background: INK, color: PAPER, padding: '0 12px'}}>{sec.n}</span>
        <span style={{fontFamily: PIXEL, fontSize: 30, color: INK}}>{sec.source}</span>
        {fast ? <span style={{fontFamily: CONSOLE, fontSize: 30, background: LIME, color: INK, padding: '0 10px'}}>{'>>'} ×{fast} 已加速</span> : null}
      </div>
      <div style={{position: 'absolute', right: 0, bottom: -44, fontFamily: CONSOLE, fontSize: 30, color: INK2}}>
        ▶ {String(Math.floor(t / 60)).padStart(2, '0')}:{(t % 60).toFixed(1).padStart(4, '0')}
      </div>
    </div>
  );
};

/** The phone recording in a phone body, its segments one after another. */
const PhonePanel: React.FC<{sec: Section; local: number}> = ({sec, local}) => {
  const {seg, local: l} = segAt(sec, local);
  const h = 760;
  const w = (h * 1170) / 2532;
  const fast = seg.fast ? Math.round((seg.rate ?? 1) * 10) / 10 : 0;
  return (
    <div style={{position: 'relative', width: PANEL.w, height: PANEL.h, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{width: w + 24, height: h + 24, borderRadius: 56, background: INK, padding: 12, boxSizing: 'border-box', boxShadow: '0 30px 70px rgba(26,26,26,0.22)'}}>
        <div style={{width: w, height: h, borderRadius: 46, overflow: 'hidden', background: PAPER}}>
          <Clock frame={l}>
            <OffthreadVideo src={staticFile(`rec/${seg.name}.mp4`)} startFrom={Math.round(seg.from * FPS)} playbackRate={seg.rate ?? 1} muted style={{width: w, height: h}} />
          </Clock>
        </div>
      </div>
      <div style={{position: 'absolute', left: 0, top: -46, display: 'flex', gap: 10, alignItems: 'center'}}>
        <span style={{fontFamily: CONSOLE, fontSize: 30, background: INK, color: PAPER, padding: '0 12px'}}>{sec.n}</span>
        <span style={{fontFamily: PIXEL, fontSize: 30, color: INK}}>{sec.source}</span>
        {fast ? <span style={{fontFamily: CONSOLE, fontSize: 30, background: LIME, color: INK, padding: '0 10px'}}>{'>>'} ×{fast} 已加速</span> : null}
      </div>
    </div>
  );
};

/** One section on the conveyor: its panel slides in from the right and out to the left; its title
 *  rises line by line and drops away. `enter` 0→1 before its start, `exit` 0→1 after its end. */
const SectionView: React.FC<{sec: Section; local: number; enter: number; exit: number}> = ({sec, local, enter, exit}) => {
  const flip = Boolean(sec.flip);
  const panelX = (1 - ease(enter)) * 1500 * (flip ? -1 : 1) - ease(exit) * 1900 * (flip ? -1 : 1);
  const textX = 96;
  const text = (
    <div style={{position: 'absolute', top: 210, width: 520, [flip ? 'right' : 'left']: textX, display: 'flex', flexDirection: 'column', gap: 10,
      alignItems: flip ? 'flex-end' : 'flex-start', textAlign: flip ? 'right' : 'left'}}>
      <Rise k={enter * 1.2} out={exit * 1.4}>
        <span style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 190, lineHeight: 0.86, color: 'transparent', WebkitTextStroke: `2px ${INK}`, letterSpacing: -6}}>{sec.n}</span>
      </Rise>
      <Rise k={enter * 1.2 - 0.12} out={exit * 1.4 - 0.08}><span style={{fontFamily: SC, fontWeight: 900, fontSize: 104, lineHeight: 1.08, color: INK, whiteSpace: 'nowrap'}}>{sec.title[0]}</span></Rise>
      <Rise k={enter * 1.2 - 0.22} out={exit * 1.4 - 0.16}>
        <span style={{fontFamily: SC, fontWeight: 900, fontSize: 104, lineHeight: 1.08, color: INK, ...MARK(clamp01(local / 24))}}>{sec.title[1]}</span>
      </Rise>
      <div style={{width: 420 * ease(clamp01(enter * 1.2 - 0.3)) * (1 - ease(exit)), height: 3, background: INK, margin: '18px 0'}} />
      <Rise k={enter * 1.2 - 0.32} out={exit * 1.4 - 0.24}><span style={{fontFamily: PIXEL, fontSize: 36, color: INK2, lineHeight: 1.5, display: 'block', maxWidth: 470}}>{sec.note}</span></Rise>
    </div>
  );
  return (
    <AbsoluteFill>
      {/* the section's numeral, huge and faint, drifting behind */}
      <div style={{position: 'absolute', [flip ? 'left' : 'right']: -60 + local * 0.15, bottom: 40, fontFamily: DISPLAY, fontWeight: 900, fontSize: 620,
        color: 'transparent', WebkitTextStroke: `2px ${LINE}`, lineHeight: 0.8, opacity: ease(enter) * (1 - ease(exit))}}>{sec.n}</div>
      {text}
      <div style={{position: 'absolute', top: 190, [flip ? 'left' : 'right']: 90, transform: `translateX(${panelX}px)`}}>
        {sec.phone ? <PhonePanel sec={sec} local={Math.max(0, local)} /> : <Panel sec={sec} local={Math.max(0, local)} />}
      </div>
    </AbsoluteFill>
  );
};

/** The rail along the bottom, the whole film: ticks, the sections' numbers, a lime marker riding to the current one. */
const Rail: React.FC<{frame: number}> = ({frame}) => {
  const x0 = 96;
  const x1 = 1824;
  const span = x1 - x0;
  const xOf = (f: number) => x0 + span * clamp01((f - INTRO) / Math.max(1, OUTRO_AT - INTRO));
  const appear = ease(clamp01((frame - INTRO + 60) / 40)) * (1 - ease(clamp01((frame - OUTRO_AT - 20) / 40)));
  const cur = STARTS.reduce((k, s, i) => (frame >= s - OVER / 2 ? i : k), 0);
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 120, opacity: appear}}>
      <div style={{position: 'absolute', left: x0, top: 58, width: span, height: 2, background: INK}} />
      {Array.from({length: 73}, (_, i) => <div key={i} style={{position: 'absolute', left: x0 + (span * i) / 72, top: i % 6 === 0 ? 46 : 52, width: 2, height: i % 6 === 0 ? 14 : 6, background: INK3}} />)}
      {SECTIONS.map((s, i) => (
        <span key={s.n} style={{position: 'absolute', left: xOf(STARTS[i]) - 4, top: 70, fontFamily: CONSOLE, fontSize: 26, color: i === cur ? INK : INK3}}>{s.n}</span>
      ))}
      <div style={{position: 'absolute', left: x0, top: 54, width: xOf(frame) - x0, height: 10, background: LIME}} />
      <div style={{position: 'absolute', left: xOf(frame) - 7, top: 40, width: 14, height: 38, background: INK}} />
    </div>
  );
};

/** The lime bar that wipes across at every hand-over, ahead of the incoming panel. */
const Wiper: React.FC<{frame: number}> = ({frame}) => {
  const bars = STARTS.slice(1).concat(OUTRO_AT).map((s, i) => {
    const k = (frame - (s - OVER)) / (OVER * 1.4);
    if (k <= 0 || k >= 1) return null;
    const flip = Boolean(SECTIONS[i + 1]?.flip);
    const x = flip ? -260 + ease(k) * 2440 : 2180 - ease(k) * 2440;
    return <div key={s} style={{position: 'absolute', top: 0, bottom: 0, left: x, width: 64, background: LIME, transform: 'skewX(-12deg)'}} />;
  });
  return <AbsoluteFill style={{pointerEvents: 'none'}}>{bars}</AbsoluteFill>;
};

// ---------------------------------------------------------------- the opening and the close
const Intro: React.FC<{frame: number}> = ({frame}) => {
  const t = clamp01(frame / 120);
  const progress = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
  const title = clamp01((frame - 130) / 30);
  const steps = stepped(frame, 60, 12);
  const out = clamp01((frame - INTRO + OVER) / OVER);
  const panel = clamp01((frame - 190) / 34);
  return (
    <AbsoluteFill>
      <div style={{opacity: 1 - ease(title)}}><Contour progress={progress} yaw={0.6 + frame * 0.0016} scale={0.56 + 0.1 * easeOut(frame / 150)} cy={600} /></div>
      <div style={{position: 'absolute', left: 96, top: 82, display: 'flex', flexDirection: 'column', gap: 6, opacity: 1 - ease(out)}}>
        <span style={{fontFamily: PIXEL, fontSize: 48, color: INK}}>逐帧读取</span>
        <span style={{fontFamily: CONSOLE, fontSize: 34, color: INK2}}>{String(Math.round(progress * 100)).padStart(3, '0')} %</span>
        <div style={{width: 520 * easeOut(frame / 30), height: 2, background: INK, marginTop: 8}} />
      </div>
      {/* the name, then the homepage itself sliding in beside it */}
      <div style={{position: 'absolute', left: 96, top: 360, display: 'flex', flexDirection: 'column', gap: 8}}>
        <Rise k={title * 1.3} out={out * 1.4}><span style={{fontFamily: SC, fontWeight: 900, fontSize: 210, lineHeight: 1, color: INK}}><span style={{...MARK(clamp01((frame - 160) / 20))}}>帧</span>寻</span></Rise>
        <Rise k={title * 1.3 - 0.15} out={out * 1.4 - 0.1}>
          <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 96, color: INK, letterSpacing: -4}}>GongJ<span style={{color: '#9CC229'}}>!</span>ng<span style={{color: '#9CC229'}}>{steps % 10 < 7 ? '?' : '!'}</span></span>
        </Rise>
        <Rise k={title * 1.3 - 0.35} out={out * 1.4 - 0.2}><span style={{fontFamily: PIXEL, fontSize: 44, color: INK2, lineHeight: 1.5}}>视频理解工作台<br />看见，再求证。</span></Rise>
      </div>
      <div style={{position: 'absolute', right: 90, top: 190, transform: `translateX(${(1 - ease(panel)) * 1500 - ease(out) * 1900}px)`}}>
        <div style={{position: 'relative', width: PANEL.w, height: PANEL.h, overflow: 'hidden', border: `2px solid ${INK}`, boxShadow: '0 30px 70px rgba(26,26,26,0.16)'}}>
          <div style={{width: 1920, height: 1080, transform: `scale(${PANEL.w / 1920})`, transformOrigin: '0 0'}}>
            <Clock frame={Math.max(0, frame - 190)}>
              <Shot name="home" rec={HOME} from={HOME_IN} rate={1} keys={[{t: HOME_IN, zoom: 1.35, x: 1500, y: 800}, {t: HOME_IN + 3, zoom: 1.05, x: 1920, y: 1080}]} />
            </Clock>
          </div>
        </div>
        <div style={{position: 'absolute', left: 0, top: -46, fontFamily: PIXEL, fontSize: 30, color: INK, opacity: panel}}>linyi.work/ZhenXun · 实机</div>
      </div>
      <Sfx name="whoosh" at={130} volume={0.35} />
      <Sfx name="whoosh" at={190} volume={0.3} rate={1.2} />
    </AbsoluteFill>
  );
};

const Outro: React.FC<{frame: number}> = ({frame}) => {
  const k = clamp01(frame / 40);
  const steps = stepped(frame, 60, 12);
  const out = clamp01((frame - OUTRO + 40) / 40);
  return (
    <AbsoluteFill style={{opacity: 1 - out}}>
      <div style={{opacity: ease(k)}}><Sculpture phase={4} scale={1.05} y={-0.5} /></div>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 24}}>
        <Rise k={k * 1.3}><span style={{fontFamily: SC, fontWeight: 900, fontSize: 230, lineHeight: 1, color: INK}}><span style={{color: LIME, textShadow: `6px 6px 0 ${INK}`}}>帧</span>寻</span></Rise>
        <Rise k={k * 1.3 - 0.15}><span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 110, color: INK, letterSpacing: -4}}>GongJ<span style={{color: '#9CC229'}}>!</span>ng<span style={{color: '#9CC229'}}>{steps % 10 < 7 ? '?' : '!'}</span></span></Rise>
        <div style={{width: 1000 * ease(clamp01((frame - 20) / 30)), height: 8, background: LIME}} />
        <div style={{display: 'flex', gap: 36, alignItems: 'center', fontFamily: PIXEL, fontSize: 56, color: INK, opacity: frame > 30 ? 1 : 0}}>
          <Typed text="看见，再求证。" at={32} cps={20} />
          <span style={{fontFamily: SILK, fontWeight: 700, fontSize: 40, color: LINE2}}>|||</span>
          <span style={{fontFamily: CONSOLE, fontSize: 52, color: INK2}}>linyi.work/ZhenXun</span>
        </div>
      </AbsoluteFill>
      <Sfx name="impact" at={4} volume={0.45} />
    </AbsoluteFill>
  );
};

export const Reel: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Fill>
      {frame < INTRO + 10 ? <Intro frame={frame} /> : null}
      {SECTIONS.map((sec, i) => {
        const s = STARTS[i];
        const e = s + secFrames(sec);
        if (frame < s - OVER || frame > e + OVER) return null;
        const enter = clamp01((frame - (s - OVER)) / OVER);
        const exit = clamp01((frame - e) / OVER);
        return (
          <React.Fragment key={sec.n}>
            <SectionView sec={sec} local={frame - s} enter={enter} exit={exit} />
          </React.Fragment>
        );
      })}
      {frame >= OUTRO_AT - 10 ? <Outro frame={frame - OUTRO_AT} /> : null}
      <Wiper frame={frame} />
      <Rail frame={frame} />
      {STARTS.map((s) => <Sfx key={s} name="whoosh" at={s - OVER} volume={0.32} rate={1.1} />)}
      {/* top corners: the name and the count, the whole film */}
      <div style={{position: 'absolute', left: 96, top: 40, fontFamily: CONSOLE, fontSize: 28, color: INK3, opacity: frame > INTRO ? 1 : 0}}>帧寻 GongJ!ng? · 实机演示</div>
      <div style={{position: 'absolute', right: 96, top: 40, fontFamily: CONSOLE, fontSize: 28, color: INK3, opacity: frame > INTRO && frame < OUTRO_AT ? 1 : 0}}>
        {String(STARTS.reduce((k, s, i) => (frame >= s - OVER / 2 ? i + 1 : k), 1)).padStart(2, '0')} / {SECTIONS.length}
      </div>
    </Fill>
  );
};
