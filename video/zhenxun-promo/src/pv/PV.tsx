import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {BG} from './kit';
import {Opening} from './Opening';
import {Rest, REST_FRAMES} from './Rest';

// The whole film: the ten-second opening (it ends on the name), then the rest — sixty seconds.
const OPENING_FRAMES = 600;
export const PV_FRAMES = OPENING_FRAMES + REST_FRAMES;

export const PV: React.FC = () => (
  <AbsoluteFill style={{background: BG}}>
    <Sequence durationInFrames={OPENING_FRAMES}><Opening /></Sequence>
    <Sequence from={OPENING_FRAMES}><Rest /></Sequence>
  </AbsoluteFill>
);
