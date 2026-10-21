import React from 'react';
import {AbsoluteFill} from 'remotion';
import {TransitionSeries} from '@remotion/transitions';
import {BG} from './kit';
import {GREETING_ZHEN, OPENING} from './Opening';
import {LAST_CLICK, REST, VERSUS_X} from './Rest';
import {reveal, timing} from './transitions';

// The whole film, sixty seconds at 60 fps. The first 600 frames are the opening (it ends on the
// name and is also cut into the deck on its own). Scenes without a transition between them hand
// over by a shared element instead (the lockup's rule → the evidence columns).
const {Greeting, Stream, NameWall} = OPENING;
const {Evidence, Clicks, Screenshot, Giant, Burst, Versus, Speed, Flood, Snake, Wall, Finale} = REST;

type Step = {scene: React.FC; frames: number} | {via: Parameters<typeof reveal>[0]; frames: number};
const STEPS: Step[] = [
  {scene: Greeting, frames: 150},
  {via: {kind: 'zoom', ...GREETING_ZHEN}, frames: 24},
  {scene: Stream, frames: 150},
  {via: {kind: 'slashes', angle: 24}, frames: 24},
  {scene: NameWall, frames: 348},
  // 600 — the opening ends on the name
  {scene: Evidence, frames: 280},
  {via: {kind: 'blocks', seed: 1}, frames: 30},
  {scene: Clicks, frames: 260},
  {via: {kind: 'diamond', x: LAST_CLICK.x, y: LAST_CLICK.y}, frames: 28},
  {scene: Screenshot, frames: 300},
  {via: {kind: 'bands'}, frames: 30},
  {scene: Giant, frames: 300},
  {via: {kind: 'chevron'}, frames: 26},
  {scene: Burst, frames: 240},
  {via: {kind: 'zoom'}, frames: 22},
  {scene: Versus, frames: 220},
  {via: {kind: 'cross', ...VERSUS_X}, frames: 28},
  {scene: Speed, frames: 220},
  {via: {kind: 'slashes', angle: -24}, frames: 24},
  {scene: Flood, frames: 160},
  {via: {kind: 'plus'}, frames: 28},
  {scene: Snake, frames: 300},
  {via: {kind: 'blocks', seed: 2}, frames: 28},
  {scene: Wall, frames: 330},
  {via: {kind: 'diamond'}, frames: 26},
  {scene: Finale, frames: 660},
];

export const PV_FRAMES = STEPS.reduce((n, s) => n + ('scene' in s ? s.frames : -s.frames), 0);
export const OPENING_FRAMES = 600;

export const PV: React.FC = () => (
  <AbsoluteFill style={{background: BG}}>
    <TransitionSeries>
      {STEPS.map((s, i) => ('scene' in s
        ? <TransitionSeries.Sequence key={i} durationInFrames={s.frames}><s.scene /></TransitionSeries.Sequence>
        : <TransitionSeries.Transition key={i} timing={timing(s.frames)} presentation={reveal(s.via)} />))}
    </TransitionSeries>
  </AbsoluteFill>
);
