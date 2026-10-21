import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {CONSOLE, hash, INK, INK3, LIME} from './kit';

// A HUD over the whole film: corner brackets, a progress hairline, a scrolling frame ruler, a
// turning dashed ring and a shifting barcode. Quiet (it frames the picture, it isn't the picture).
export const Hud: React.FC<{opacity?: number}> = ({opacity = 0.55}) => {
  const frame = useCurrentFrame();
  const {width, height, durationInFrames} = useVideoConfig();
  const m = 34; // margin
  const corner = (x: number, y: number, sx: number, sy: number) => (
    <path key={`${x}-${y}`} d={`M${x} ${y + sy * 34}V${y}H${x + sx * 34}`} fill="none" stroke={INK} strokeWidth={2.5} />
  );
  const shift = (frame * 3) % 24;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', opacity}}>
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        {corner(m, m, 1, 1)}{corner(width - m, m, -1, 1)}{corner(m, height - m, 1, -1)}{corner(width - m, height - m, -1, -1)}
        {/* progress hairline along the top */}
        <rect x={m + 50} y={m - 1} width={(width - 2 * m - 100) * (frame / durationInFrames)} height={2} fill={INK} />
        {/* the ruler along the bottom, scrolling */}
        {Array.from({length: 46}, (_, i) => {
          const x = 300 + i * 24 - shift;
          const major = (i + Math.floor((frame * 3) / 24)) % 5 === 0;
          return <rect key={i} x={x} y={height - m - (major ? 16 : 8)} width={2} height={major ? 16 : 8} fill={INK} opacity={major ? 0.7 : 0.35} />;
        })}
        {/* the turning ring, top right */}
        <g transform={`translate(${width - m - 70} ${m + 70}) rotate(${frame * 2.2})`}>
          <circle r={26} fill="none" stroke={INK3} strokeWidth={2} strokeDasharray="6 7" />
          <path d="M0 -36V-30M0 30V36M-36 0H-30M30 0H36" stroke={INK} strokeWidth={3} />
          <circle r={5} fill={LIME} />
        </g>
        {/* barcode, bottom right */}
        {Array.from({length: 22}, (_, i) => (
          <rect key={i} x={width - m - 260 + i * 9} y={height - m - 40} width={hash(i, Math.floor(frame / 6)) < 0.5 ? 2 : 5} height={22} fill={INK} opacity={0.6} />
        ))}
      </svg>
      <div style={{position: 'absolute', left: 300 + 46 * 24 + 12, bottom: m - 6, fontFamily: CONSOLE, fontSize: 30, color: INK}}>
        {String(frame).padStart(4, '0')}
      </div>
    </AbsoluteFill>
  );
};
