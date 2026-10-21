import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {INK, LIME, PAPER} from './theme';

// Marathon-style cuts: whole-frame colour flashes a few frames long, a lime block pushed across
// on a diagonal, and a halftone dot field under titles.
export const Flash: React.FC<{at: number; colors?: string[]}> = ({at, colors = [PAPER, LIME, INK]}) => {
  const i = useCurrentFrame() - at;
  if (i < 0 || i >= colors.length * 2) return null;
  return <AbsoluteFill style={{background: colors[Math.floor(i / 2)]}} />;
};

export const DiagonalWipe: React.FC<{at: number; frames?: number; color?: string}> = ({at, frames = 18, color = LIME}) => {
  const k = (useCurrentFrame() - at) / frames;
  if (k < 0 || k > 1) return null;
  const head = k * 160 - 30; // % across, the band leans 30%
  return <AbsoluteFill style={{background: color, clipPath: `polygon(${head - 40}% 0, ${head + 10}% 0, ${head - 20}% 100%, ${head - 70}% 100%)`}} />;
};

export const Halftone: React.FC<{opacity?: number; size?: number; color?: string}> = ({opacity = 0.18, size = 14, color = INK}) => (
  <AbsoluteFill style={{opacity, backgroundImage: `radial-gradient(${color} 28%, transparent 30%)`, backgroundSize: `${size}px ${size}px`,
    maskImage: 'linear-gradient(90deg, black, transparent 55%)', WebkitMaskImage: 'linear-gradient(90deg, black, transparent 55%)'}} />
);
