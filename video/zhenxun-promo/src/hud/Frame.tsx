import React from 'react';
import {useCurrentFrame} from 'remotion';
import {FPS, INK, LIME, MONO} from '../theme';

// The HUD laid over every shot: corner brackets, a running timecode, a barcode strip and a
// crosshair; faint by default, lit by `flare` (0–1) at emphasis. Drawn from the frame number.
export const HudFrame: React.FC<{flare?: number; tone?: 'ink' | 'paper'}> = ({flare = 0, tone = 'ink'}) => {
  const frame = useCurrentFrame();
  const col = tone === 'ink' ? INK : '#F5F3EF';
  const s = frame / FPS;
  const tc = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}:${String(frame % FPS).padStart(2, '0')}`;
  const op = 0.55 + 0.45 * flare;
  const corner = (style: React.CSSProperties) => (
    <div style={{position: 'absolute', width: 54, height: 54, borderColor: col, borderStyle: 'solid', borderWidth: 0, opacity: op, ...style}} />
  );
  const bars = Array.from({length: 22}, (_, i) => ((i * 7 + Math.floor(frame / 5)) % 5) + 1);
  return (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', fontFamily: MONO, color: col}}>
      {corner({left: 40, top: 40, borderLeftWidth: 3, borderTopWidth: 3})}
      {corner({right: 40, top: 40, borderRightWidth: 3, borderTopWidth: 3})}
      {corner({left: 40, bottom: 40, borderLeftWidth: 3, borderBottomWidth: 3})}
      {corner({right: 40, bottom: 40, borderRightWidth: 3, borderBottomWidth: 3})}
      <div style={{position: 'absolute', right: 112, top: 50, fontSize: 22, letterSpacing: 2, opacity: op}}>◆ {tc}</div>
      <div style={{position: 'absolute', left: 112, bottom: 52, display: 'flex', gap: 3, alignItems: 'flex-end', opacity: 0.5 + 0.5 * flare}}>
        {bars.map((h, i) => <span key={i} style={{width: h > 3 ? 4 : 2, height: 26, background: i % 6 === 0 ? LIME : col}} />)}
      </div>
      <div style={{position: 'absolute', right: 112, bottom: 46, fontSize: 24, letterSpacing: 6, opacity: op}}>{'>>>'}</div>
    </div>
  );
};
