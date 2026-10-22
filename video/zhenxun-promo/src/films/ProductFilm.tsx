import React from 'react';
import {AbsoluteFill, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont as loadSerif} from '@remotion/google-fonts/NotoSerifSC';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import askRec from '../../public/rec/ask.json';
import evidenceRec from '../../public/rec/evidence.json';
import importRec from '../../public/rec/import.json';
import replayRec from '../../public/rec/replay.json';
import shotRec from '../../public/rec/screenshot.json';
import {Key, Track} from '../camera';
import {Shot} from '../Shot';
import {Sfx, WORDMARK} from '../pv/kit';
import {markAt} from './follow';

// The product film, in the manner of the Claude and Codex launch films: a warm, quiet page; one
// sentence at a time in a serif; the real product in a soft-shadowed window that drifts slowly
// closer; cross-fades and nothing else. No HUD, no glitch, no stickers — the product carries it.

const SERIF = `${loadSerif('normal', {weights: ['500', '700']}).fontFamily}, "Songti SC", serif`;
const SANS = `${loadInter('normal', {weights: ['400', '500']}).fontFamily}, "PingFang SC", sans-serif`;
const CANVAS = '#F0EEE6'; // warm paper
const TEXT = '#1F1E1D';
const MUTED = '#6F6B63';
const ACCENT = '#A8CC3A';
const FPS = 60;
const T = (r: unknown) => r as Track;

const ease = (k: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, k)), 3);
/** In and out softly over `d` frames at both ends of a `len`-frame piece. */
const fade = (frame: number, len: number, d = 24) => interpolate(frame, [0, d, len - d, len], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

const Line: React.FC<{text: React.ReactNode; small?: string; len: number; size?: number}> = ({text, small, len, size = 92}) => {
  const frame = useCurrentFrame();
  const o = fade(frame, len, 30);
  return (
    <AbsoluteFill style={{background: CANVAS, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 28}}>
      <div style={{fontFamily: SERIF, fontWeight: 500, fontSize: size, color: TEXT, letterSpacing: 2, opacity: o, transform: `translateY(${(1 - ease(frame / 40)) * 24}px)`}}>{text}</div>
      {small ? <div style={{fontFamily: SANS, fontSize: 30, color: MUTED, letterSpacing: 1, opacity: o * ease((frame - 20) / 30)}}>{small}</div> : null}
    </AbsoluteFill>
  );
};

/** The product in a window: the recording, gently framed (a slow drift toward `focus`). */
const Window: React.FC<{name: string; rec: Track; from: number; to: number; rate?: number; focus: {x: number; y: number; zoom: number}; caption: string; len: number}> =
  ({name, rec, from, to, rate = 1, focus, caption, len}) => {
    const frame = useCurrentFrame();
    const o = fade(frame, len, 26);
    // the camera: wide at first, easing toward the focus over the whole piece (never snapping)
    const keys: Key[] = [
      {t: from, zoom: 1, x: rec.width / 2, y: rec.height / 2},
      {t: to, zoom: focus.zoom, x: focus.x, y: focus.y},
    ];
    const W = 1500;
    const H = (W * 9) / 16;
    const drift = 1 + 0.04 * (frame / len);
    void to;
    return (
      <AbsoluteFill style={{background: CANVAS, alignItems: 'center', justifyContent: 'center', opacity: o}}>
        <div style={{position: 'relative', width: W, height: H, borderRadius: 22, overflow: 'hidden', transform: `translateY(-40px) scale(${drift})`,
          boxShadow: '0 2px 4px rgba(31,30,29,0.06), 0 30px 80px rgba(31,30,29,0.16)', background: '#fff'}}>
          <div style={{position: 'absolute', inset: 0, transform: `scale(${W / 1920})`, transformOrigin: '0 0', width: 1920, height: 1080}}>
            <Shot name={name} rec={rec} from={from} rate={rate} keys={keys} />
          </div>
        </div>
        <div style={{position: 'absolute', bottom: 64, fontFamily: SERIF, fontWeight: 500, fontSize: 44, color: TEXT, opacity: ease((frame - 18) / 30)}}>{caption}</div>
      </AbsoluteFill>
    );
  };

const PhoneWindow: React.FC<{len: number}> = ({len}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const o = fade(frame, len, 26);
  const h = 860;
  const w = (h * 1170) / 2532;
  return (
    <AbsoluteFill style={{background: CANVAS, alignItems: 'center', justifyContent: 'center', opacity: o, flexDirection: 'row', gap: 140}}>
      <div style={{fontFamily: SERIF, fontWeight: 500, fontSize: 64, color: TEXT, lineHeight: 1.5, opacity: ease((frame - 10) / 40)}}>笔记，<br />一张长图带走。</div>
      <div style={{width: w, height: h, borderRadius: 48, overflow: 'hidden', boxShadow: '0 2px 4px rgba(31,30,29,0.06), 0 30px 80px rgba(31,30,29,0.18)',
        transform: `translateY(${(1 - ease(frame / 50)) * 40}px)`, background: '#fff'}}>
        <OffthreadVideo src={staticFile('rec/phone.mp4')} startFrom={Math.round(26 * fps)} playbackRate={1.6} muted style={{width: w, height: h}} />
      </div>
    </AbsoluteFill>
  );
};

const Close: React.FC<{len: number}> = ({len}) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, 30, len - 20, len], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: CANVAS, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 36, opacity: o}}>
      <div style={{display: 'flex', alignItems: 'baseline', gap: 36, transform: `translateY(${(1 - ease(frame / 50)) * 20}px)`}}>
        <span style={{fontFamily: SERIF, fontWeight: 700, fontSize: 150, color: TEXT}}>帧寻</span>
        <span style={{fontFamily: WORDMARK, fontWeight: 700, fontSize: 84, color: TEXT, letterSpacing: -3}}>GongJ<span style={{color: ACCENT}}>!</span>ng?</span>
      </div>
      <div style={{fontFamily: SERIF, fontWeight: 500, fontSize: 48, color: TEXT, opacity: ease((frame - 30) / 40)}}>看见，再求证。</div>
      <div style={{fontFamily: SANS, fontSize: 30, color: MUTED, opacity: ease((frame - 50) / 40)}}>linyi.work/ZhenXun</div>
    </AbsoluteFill>
  );
};

const IMPORT = T(importRec);
const ASK = T(askRec);
const EVID = T(evidenceRec);
const REPLAY = T(replayRec);
const SHOT = T(shotRec);

type Piece = {len: number; el: (len: number) => React.ReactNode; sound?: boolean};
const PIECES: Piece[] = [
  {len: 200, el: (len) => <Line len={len} text="看教程，总会卡在某一步。" />},
  {len: 170, el: (len) => <Line len={len} text={<>帧寻，读懂一段视频的<span style={{borderBottom: `5px solid ${ACCENT}`}}>每一帧</span>。</>} small="画面 · 原声 · 画面文字" />},
  {len: 420, sound: true, el: (len) => <Window len={len} name="import" rec={IMPORT} from={markAt(IMPORT, 'analysing') - 0.5} to={markAt(IMPORT, 'ready') + 2} rate={2.4}
    focus={{x: 1700, y: 1050, zoom: 1.25}} caption="贴一个链接，它就开始读。" />},
  {len: 420, sound: true, el: (len) => <Window len={len} name="ask" rec={ASK} from={7} to={22.5} rate={2.2} focus={{x: 1950, y: 700, zoom: 1.5}} caption="问它，用你自己的话。" />},
  {len: 360, sound: true, el: (len) => <Window len={len} name="evidence" rec={EVID} from={11} to={20.5} rate={1.6} focus={{x: 2600, y: 500, zoom: 1.4}} caption="每句回答，都能回到原片的那一刻。" />},
  {len: 360, sound: true, el: (len) => <Window len={len} name="screenshot" rec={SHOT} from={14} to={27} rate={2.2} focus={{x: 1950, y: 700, zoom: 1.45}} caption="卡住了，发一张截图就行。" />},
  {len: 330, sound: true, el: (len) => <Window len={len} name="replay" rec={REPLAY} from={8} to={25} rate={3.1} focus={{x: 1900, y: 860, zoom: 1.4}} caption="拖一段，一帧一帧慢慢看。" />},
  {len: 330, el: (len) => <PhoneWindow len={len} />},
  {len: 300, el: (len) => <Close len={len} />},
];
export const PRODUCT_FRAMES = PIECES.reduce((n, p) => n + p.len, 0);
void FPS;

export const ProductFilm: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{background: CANVAS}}>
      {PIECES.map((p, i) => {
        const seq = (
          <Sequence key={i} from={at} durationInFrames={p.len}>
            {p.el(p.len)}
            {p.sound ? <Sfx name="soft" at={20} volume={0.2} /> : null}
          </Sequence>
        );
        at += p.len;
        return seq;
      })}
    </AbsoluteFill>
  );
};
