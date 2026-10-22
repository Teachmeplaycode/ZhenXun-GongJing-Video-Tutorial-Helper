import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {CONSOLE, INK, INK2, INK3, LIME, PAPER, PIXEL, SC, stepped} from '../pv/kit';
import {Pose, Snake, useFreeContext} from './Snake3D';

// The character sheet for the ad's lead: the mascot snake drawn as anime (三渲二) — four turns and
// six expressions on one sheet (one WebGL canvas), and an 8-second loop of it acting. Everything
// moves on twos (12 fps), the limited animation of TV anime. A white paper edge and one drop shadow
// cut it out like a paper puppet, as the collage world will need.

const UNIT = 43.4; // px per world unit at the picture plane (camera fov 22° at z 64)
/** A white paper edge around whatever is drawn, then its shadow: chained drop-shadows. */
export const PAPER_EDGE = 'drop-shadow(5px 0 0 #fff) drop-shadow(-5px 0 0 #fff) drop-shadow(0 5px 0 #fff) drop-shadow(0 -5px 0 #fff) drop-shadow(10px 12px 0 rgba(26,26,26,0.16))';

const TURNS: {label: string; turn: number}[] = [
  {label: '正面 3/4', turn: 0},
  {label: '侧面', turn: -1.2},
  {label: '背面 3/4', turn: 2.5},
  {label: '另一侧', turn: 1.05},
];
const MOODS: {label: string; pose: (t: number) => Pose}[] = [
  {label: '待机', pose: () => ({})},
  {label: '眨眼', pose: (t) => ({blink: Math.max(0, 1 - Math.abs(((t * 1.2) % 2) - 1) * 4)})},
  {label: '疑惑', pose: (t) => ({tilt: 0.8 + Math.sin(t * 2) * 0.1, sway: -0.3})},
  {label: '探头看', pose: (t) => ({look: 0.7, rise: 1, nod: 0.25 + Math.sin(t * 2) * 0.1})},
  {label: '尾巴指', pose: (t) => ({lift: 0.9 + Math.sin(t * 3) * 0.08, look: -0.4})},
  {label: '开心', pose: () => ({happy: 1, blink: 0.55})},
];

const Labels: React.FC<{items: {label: string; x: number; y: number}[]}> = ({items}) => (
  <>
    {items.map((it) => (
      <div key={it.label + it.x} style={{position: 'absolute', left: it.x - 120, width: 240, top: it.y, textAlign: 'center', fontFamily: PIXEL, fontSize: 30, color: INK}}>{it.label}</div>
    ))}
  </>
);

export const SnakeSheet: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = stepped(frame, fps, 12) / 12; // on twos
  const onCreated = useFreeContext();
  const turnX = (i: number) => (i - 1.5) * 9.6;
  const moodX = (i: number) => (i - 2.5) * 7.0;
  return (
    <AbsoluteFill style={{background: PAPER}}>
      <div style={{position: 'absolute', left: 80, top: 52, display: 'flex', alignItems: 'baseline', gap: 24}}>
        <span style={{fontFamily: SC, fontWeight: 900, fontSize: 64, color: INK}}>角色设定 · 小蛇</span>
        <span style={{fontFamily: CONSOLE, fontSize: 32, color: INK2}}>三渲二 · 一拍二 12fps · 3 级明暗 + 荧光绿轮廓光 + 墨线</span>
      </div>
      <div style={{position: 'absolute', left: 80, top: 140, width: 1760, height: 2, background: INK}} />
      <div style={{position: 'absolute', left: 80, top: 580, width: 1760, height: 1, background: INK3}} />
      <AbsoluteFill style={{filter: PAPER_EDGE}}>
        <ThreeCanvas width={width} height={height} camera={{fov: 22, position: [0, 0, 64], near: 1, far: 400}}
          gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}} onCreated={onCreated}>
          {TURNS.map((v, i) => <Snake key={v.label} t={t} pose={{turn: v.turn}} position={[turnX(i), 5.6, 0]} scale={0.46} />)}
          {MOODS.map((m, i) => <Snake key={m.label} t={t + i * 0.7} pose={m.pose(t)} position={[moodX(i), -5.2, 0]} scale={0.4} />)}
        </ThreeCanvas>
      </AbsoluteFill>
      <Labels items={TURNS.map((v, i) => ({label: v.label, x: 960 + turnX(i) * UNIT, y: 520}))} />
      <Labels items={MOODS.map((m, i) => ({label: m.label, x: 960 + moodX(i) * UNIT, y: 990}))} />
      <div style={{position: 'absolute', right: 80, top: 86, display: 'flex', gap: 10, alignItems: 'center', fontFamily: CONSOLE, fontSize: 26, color: INK2}}>
        {['#141414', '#262626', '#4A4A4A', LIME].map((c) => <span key={c} style={{width: 30, height: 30, background: c, border: `1px solid ${INK3}`}} />)}
        <span>暗 · 中 · 亮 · 轮廓光</span>
      </div>
    </AbsoluteFill>
  );
};

/** Eight seconds of the snake acting, one big, on paper. */
export const SnakeLoop: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = stepped(frame, fps, 12) / 12;
  const onCreated = useFreeContext();
  // a little performance: rest, blink, a curious tilt, a look, point with the tail, happy, rest
  const beat = (a: number, b: number) => Math.max(0, Math.min(1, (t - a) / 0.35)) * Math.max(0, Math.min(1, (b - t) / 0.35));
  const pose: Pose = {
    blink: Math.max(0, 1 - Math.abs(t - 1.2) * 8) + Math.max(0, 1 - Math.abs(t - 6.6) * 8),
    tilt: beat(1.6, 3.0) * 0.85,
    look: beat(3.0, 4.3) * 0.7,
    nod: beat(3.0, 4.3) * 0.3,
    lift: beat(4.3, 5.7),
    happy: beat(5.7, 7.2),
    turn: Math.sin(t * 0.8) * 0.25,
  };
  const label = t < 1.6 ? '待机 · 眨眼' : t < 3 ? '疑惑' : t < 4.3 ? '探头看' : t < 5.7 ? '尾巴指' : t < 7.2 ? '开心' : '待机';
  return (
    <AbsoluteFill style={{background: PAPER}}>
      <AbsoluteFill style={{filter: PAPER_EDGE}}>
        <ThreeCanvas width={width} height={height} camera={{fov: 22, position: [0, 0, 64], near: 1, far: 400}}
          gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}} onCreated={onCreated}>
          <Snake t={t} pose={pose} position={[0, -0.6, 0]} scale={1.05} />
        </ThreeCanvas>
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 80, bottom: 70, fontFamily: PIXEL, fontSize: 48, color: INK}}>{label}</div>
      <div style={{position: 'absolute', right: 80, bottom: 76, fontFamily: CONSOLE, fontSize: 32, color: INK2}}>一拍二 · 12fps</div>
    </AbsoluteFill>
  );
};
