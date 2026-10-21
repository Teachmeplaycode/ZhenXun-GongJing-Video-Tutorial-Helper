import React from 'react';
import {useCurrentFrame} from 'remotion';
import {HEAVY, INK, LIME, PAPER} from './theme';

// A heavy Chinese title stamped in piece by piece on a sticker block (stepped at 12 fps, the
// Marathon judder), with geometric marks around it. `at`: the frame it starts, `size` in px.
export const Caption: React.FC<{text: string; at: number; mark?: string; sticker?: 'ink' | 'lime'; size?: number;
  x?: number; y?: number}> = ({text, at, mark = '>>>', sticker = 'ink', size = 64, x = 120, y = 860}) => {
  const frame = useCurrentFrame();
  const step = Math.floor((frame - at) / 5); // 12 fps steps at 60 fps
  if (step < 0) return null;
  const shown = Array.from(text).slice(0, Math.max(0, step * 2));
  const bg = sticker === 'ink' ? INK : LIME;
  const fg = sticker === 'ink' ? PAPER : INK;
  const reveal = Math.min(1, step / 2); // the block slides open over the first steps
  return (
    <div style={{position: 'absolute', left: x, top: y, display: 'flex', alignItems: 'center', gap: 22}}>
      <span style={{fontFamily: HEAVY, fontWeight: 900, fontSize: size * 0.5, color: bg, letterSpacing: 2}}>{mark}</span>
      <span style={{fontFamily: HEAVY, fontWeight: 900, fontSize: size, lineHeight: 1.15, color: fg, background: bg,
        padding: `${size * 0.08}px ${size * 0.28}px`, clipPath: `inset(0 ${100 - reveal * 100}% 0 0)`, whiteSpace: 'nowrap'}}>
        {shown.join('')}
        <span style={{opacity: shown.length < Array.from(text).length ? 1 : 0, color: sticker === 'ink' ? LIME : INK}}>▮</span>
      </span>
    </div>
  );
};

/** A chapter tag: number and marks only, no words. */
export const Tag: React.FC<{label: string; at: number; x?: number; y?: number}> = ({label, at, x = 120, y = 120}) => {
  const frame = useCurrentFrame();
  const step = Math.floor((frame - at) / 5);
  if (step < 0) return null;
  return (
    <div style={{position: 'absolute', left: x, top: y, fontFamily: HEAVY, fontWeight: 900, fontSize: 40, color: INK,
      letterSpacing: 4, display: 'flex', gap: 14, alignItems: 'center'}}>
      <span style={{background: LIME, padding: '2px 14px'}}>{label.slice(0, Math.min(label.length, step + 1))}</span>
    </div>
  );
};
