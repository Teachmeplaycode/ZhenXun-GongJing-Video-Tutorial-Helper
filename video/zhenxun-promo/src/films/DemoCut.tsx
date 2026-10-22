import React from 'react';
import {AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {TransitionSeries} from '@remotion/transitions';
import askRec from '../../public/rec/ask.json';
import evidenceRec from '../../public/rec/evidence.json';
import homeRec from '../../public/rec/home.json';
import importRec from '../../public/rec/import.json';
import phoneRec from '../../public/rec/phone.json';
import replayRec from '../../public/rec/replay.json';
import shotRec from '../../public/rec/screenshot.json';
import tabRec from '../../public/rec/tab.json';
import gifRec from '../../public/rec/gif.json';
import {Key, Track} from '../camera';
import {Shot} from '../Shot';
import {CONSOLE, easeOut, Grain, INK, INK2, LIME, PAPER, PIXEL, pop, SC, Sfx, SILK, stepped, WORDMARK} from '../pv/kit';
import {reveal, timing} from '../pv/transitions';
import {follow, markAt} from './follow';

// The demo cut: the live site, feature by feature, from the recordings (record/record.mjs), the
// camera easing in on whatever the cursor does (Screen Studio–style) and out across pauses, the
// waits sped up and marked as such, a caption per feature, scenes handed over through the PV's
// shape reveals. Light, the site's own look; no HUD.

const FPS = 60;
type Seg = {name: string; rec: Track; from: number; to: number; rate?: number; zoom?: number; extra?: Key[]; fast?: boolean};
const T = (r: unknown) => r as Track;

// Every stretch is placed by what happened in the take (record/record.mjs marks and events), not
// by clock times, so a new take cuts the same way.
type Ev = {t: number; type: string; label?: string};
const evs = (r: Track) => r.track as Ev[];
const first = (r: Track, type: string, after = 0) => evs(r).find((e) => e.type === type && e.t >= after)?.t ?? after;
const lastBefore = (r: Track, type: string, before: number) => [...evs(r)].reverse().find((e) => e.type === type && e.t < before)?.t ?? before;
const end = (r: Track) => evs(r)[evs(r).length - 1].t;

const HOME = T(homeRec);
const IMPORT = T(importRec);
const ASK = T(askRec);
const EVID = T(evidenceRec);
const REPLAY = T(replayRec);
const SHOT = T(shotRec);
const TAB = T(tabRec);
const GIF = T(gifRec);
const READY = markAt(IMPORT, 'ready');
const ANALYSING = markAt(IMPORT, 'analysing');
const ASKED = markAt(ASK, 'asked');
const CITES = markAt(ASK, 'cites');
const PLAYING = markAt(EVID, 'playing');
const REPLAYED = markAt(REPLAY, 'replay');
const ATTACHED = markAt(SHOT, 'attached');
const COMPLETED = markAt(TAB, 'completed');
const STUDIO = markAt(GIF, 'studio');
const MAKING = markAt(GIF, 'making');
const MADE = markAt(GIF, 'made');
const HOME_IN = first(HOME, 'ready') + 0.8; // the page has painted

/** A scene: one or more stretches of recordings played one after another, with a caption. */
type Scene = {segs: Seg[]; caption: string; mark: string; via?: Parameters<typeof reveal>[0]};
const answerArea = (t: number, zoom = 1.7): Key => ({t, zoom, x: 1950, y: 640});

const SCENES: Scene[] = [
  {caption: '帧寻 · 视频理解工作台', mark: '00', segs: [{name: 'home', rec: HOME, from: HOME_IN, to: HOME_IN + 5.6, zoom: 1.6,
    extra: [{t: HOME_IN, zoom: 1.9, x: 900, y: 420}, {t: HOME_IN + 2.6, zoom: 1.25, x: 1600, y: 900}]}]},
  {caption: '贴一个教程链接', mark: '01', via: {kind: 'slashes', angle: -24, tint: INK}, segs: [
    {name: 'import', rec: IMPORT, from: first(IMPORT, 'click') - 0.5, to: ANALYSING + 0.4, rate: 1.6, zoom: 2.6},
    {name: 'import', rec: IMPORT, from: ANALYSING + 0.4, to: READY + 0.3, rate: Math.max(1.5, (READY - ANALYSING) / 4.5), zoom: 1.4, fast: true,
      extra: [{t: ANALYSING + 1.5, zoom: 1.5, x: 1600, y: 1000}, {t: READY, zoom: 1.2, x: 1920, y: 1080}]},
    {name: 'import', rec: IMPORT, from: READY + 0.3, to: READY + 4.6, zoom: 1.8},
  ]},
  {caption: '看到哪，问到哪', mark: '02', via: {kind: 'blocks', seed: 3, tint: INK}, segs: [
    {name: 'ask', rec: ASK, from: lastBefore(ASK, 'click', ASKED) - 0.4, to: ASKED + 0.6, rate: 1.7, zoom: 2.4},
    {name: 'ask', rec: ASK, from: ASKED + 0.6, to: CITES - 1.6, rate: Math.max(1.4, (CITES - ASKED) / 6), zoom: 1.6, fast: CITES - ASKED > 10,
      extra: [answerArea(ASKED + 2), answerArea(CITES - 2, 1.9)]},
  ]},
  {caption: '每句回答都有出处，点一下回到原片', mark: '03', via: {kind: 'bars', tint: LIME, seed: 5}, segs: [
    {name: 'ask', rec: ASK, from: CITES - 1.6, to: end(ASK) + 0.8, rate: 1.1, zoom: 2.1, extra: [answerArea(CITES + 0.3, 2.1)]},
    {name: 'evidence', rec: EVID, from: PLAYING - 0.5, to: PLAYING + 6.5, rate: 1.1, zoom: 2.2,
      extra: [{t: PLAYING - 0.2, zoom: 1.9, x: 3200, y: 420}, {t: PLAYING + 6, zoom: 2.1, x: 3200, y: 420}]},
  ]},
  {caption: '拖一段，逐帧慢放', mark: '04', via: {kind: 'slashes', angle: 24, tint: LIME}, segs: [
    {name: 'replay', rec: REPLAY, from: REPLAYED - 4.5, to: end(REPLAY) + 0.4, rate: 1.6, zoom: 2,
      extra: [{t: REPLAYED + 1.5, zoom: 1.7, x: 1900, y: 900}, {t: end(REPLAY), zoom: 1.8, x: 1900, y: 860}]},
  ]},
  {caption: '卡住了？发张截图就行', mark: '05', via: {kind: 'blocks', seed: 6, tint: INK}, segs: [
    {name: 'screenshot', rec: SHOT, from: ATTACHED - 1.6, to: end(SHOT) + 0.4, rate: 1.5, zoom: 2.2,
      extra: [answerArea(ATTACHED + 4, 1.6), answerArea(end(SHOT), 1.8)]},
  ]},
  {caption: '一句话，截成 GIF 表情包', mark: '06', via: {kind: 'bars', tint: LIME, seed: 8}, segs: [
    {name: 'gif', rec: GIF, from: first(GIF, 'key') - 0.6, to: STUDIO + 0.6, rate: 1.6, zoom: 2.4},
    {name: 'gif', rec: GIF, from: STUDIO + 0.6, to: MAKING + 0.3, rate: 1.3, zoom: 1.7, extra: [{t: STUDIO + 1, zoom: 1.5, x: 1900, y: 900}]},
    {name: 'gif', rec: GIF, from: MAKING + 0.3, to: MADE, rate: Math.max(1, (MADE - MAKING) / 1.5), zoom: 1.5, fast: MADE - MAKING > 3},
    {name: 'gif', rec: GIF, from: MADE, to: end(GIF) + 0.4, zoom: 1.7, extra: [{t: MADE + 0.5, zoom: 1.6, x: 1900, y: 1200}]},
  ]},
  {caption: 'Tab 补全下一个问题', mark: '07', via: {kind: 'bars', tint: INK, seed: 2}, segs: [
    {name: 'tab', rec: TAB, from: first(TAB, 'key') - 0.6, to: COMPLETED + 2.4, rate: 1.5, zoom: 2.8},
  ]},
];
// The phone: its taps at 2×, the notes being made (when the take had to make them) fast, the long picture at 1.6×.
const PHONE_REC = T(phoneRec);
const PHONE_NOTES = markAt(PHONE_REC, 'notes');
const PHONE_MAKE = PHONE_NOTES ? lastBefore(PHONE_REC, 'click', PHONE_NOTES) + 0.3 : 0;
const PHONE_SEGS: {from: number; to: number; rate: number; fast?: boolean}[] = PHONE_NOTES ? [
  {from: first(PHONE_REC, 'ready') + 1, to: PHONE_MAKE, rate: 2},
  {from: PHONE_MAKE, to: PHONE_NOTES, rate: Math.max(2, (PHONE_NOTES - PHONE_MAKE) / 1.6), fast: true},
  {from: PHONE_NOTES, to: end(PHONE_REC) + 5.5, rate: 1.6},
] : [{from: first(PHONE_REC, 'ready') + 1, to: end(PHONE_REC) + 0.5, rate: 2.4}];

const segFrames = (s: Seg) => Math.round(((s.to - s.from) / (s.rate ?? 1)) * FPS);
const sceneFrames = (sc: Scene) => sc.segs.reduce((n, s) => n + segFrames(s), 0);

const Captioned: React.FC<{text: string; mark: string; fast?: number}> = ({text, mark, fast}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = pop(frame, 6, fps, 200);
  return (
    <>
      <div style={{position: 'absolute', left: 80, bottom: 70, display: 'flex', alignItems: 'center', gap: 20, background: PAPER, padding: '10px 26px 10px 18px',
        borderRadius: 14, boxShadow: '0 12px 40px rgba(26,26,26,0.14)', transform: `translateY(${(1 - k) * 140}px)`}}>
        <span style={{fontFamily: CONSOLE, fontSize: 40, color: INK, background: LIME, padding: '0 10px', borderRadius: 6}}>{mark}</span>
        <span style={{fontFamily: SC, fontWeight: 900, fontSize: 52, color: INK}}>{text}</span>
      </div>
      {fast ? (
        <div style={{position: 'absolute', right: 80, top: 70, fontFamily: SILK, fontWeight: 700, fontSize: 34, color: INK, background: LIME, padding: '6px 16px', borderRadius: 8}}>
          {'>>'} ×{Math.round(fast * 10) / 10} <span style={{fontFamily: PIXEL, fontSize: 36}}>已加速</span>
        </div>
      ) : null}
    </>
  );
};

const SceneView: React.FC<{sc: Scene}> = ({sc}) => {
  const frame = useCurrentFrame();
  let start = 0;
  let current: Seg = sc.segs[0];
  let local = 0;
  for (const s of sc.segs) {
    const d = segFrames(s);
    if (frame < start + d || s === sc.segs[sc.segs.length - 1]) { current = s; local = frame - start; break; }
    start += d;
  }
  const keys = follow(current.rec, current.from, current.to, {zoom: current.zoom ?? 2, extra: current.extra});
  return (
    <AbsoluteFill style={{background: PAPER}}>
      <SegClock frame={local}>
        <Shot name={current.name} rec={current.rec} from={current.from} rate={current.rate ?? 1} keys={keys} />
      </SegClock>
      <Captioned text={sc.caption} mark={sc.mark} fast={current.fast ? current.rate : undefined} />
      <Sfx name="soft" at={6} volume={0.3} />
    </AbsoluteFill>
  );
};

/** Gives a child its own frame count (the segment's), as Shot reads useCurrentFrame. */
const SegClock: React.FC<{frame: number; children: React.ReactNode}> = ({frame, children}) => {
  const now = useCurrentFrame();
  return <Sequence from={now - frame} layout="none">{children}</Sequence>;
};

const Phone: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = pop(frame, 0, fps, 120);
  const h = 940;
  const w = (h * 1170) / 2532;
  let at = 0;
  let fast: number | null = null;
  const parts = PHONE_SEGS.map((seg, i) => {
    const d = Math.round(((seg.to - seg.from) / seg.rate) * fps);
    if (frame >= at && frame < at + d && seg.fast) fast = seg.rate;
    const el = (
      <Sequence key={i} from={at} durationInFrames={d} layout="none">
        <OffthreadVideo src={staticFile('rec/phone.mp4')} startFrom={Math.round(seg.from * fps)} playbackRate={seg.rate} muted
          style={{position: 'absolute', inset: 0, width: w, height: h}} />
      </Sequence>
    );
    at += d;
    return el;
  });
  return (
    <AbsoluteFill style={{background: PAPER, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'absolute', left: 140, top: 300, fontFamily: SC, fontWeight: 900, fontSize: 96, color: INK, lineHeight: 1.2, width: 520}}>
        手机上<br />也一样<span style={{backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundSize: '100% 38%', backgroundRepeat: 'no-repeat', backgroundPosition: '0 88%'}}>好用</span>
      </div>
      <div style={{width: w + 28, height: h + 28, borderRadius: 64, background: INK, padding: 14, boxSizing: 'border-box', boxShadow: '0 40px 90px rgba(26,26,26,0.25)',
        transform: `translateY(${(1 - k) * 300}px) rotate(${(1 - k) * 4}deg)`}}>
        <div style={{position: 'relative', width: w, height: h, borderRadius: 52, overflow: 'hidden', background: PAPER}}>{parts}</div>
      </div>
      {fast ? <div style={{position: 'absolute', right: 120, bottom: 120, fontFamily: SILK, fontWeight: 700, fontSize: 34, color: INK, background: LIME, padding: '6px 16px', borderRadius: 8}}>
        {'>>'} ×{Math.round((fast as number) * 10) / 10} <span style={{fontFamily: PIXEL, fontSize: 36}}>正在生成笔记</span></div> : null}
    </AbsoluteFill>
  );
};

const End: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const a = pop(frame, 4, fps, 160);
  const steps = stepped(frame, 60, 12);
  return (
    <AbsoluteFill style={{background: PAPER, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 34}}>
      <Sfx name="impact" at={4} volume={0.5} />
      <div style={{display: 'flex', alignItems: 'center', gap: 48, transform: `translateY(${(1 - a) * 80}px)`, opacity: a}}>
        <span style={{fontFamily: SC, fontWeight: 900, fontSize: 220, color: INK, lineHeight: 1}}><span style={{color: LIME, textShadow: `6px 6px 0 ${INK}`}}>帧</span>寻</span>
        <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 120, color: INK, letterSpacing: -5}}>GongJ<span style={{color: '#9CC229'}}>!</span>ng<span style={{color: '#9CC229'}}>{steps % 10 < 7 ? '?' : '!'}</span></span>
      </div>
      <div style={{width: 1100, height: 8, background: LIME, transform: `scaleX(${easeOut((frame - 14) / 20)})`}} />
      <div style={{fontFamily: PIXEL, fontSize: 60, color: INK, opacity: frame > 24 ? 1 : 0}}>看见，再求证。 <span style={{fontFamily: CONSOLE, color: INK2}}>linyi.work/ZhenXun</span></div>
    </AbsoluteFill>
  );
};

const PHONE_FRAMES = PHONE_SEGS.reduce((n, seg) => n + Math.round(((seg.to - seg.from) / seg.rate) * FPS), 0);
const END_FRAMES = 180;
const OVER = 26;
export const DEMO_FRAMES = SCENES.reduce((n, sc) => n + sceneFrames(sc), 0) + PHONE_FRAMES + END_FRAMES - OVER * SCENES.length - OVER;

export const DemoCut: React.FC = () => (
  <AbsoluteFill style={{background: PAPER}}>
    <TransitionSeries>
      {SCENES.flatMap((sc, i) => [
        ...(sc.via ? [<TransitionSeries.Transition key={`t${i}`} timing={timing(OVER)} presentation={reveal(sc.via)} />] : []),
        <TransitionSeries.Sequence key={`s${i}`} durationInFrames={sceneFrames(sc)}><SceneView sc={sc} /></TransitionSeries.Sequence>,
      ])}
      <TransitionSeries.Transition timing={timing(OVER)} presentation={reveal({kind: 'diamond', tint: LIME})} />
      <TransitionSeries.Sequence durationInFrames={PHONE_FRAMES}><Phone /></TransitionSeries.Sequence>
      <TransitionSeries.Transition timing={timing(OVER)} presentation={reveal({kind: 'blocks', seed: 9, tint: INK})} />
      <TransitionSeries.Sequence durationInFrames={END_FRAMES}><End /></TransitionSeries.Sequence>
    </TransitionSeries>
    <Grain opacity={0.06} />
  </AbsoluteFill>
);
