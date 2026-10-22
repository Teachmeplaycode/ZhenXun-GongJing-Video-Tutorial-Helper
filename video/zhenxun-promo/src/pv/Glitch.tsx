import React from 'react';

// The homepage model's signal interruption (front/src/lib/useModelGlitch.js + postPass.js), made
// deterministic: the same looks (jitter / warp / slice / tear: wave warp, torn bands, RGB split,
// displaced strips, interlace) in the same stuttering bursts of short hard-cut frames, starting
// at given frames instead of at random times. Drawn as an SVG filter over the layer it wraps.

type Look = {warp: number; slice: number; tear: number; rgb: number; blocks: number; scan: number};
const LOOKS: Record<string, Look> = {
  jitter: {warp: 0.003, slice: 0.35, tear: 0.02, rgb: 3, blocks: 0, scan: 0.6},
  warp: {warp: 0.012, slice: 0.15, tear: 0.015, rgb: 4, blocks: 0, scan: 0.5},
  slice: {warp: 0.005, slice: 1, tear: 0.06, rgb: 6, blocks: 0.2, scan: 1},
  tear: {warp: 0.008, slice: 1, tear: 0.1, rgb: 8, blocks: 0.4, scan: 1},
};
// [look, ms] — as on the site; 'clean' gaps between hits sell the rhythm
const BURSTS: [string, number][][] = [
  [['jitter', 50], ['clean', 40], ['warp', 90], ['slice', 50], ['clean', 50], ['jitter', 40]],
  [['tear', 60], ['warp', 110], ['slice', 40], ['clean', 60], ['jitter', 50]],
  [['warp', 70], ['clean', 40], ['slice', 50], ['tear', 50], ['clean', 50], ['warp', 60]],
];

/** The look at `frame` given bursts starting at `starts` (frames, 60 fps), or null when clean. */
export const glitchAt = (frame: number, starts: number[], fps = 60): (Look & {seed: number}) | null => {
  for (let b = 0; b < starts.length; b += 1) {
    let t = starts[b];
    for (const [look, ms] of BURSTS[b % BURSTS.length]) {
      const d = Math.max(1, Math.round((ms / 1000) * fps));
      if (frame >= t && frame < t + d) return look === 'clean' ? null : {...LOOKS[look], seed: (b * 17 + t) % 97};
      t += d;
    }
  }
  return null;
};

/** Wraps a layer; while a burst is on, the layer is torn, warped and split. */
export const Glitch: React.FC<{frame: number; starts: number[]; id: string; children: React.ReactNode}> = ({frame, starts, id, children}) => {
  const g = glitchAt(frame, starts);
  if (!g) return <>{children}</>;
  const fid = `zx-glitch-${id}-${frame}`;
  return (
    <>
      <svg width={0} height={0} style={{position: 'absolute'}}>
        <filter id={fid} x="-5%" y="-5%" width="110%" height="110%" colorInterpolationFilters="sRGB">
          {/* torn bands: noise varying only down the frame, quantised so most rows stay put and a
              few bands jump sideways as whole strips (not a wave) */}
          <feTurbulence type="fractalNoise" baseFrequency={`0 ${0.012 + g.slice * 0.02}`} numOctaves={1} seed={g.seed} result="noise" />
          <feComponentTransfer in="noise" result="bands">
            <feFuncR type="discrete" tableValues={g.slice > 0.5 ? '0.5 0.5 0.5 0.18 0.5 0.5 0.82 0.5 0.5 0.35' : '0.5 0.5 0.5 0.5 0.3 0.5 0.5 0.5 0.7 0.5'} />
            <feFuncA type="discrete" tableValues="0.5" />
          </feComponentTransfer>
          <feDisplacementMap in="SourceGraphic" in2="bands" scale={1920 * g.tear} xChannelSelector="R" yChannelSelector="A" result="torn" />
          {/* RGB split: red one way, green+blue the other, added back together */}
          <feOffset in="torn" dx={g.rgb} result="ro" />
          <feColorMatrix in="ro" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
          <feOffset in="torn" dx={-g.rgb} result="gbo" />
          <feColorMatrix in="gbo" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0" result="gb" />
          <feComposite in="r" in2="gb" operator="arithmetic" k1={0} k2={1} k3={1} k4={0} />
        </filter>
      </svg>
      <div style={{position: 'absolute', inset: 0, filter: `url(#${fid})`}}>{children}</div>
      {/* interlace */}
      {g.scan > 0 ? <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.12 * g.scan,
        background: 'repeating-linear-gradient(0deg, rgba(26,26,26,0.5) 0 1px, transparent 1px 4px)'}} /> : null}
    </>
  );
};
