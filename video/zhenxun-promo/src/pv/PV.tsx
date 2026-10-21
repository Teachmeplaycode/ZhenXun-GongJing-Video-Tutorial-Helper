import React from 'react';
import {AbsoluteFill, Audio, interpolate, staticFile, useVideoConfig} from 'remotion';
import {TransitionSeries} from '@remotion/transitions';
import {Hud} from './Hud';
import {BG} from './kit';
import {greetingZhen, OPENING} from './Opening';
import {Pipeline} from './Pipeline';
import {LAST_CLICK, REST, versusX} from './Rest';
import {reveal, timing} from './transitions';

// The whole film: sixty seconds at 60 fps, cut to a 128 BPM grid (a bar is 112.5 frames) so the
// music's downbeats land on the cuts. The first 600 frames are the opening, which ends on the name
// and is also cut into the deck on its own.
export const BPM = 128;
export const BAR = (60 / BPM) * 4 * 60; // frames
const {Greeting, Stream, NameWall} = OPENING;
const {Evidence, Clicks, Screenshot, Giant, Burst, Versus, Speed, Snake, Wall, Finale} = REST;

type Via = Parameters<typeof reveal>[0];
/** Each scene, and when the next one is fully in (in bars), and how it arrives (none: a match cut). */
const PLAN: {scene: React.FC; until: number; via?: Via; over?: number}[] = [
  {scene: Greeting, until: 1.5, via: {kind: 'zoom', at: greetingZhen}, over: 24},
  {scene: Stream, until: 2.5, via: {kind: 'slashes', angle: 24}, over: 24},
  {scene: NameWall, until: 600 / BAR}, // the title lands on bar 4; the opening ends at 10 s
  {scene: Evidence, until: 7.5, via: {kind: 'blocks', seed: 1}, over: 30},
  {scene: Pipeline, until: 12, via: {kind: 'bands'}, over: 30},
  {scene: Clicks, until: 14, via: {kind: 'diamond', x: LAST_CLICK.x, y: LAST_CLICK.y}, over: 28},
  {scene: Screenshot, until: 16.5, via: {kind: 'slashes', angle: -24}, over: 26},
  {scene: Giant, until: 19.5, via: {kind: 'chevron'}, over: 26},
  {scene: Burst, until: 21, via: {kind: 'zoom'}, over: 22},
  {scene: Versus, until: 22.5, via: {kind: 'cross', at: versusX}, over: 28},
  {scene: Speed, until: 24, via: {kind: 'plus'}, over: 24},
  {scene: Snake, until: 25.5, via: {kind: 'blocks', seed: 2}, over: 28},
  {scene: Wall, until: 27.5, via: {kind: 'diamond'}, over: 26},
  {scene: Finale, until: 32},
];

/** When each scene is fully on screen (frames): the cuts the music hits. */
export const CUTS = PLAN.slice(0, -1).map((p) => Math.round(p.until * BAR));
export const PV_FRAMES = Math.round(32 * BAR);
export const OPENING_FRAMES = 600;

const steps = () => {
  let fullyIn = 0; // when the current scene is fully on screen
  let arriving = 0; // frames the current scene spent arriving
  return PLAN.map((p, i) => {
    const cut = i === PLAN.length - 1 ? PV_FRAMES : Math.round(p.until * BAR);
    const over = p.via ? p.over ?? 24 : 0;
    // a scene starts as the transition into it starts and ends when the one out of it ends
    const frames = cut - fullyIn + arriving;
    fullyIn = cut;
    arriving = over;
    return {scene: p.scene, frames, via: p.via, over};
  });
};

/** The score (music/score.js, rendered by music/render.mjs), cut to the same bars; faded out at
 *  the end of whatever is being rendered (the ten-second opening ends mid-phrase). */
const Music: React.FC = () => {
  const {durationInFrames} = useVideoConfig();
  return <Audio src={staticFile('music/zhenxun-pv.wav')} volume={(f) => 0.5 * interpolate(f, [durationInFrames - 40, durationInFrames - 2], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />;
};

export const PV: React.FC = () => (
  <AbsoluteFill style={{background: BG}}>
    <Music />
    <TransitionSeries>
      {steps().flatMap((s, i) => [
        <TransitionSeries.Sequence key={`s${i}`} durationInFrames={s.frames}><s.scene /></TransitionSeries.Sequence>,
        ...(s.via ? [<TransitionSeries.Transition key={`t${i}`} timing={timing(s.over)} presentation={reveal(s.via)} />] : []),
      ])}
    </TransitionSeries>
    <Hud />
  </AbsoluteFill>
);
