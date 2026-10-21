import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {cameraAt, frameTransform, Key, Track} from './camera';
import {LIME} from './theme';

// One shot of a recording: from source second `from` at `rate`, the camera following `keys`
// (source-time keys, recording pixels), and a lime ripple where the mouse clicked.
export const Shot: React.FC<{name: string; rec: Track; from: number; rate?: number; keys: Key[]}> = ({name, rec, from, rate = 1, keys}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = from + (frame / fps) * rate; // source second shown now
  const cam = cameraAt(keys, t);
  const transform = frameTransform(cam, rec.width, rec.height, width, height);
  const scale = (width / rec.width) * Math.max(1, cam.zoom);
  const halfW = width / 2 / scale;
  const halfH = height / 2 / scale;
  const cx = Math.min(rec.width - halfW, Math.max(halfW, cam.x));
  const cy = Math.min(rec.height - halfH, Math.max(halfH, cam.y));
  const ripples = rec.track.filter((e) => e.type === 'click' && t >= e.t && t - e.t < 0.6);
  return (
    <AbsoluteFill style={{overflow: 'hidden', background: '#F5F3EF'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: rec.width, height: rec.height, transformOrigin: '0 0', transform}}>
        <OffthreadVideo src={staticFile(`rec/${name}.mp4`)} startFrom={Math.round(from * fps)} playbackRate={rate} muted
          style={{width: rec.width, height: rec.height}} />
      </div>
      {ripples.map((e) => {
        const k = (t - e.t) / 0.6;
        const x = (e.x - cx) * scale + width / 2;
        const y = (e.y - cy) * scale + height / 2;
        const r = 18 + k * 90;
        return <div key={e.t} style={{position: 'absolute', left: x - r, top: y - r, width: r * 2, height: r * 2, borderRadius: '50%',
          border: `${6 * (1 - k) + 1}px solid ${LIME}`, opacity: 1 - k}} />;
      })}
    </AbsoluteFill>
  );
};
