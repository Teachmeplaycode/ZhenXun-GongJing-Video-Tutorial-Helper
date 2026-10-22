import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {CONSOLE, INK, INK2, LIME, PAPER, PIXEL, SC, stepped} from '../pv/kit';
import {CutText, Halftone, KRAFT, Paper, Photo, Pin, Stamp, Tape, Thread} from './paper';
import {PAPER_EDGE} from './SnakeSheet';
import {Snake, useFreeContext} from './Snake3D';

// The style frame for the ad: the evidence board of 22–32 s. A question on a torn slip, the answer
// on a card with its evidence stamped on it, the keyframes it rests on pinned and taped to the
// right, red thread from each stamp to its frame, and the snake pointing with its tail.

const frameImg = (i: number) => staticFile(`ad/frames/vlookup/${String(i).padStart(2, '0')}.jpg`);

export const StyleFrame: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = stepped(frame, fps, 12) / 12;
  const onCreated = useFreeContext();
  const look = Math.min(1, Math.max(0, (t - 1.2) / 0.5));
  return (
    <AbsoluteFill style={{background: PAPER, overflow: 'hidden'}}>
      {/* the desk: a kraft sheet, halftone, a lime strip */}
      <Paper x={-60} y={40} w={1060} h={720} rot={-3} color={KRAFT} seed={2} at={0} />
      <Halftone x={1240} y={760} w={560} h={300} rot={-4} />
      <Paper x={-40} y={880} w={1240} h={110} rot={2} color={LIME} seed={9} at={4} />
      {/* the question */}
      <Paper x={110} y={110} w={780} h={150} rot={-2} seed={4} at={8}>
        <div style={{position: 'absolute', left: 36, top: 26, fontFamily: CONSOLE, fontSize: 30, color: INK2}}>提问</div>
        <div style={{position: 'absolute', left: 36, top: 66, fontFamily: SC, fontWeight: 500, fontSize: 40, color: INK}}>第二参数框选后，按哪个键做绝对引用？</div>
      </Paper>
      {/* the answer card */}
      <Paper x={150} y={320} w={780} h={420} rot={1.5} torn={false} color="#FFFFFF" seed={6} at={20}>
        <div style={{position: 'absolute', left: 44, top: 40, fontFamily: SC, fontWeight: 900, fontSize: 72, color: INK}}>按 F4 键做绝对引用。</div>
        {['1  框选第二参数的数据范围', '2  按 F4 → $B$1:$F$19', '3  往下填充，范围不跑偏'].map((l, i) => (
          <div key={i} style={{position: 'absolute', left: 48, top: 160 + i * 58, fontFamily: PIXEL, fontSize: 40, color: INK}}>{l}</div>
        ))}
      </Paper>
      <Tape x={540} y={326} w={180} rot={-4} at={26} />
      <Stamp x={330} y={690} text="画面 01:32" rot={-7} at={44} />
      <Stamp x={640} y={712} text="原声 01:54" rot={4} at={52} color="#3A6B2A" seed={8} />
      {/* the keyframes the answer rests on */}
      <Photo x={1040} y={110} w={440} h={276} rot={3} at={30} seed={12}><Img src={frameImg(20)} style={{width: '100%', height: '100%', objectFit: 'cover'}} /></Photo>
      <Pin x={1262} y={128} at={38} />
      <Photo x={1420} y={300} w={420} h={264} rot={-4} at={36} seed={13}><Img src={frameImg(25)} style={{width: '100%', height: '100%', objectFit: 'cover'}} /></Photo>
      <Tape x={1630} y={306} w={140} rot={6} at={42} />
      <Photo x={1080} y={500} w={380} h={240} rot={-2} at={42} seed={14}><Img src={frameImg(27)} style={{width: '100%', height: '100%', objectFit: 'cover'}} /></Photo>
      <Pin x={1270} y={516} color="#FFFFFF" at={48} />
      {[['01:32', 1100, 400], ['01:54', 1470, 586], ['02:03', 1110, 762]].map(([tc, x, y]) => (
        <div key={tc as string} style={{position: 'absolute', left: x as number, top: (y as number) - 6, fontFamily: CONSOLE, fontSize: 32, background: INK, color: PAPER, padding: '0 10px',
          opacity: frame > 50 ? 1 : 0, zIndex: 57}}>{tc}</div>
      ))}
      <Thread a={[330, 690]} b={[1262, 128]} at={64} />
      <Thread a={[640, 712]} b={[1630, 306]} at={76} />
      {/* the snake, pointing at the frames with its tail */}
      <AbsoluteFill style={{filter: PAPER_EDGE, zIndex: 70, opacity: t > 0.8 ? 1 : 0}}>
        <ThreeCanvas width={width} height={height} camera={{fov: 22, position: [0, 0, 64], near: 1, far: 400}}
          gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}} onCreated={onCreated}>
          <Snake t={t} pose={{lift: look, look: -0.5 * look, tilt: 0.2, turn: -0.35}} position={[15.8, -6.6, 0]} scale={0.52} />
        </ThreeCanvas>
      </AbsoluteFill>
      <CutText x={96} y={790} text="每句都有出处" size={70} at={90} />
    </AbsoluteFill>
  );
};
