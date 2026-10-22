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

const IMPORT = T(importRec);
const ASK = T(askRec);
const READY = markAt(IMPORT, 'ready');
const ANALYSING = markAt(IMPORT, 'analysing');
const ASKED = markAt(ASK, 'asked');
const EVID = T(evidenceRec);
const SEEK = markAt(EVID, 'seek');
const REPLAY = T(replayRec);
const SHOT = T(shotRec);
const TAB = T(tabRec);

/** A scene: one or more stretches of recordings played one after another, with a caption. */
type Scene = {segs: Seg[]; caption: string; mark: string; via?: Parameters<typeof reveal>[0]};
const answerArea = (t: number, zoom = 1.7): Key => ({t, zoom, x: 1950, y: 640});

const SCENES: Scene[] = [
  {caption: '帧寻 · 视频理解工作台', mark: '00', segs: [{name: 'home', rec: T(homeRec), from: 4.0, to: 9.6, zoom: 1.6,
    extra: [{t: 4.0, zoom: 1.9, x: 900, y: 420}, {t: 6.6, zoom: 1.25, x: 1600, y: 900}]}]},
  {caption: '贴一个教程链接', mark: '01', via: {kind: 'slashes', angle: -24, tint: INK}, segs: [
    {name: 'import', rec: IMPORT, from: 6.6, to: ANALYSING + 0.4, rate: 1.6, zoom: 2.6},
    {name: 'import', rec: IMPORT, from: ANALYSING + 0.4, to: READY + 0.3, rate: 3.5, zoom: 1.4, fast: true,
      extra: [{t: ANALYSING + 1.5, zoom: 1.5, x: 1600, y: 1000}, {t: READY, zoom: 1.2, x: 1920, y: 1080}]},
    {name: 'import', rec: IMPORT, from: READY + 0.3, to: READY + 4.6, zoom: 1.8},
  ]},
  {caption: '看到哪，问到哪', mark: '02', via: {kind: 'blocks', seed: 3, tint: INK}, segs: [
    {name: 'ask', rec: ASK, from: 6.8, to: ASKED + 0.6, rate: 1.7, zoom: 2.4},
    {name: 'ask', rec: ASK, from: ASKED + 0.6, to: ASK.track[ASK.track.length - 1].t + 1.6, rate: 1.4, zoom: 1.6,
      extra: [answerArea(ASKED + 2), answerArea(ASKED + 6, 1.9)]},
  ]},
  {caption: '每句回答都有出处，点一下回到原片', mark: '03', via: {kind: 'bars', tint: LIME, seed: 5}, segs: [
    {name: 'evidence', rec: EVID, from: 10.6, to: SEEK + 7.4, rate: 1.1, zoom: 2.2,
      extra: [{t: SEEK + 0.8, zoom: 1.9, x: 3200, y: 420}, {t: SEEK + 6.5, zoom: 2.1, x: 3200, y: 420}]},
  ]},
  {caption: '拖一段，逐帧慢放', mark: '04', via: {kind: 'slashes', angle: 24, tint: LIME}, segs: [
    {name: 'replay', rec: REPLAY, from: 5.8, to: 25, rate: 1.9, zoom: 2,
      extra: [{t: markAt(REPLAY, 'replay') + 1.5, zoom: 1.7, x: 1900, y: 900}, {t: 24.5, zoom: 1.8, x: 1900, y: 860}]},
  ]},
  {caption: '卡住了？发张截图就行', mark: '05', via: {kind: 'blocks', seed: 6, tint: INK}, segs: [
    {name: 'screenshot', rec: SHOT, from: 13.8, to: 27, rate: 1.5, zoom: 2.2,
      extra: [answerArea(19.5, 1.6), answerArea(26.5, 1.8)]},
  ]},
  {caption: 'Tab 补全下一个问题', mark: '06', via: {kind: 'bars', tint: INK, seed: 2}, segs: [
    {name: 'tab', rec: TAB, from: 7.2, to: 19, rate: 1.5, zoom: 2.8},
  ]},
];
const PHONE = {from: 6, to: 34.5, rate: 2.4};

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
          {'>>'} ×{fast} <span style={{fontFamily: PIXEL, fontSize: 36}}>已加速</span>
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
  return (
    <AbsoluteFill style={{background: PAPER, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'absolute', left: 140, top: 300, fontFamily: SC, fontWeight: 900, fontSize: 96, color: INK, lineHeight: 1.2, width: 520}}>
        手机上<br />也一样<span style={{backgroundImage: `linear-gradient(${LIME}, ${LIME})`, backgroundSize: '100% 38%', backgroundRepeat: 'no-repeat', backgroundPosition: '0 88%'}}>好用</span>
      </div>
      <div style={{width: w + 28, height: h + 28, borderRadius: 64, background: INK, padding: 14, boxSizing: 'border-box', boxShadow: '0 40px 90px rgba(26,26,26,0.25)',
        transform: `translateY(${(1 - k) * 300}px) rotate(${(1 - k) * 4}deg)`}}>
        <div style={{width: w, height: h, borderRadius: 52, overflow: 'hidden', background: PAPER}}>
          <OffthreadVideo src={staticFile('rec/phone.mp4')} startFrom={Math.round(PHONE.from * fps)} playbackRate={PHONE.rate} muted style={{width: w, height: h}} />
        </div>
      </div>
      <div style={{position: 'absolute', right: 120, bottom: 120, fontFamily: CONSOLE, fontSize: 40, color: INK2}}>{'>>'} ×{PHONE.rate} 已加速</div>
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

const PHONE_FRAMES = Math.round(((PHONE.to - PHONE.from) / PHONE.rate) * FPS);
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
