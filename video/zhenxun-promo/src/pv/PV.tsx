import React from 'react';
import {AbsoluteFill} from 'remotion';
import {TransitionSeries} from '@remotion/transitions';
import {Evidence} from './Evidence';
import {Hud} from './Hud';
import {BG, Grain, INK, LIME} from './kit';
import {OPENING} from './Opening';
import {Pipeline} from './Pipeline';
import {LAST_CLICK, REST, versusX} from './Rest';
import {reveal, timing} from './transitions';

// The whole film, sixty seconds at 60 fps. The first 600 frames are the opening (one shot, ending
// on the name; also cut into the deck on its own). From the click scene to the slogan the film is
// on the night side; the slogan folds into a line that opens back onto paper for the end.
const {Opening} = OPENING;
const {Clicks, Screenshot, Giant, Burst, Versus, Speed, Snake, Wall, Finale} = REST;

type Via = Parameters<typeof reveal>[0];
/** Each scene, the frame by which the next is fully in, and how it arrives (none: a match cut). */
const PLAN: {scene: React.FC; until: number; via?: Via; over?: number}[] = [
  {scene: Opening, until: 600},
  {scene: Evidence, until: 900, via: {kind: 'blocks', seed: 1, tint: INK}, over: 30},
  {scene: Pipeline, until: 1440, via: {kind: 'bars', tint: LIME, seed: 9}, over: 32},
  {scene: Clicks, until: 1660, via: {kind: 'diamond', x: LAST_CLICK.x, y: LAST_CLICK.y}, over: 28},
  {scene: Screenshot, until: 1970, via: {kind: 'slashes', angle: -24, tint: LIME}, over: 26},
  {scene: Giant, until: 2310, via: {kind: 'chevron'}, over: 26},
  {scene: Burst, until: 2490, via: {kind: 'zoom'}, over: 22},
  {scene: Versus, until: 2680, via: {kind: 'cross', at: versusX}, over: 28},
  {scene: Speed, until: 2850, via: {kind: 'plus'}, over: 24},
  {scene: Snake, until: 3020, via: {kind: 'blocks', seed: 2, tint: LIME}, over: 28},
  {scene: Wall, until: 3194, via: {kind: 'diamond'}, over: 26},
  {scene: Finale, until: 3600},
];

export const PV_FRAMES = 3600;
export const OPENING_FRAMES = 600;
/** The night side, for the HUD drawn over everything. */
export const NIGHT_RANGE: [number, number] = [1424, 3390];

const steps = () => {
  let fullyIn = 0;
  let arriving = 0;
  return PLAN.map((p) => {
    const over = p.via ? p.over ?? 24 : 0;
    const frames = p.until - fullyIn + arriving;
    fullyIn = p.until;
    arriving = over;
    return {scene: p.scene, frames, via: p.via, over};
  });
};

export const PV: React.FC = () => (
  <AbsoluteFill style={{background: BG}}>
    <TransitionSeries>
      {steps().flatMap((s, i) => [
        <TransitionSeries.Sequence key={`s${i}`} durationInFrames={s.frames}><s.scene /></TransitionSeries.Sequence>,
        ...(s.via ? [<TransitionSeries.Transition key={`t${i}`} timing={timing(s.over)} presentation={reveal(s.via)} />] : []),
      ])}
    </TransitionSeries>
    <Hud night={NIGHT_RANGE} />
    <Grain />
  </AbsoluteFill>
);
