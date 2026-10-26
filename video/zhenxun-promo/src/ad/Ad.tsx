import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {cameraAt, frameTransform, Key, Track} from '../camera';
import {follow, markAt} from '../films/follow';
import {CONSOLE, CREAM, DISPLAY, hash, INK, INK2, LIME, NIGHT, PAPER, PIXEL, SC, Sfx} from '../pv/kit';
import {CutText, Halftone, KRAFT, Paper, Photo, Pin, RED, Stamp, Tape, Thread, useStep} from './paper';
import {PAPER_EDGE} from './SnakeSheet';
import {ThreeCanvas} from '@remotion/three';
import {Pose, Snake, useFreeContext} from './Snake3D';
import {BLENDER, LINK, ROWS, STEPS, STUCK, TUTORIALS} from './data';
import stepsRec from '../../public/rec/steps.json';
import evidenceRec from '../../public/rec/evidence.json';
import compareRec from '../../public/rec/compare.json';

// The 60-second ad, a paper collage told in one take: seven boards laid out on one long desk and the
// camera gliding from each to the next while the next one's pieces are already landing. Paper moves on
// twelve steps a second like stop motion; the screen recordings inside the photos play smoothly, their
// own camera following the mouse. The story is the product's: stuck on a tutorial → its step cards →
// a screenshot says which step you're on and opens the original there → several tutorials lined up →
// 「平台的总结帮你看完，帧寻帮你照着做完」. The first ten seconds stand alone and end on the name.
// Sound effects only.

export const AD_FPS = 60;
export const AD_FRAMES = 60 * AD_FPS;
export const AD_OPENING = 10 * AD_FPS;

const W = 1920;
const H = 1080;
const GAP = 2160; // boards' spacing on the desk
const MOVE = 40; // frames the camera takes from one board to the next
const LEAD = 26; // a board starts landing this many frames before the camera arrives

// Boards: where they lie on the desk and when the camera reaches them.
const BOARDS: {at: number; x: number; y: number; rot: number; lead?: number}[] = [
  {at: 0, x: 0, y: 0, rot: 0},
  {at: 330, x: GAP, y: -180, rot: -1.2},
  {at: 600, x: GAP * 2, y: 40, rot: 0.8},
  {at: 1320, x: GAP * 3, y: -120, rot: -0.6},
  {at: 2160, x: GAP * 4, y: 60, rot: 0.9},
  {at: 2880, x: GAP * 5, y: -160, rot: -0.8, lead: MOVE + 8}, // the dark sheet is down before the camera turns to it: it darkens with the move, not in a step
  {at: 3240, x: GAP * 6, y: 0, rot: 0},
];

const ease = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
const clamp = (x: number) => Math.min(1, Math.max(0, x));

/** The desk camera at a frame: resting on a board (drifting in a little), or gliding to the next one. */
function deskCamera(frame: number) {
  let i = 0;
  while (i + 1 < BOARDS.length && frame >= BOARDS[i + 1].at - MOVE) i += 1;
  const b = BOARDS[i];
  const prev = BOARDS[Math.max(0, i - 1)];
  const k = i === 0 ? 1 : ease(clamp((frame - (b.at - MOVE)) / MOVE));
  const hold = frame - b.at;
  const drift = 1 + Math.min(0.035, Math.max(0, hold) * 0.00006);
  const lift = Math.sin(Math.PI * k) * 0.07; // pulls back a little on the way
  return {x: prev.x + (b.x - prev.x) * k, y: prev.y + (b.y - prev.y) * k, rot: prev.rot + (b.rot - prev.rot) * k, zoom: drift - lift};
}

/** A recording inside a w×h box, its camera following the mouse (recording pixels, source seconds). */
const ShotIn: React.FC<{name: string; rec: Track; from: number; rate?: number; keys: Key[]; w: number; h: number}> = ({name, rec, from, rate = 1, keys, w, h}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = from + (frame / fps) * rate;
  const cam = cameraAt(keys, t);
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: PAPER}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: rec.width, height: rec.height, transformOrigin: '0 0', transform: frameTransform(cam, rec.width, rec.height, w, h)}}>
        <OffthreadVideo src={staticFile(`rec/${name}.mp4`)} startFrom={Math.round(from * fps)} playbackRate={rate} muted style={{width: rec.width, height: rec.height}} />
      </div>
    </div>
  );
};

/** A character cut out of the pose pack, a paper puppet: white edge, the common shadow, a stop-motion
 *  wobble, poses swapped on a step with a squash. `poses`: [frame, pose] from its arrival. */
const Puppet: React.FC<{poses: [number, string][]; x: number; y: number; h: number; at?: number; from?: [number, number]; flip?: boolean; z?: number}> =
  ({poses, x, y, h, at = 0, from = [0, 260], flip = false, z = 30}) => {
    const t = useStep(at);
    if (t < 0) return null;
    const f = t * AD_FPS;
    const k = clamp(t / (3 / 12));
    const [swapAt, pose] = [...poses].reverse().find(([p]) => f >= p) ?? poses[0];
    const sinceSwap = f - swapAt;
    const squash = (t < 4 / 12 && t >= 3 / 12) || (sinceSwap >= 0 && sinceSwap < 5 && swapAt > 0) ? 1.05 : 1;
    const wob = (Math.floor(t * 6) % 2 ? 1 : -1) * 1.1 + (hash(Math.floor(t * 3), x) - 0.5) * 0.8;
    return (
      <div style={{position: 'absolute', left: x, top: y, height: h, zIndex: z, filter: PAPER_EDGE, transformOrigin: '50% 100%',
        transform: `translate(${from[0] * (1 - k)}px, ${from[1] * (1 - k)}px) rotate(${wob}deg) scale(${flip ? -1 : 1}, 1) scaleY(${squash})`}}>
        <Img src={staticFile(`ad/chars/${pose}.png`)} style={{height: h, display: 'block'}} />
      </div>
    );
  };

/** The mascot snake, cel-shaded (三渲二, Snake3D) in its own w×h canvas, cut out like the puppets: it rises
 *  into place on the stop-motion grid; `pose(t)` (seconds since arrival) makes it act. */
const SnakeActor: React.FC<{x: number; y: number; w: number; h: number; at?: number; scale?: number; pose?: (t: number) => Pose; z?: number}> =
  ({x, y, w, h, at = 0, scale = 1, pose = () => ({}), z = 46}) => {
    const t = useStep(at);
    const onCreated = useFreeContext();
    if (t < 0) return null;
    const k = clamp(t / (4 / 12));
    return (
      <div style={{position: 'absolute', left: x, top: y, width: w, height: h, zIndex: z, filter: PAPER_EDGE, transform: `translateY(${(1 - k) * h * 0.6}px)`, opacity: k > 0 ? 1 : 0}}>
        <ThreeCanvas width={w} height={h} camera={{fov: 22, position: [0, 0, 64], near: 1, far: 400}}
          gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}} onCreated={onCreated}>
          <Snake t={t} pose={{rise: 0.4 + 0.6 * k, ...pose(t)}} position={[0, -1.2, 0]} scale={scale} />
        </ThreeCanvas>
      </div>
    );
  };

const beat = (t: number, a: number, b: number) => clamp((t - a) / 0.35) * clamp((b - t) / 0.35);

/** A section head: an index number on lime and the line cut out in letters. */
const Head: React.FC<{n: string; text: string; at?: number; size?: number}> = ({n, text, at = 0, size = 92}) => (
  <>
    <Paper x={90} y={84} w={120} h={92} rot={-4} color={LIME} seed={31} at={at} torn={false} z={41}>
      <div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', fontFamily: CONSOLE, fontSize: 60, color: INK}}>{n}</div>
    </Paper>
    <CutText x={236} y={70} text={text} size={size} at={at + 6} gap={3} seed={40 + n.charCodeAt(1)} />
  </>
);

/** A keyframe of the tutorial (the VLOOKUP one, shot upright: the formula bar and table are at the top). */
const Frame: React.FC<{i: number; step?: boolean}> = ({i, step = false}) => (
  <Img src={staticFile(step ? `ad/frames/steps/${i}.jpg` : `ad/frames/vlookup/${String(i).padStart(2, '0')}.jpg`)}
    style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 22%'}} />
);

const TimeTag: React.FC<{x: number; y: number; text: string; at?: number; color?: string; bg?: string}> = ({x, y, text, at = 0, color = PAPER, bg = INK}) => {
  const t = useStep(at);
  if (t < 0) return null;
  return <div style={{position: 'absolute', left: x, top: y, zIndex: 57, fontFamily: CONSOLE, fontSize: 34, background: bg, color, padding: '0 12px', lineHeight: '42px'}}>{text}</div>;
};

/** A line written out a character at a time on the 12 fps grid, with a key sound per few. */
const Written: React.FC<{text: string; at: number; cps?: number; style: React.CSSProperties; sound?: boolean}> = ({text, at, cps = 18, style, sound = true}) => {
  const t = useStep(at);
  const n = t < 0 ? 0 : Math.min(text.length, Math.floor(t * cps));
  return (
    <>
      <div style={{whiteSpace: 'nowrap', ...style}}>{text.slice(0, n)}<span style={{opacity: n < text.length && t >= 0 ? 1 : 0, color: LIME, textShadow: `0 0 0 ${INK}`}}>▍</span></div>
      {sound ? Array.from({length: Math.ceil(text.length / 3)}, (_, i) => <Sfx key={i} name="key" at={at + (i * 3 * AD_FPS) / cps} volume={0.18} />) : null}
    </>
  );
};

// ---- boards ----------------------------------------------------------------------------------

/** 0–5.5 s: following a tutorial, stuck. The laptop paused on a frame, frames scattered, the girl lost; the helper turns up. */
const Stuck: React.FC = () => (
  <>
    <Paper x={-80} y={70} w={1300} h={860} rot={-2.5} color={KRAFT} seed={2} at={0} from={[0, -40]} />
    <Halftone x={1260} y={640} w={620} h={380} rot={-5} />
    <Photo x={150} y={170} w={880} h={520} rot={-1.5} at={6} seed={12}><Frame i={26} step /></Photo>
    <Tape x={590} y={176} w={200} rot={-3} at={10} />
    {/* the pause on the tutorial */}
    <Paper x={500} y={360} w={170} h={170} rot={3} color={INK} torn={false} seed={5} at={34} z={45}>
      {[46, 98].map((x) => <div key={x} style={{position: 'absolute', left: x, top: 42, width: 28, height: 86, background: PAPER}} />)}
    </Paper>
    <TimeTag x={176} y={624} text="02:00 / 04:48" at={36} />
    <Paper x={180} y={760} w={700} h={130} rot={-3} seed={7} at={56}>
      <Written text="下一步……点哪来着？" at={62} style={{position: 'absolute', left: 40, top: 30, fontFamily: PIXEL, fontSize: 60, color: INK}} />
    </Paper>
    {/* the frames she scrubbed through, scattered */}
    <Photo x={1000} y={90} w={330} h={196} rot={9} at={116} seed={13} z={20}><Frame i={9} step /></Photo>
    <Photo x={-30} y={620} w={300} h={180} rot={-11} at={124} seed={14} z={20}><Frame i={30} step /></Photo>
    <Photo x={960} y={560} w={320} h={190} rot={-7} at={132} seed={15} z={20}><Frame i={50} step /></Photo>
    <Stamp x={1150} y={250} text="？" rot={12} at={140} size={70} />
    <Stamp x={150} y={700} text="？" rot={-10} at={146} size={60} />
    <Puppet poses={[[0, 'G1'], [118, 'G2']]} x={1230} y={150} h={880} at={12} z={35} />
    <Sfx name="pop" at={6} volume={0.35} />
    <Sfx name="pop" at={116} volume={0.3} />
    <Sfx name="pop" at={124} volume={0.3} rate={1.1} />
    <Sfx name="pop" at={132} volume={0.3} rate={1.2} />
    {/* the helper pops up from the bottom and points at the screen */}
    <Puppet poses={[[0, 'B2'], [70, 'B3']]} x={1500} y={600} h={460} at={196} from={[0, 520]} flip z={38} />
    <Sfx name="swish" at={196} volume={0.3} />
    <Stamp x={1330} y={1000} text="交给帧寻" rot={-8} at={276} size={52} color="#3A6B2A" seed={9} />
  </>
);

/** 5.5–10 s: the name. */
const Name: React.FC = () => (
  <>
    <Paper x={120} y={130} w={1680} h={820} rot={1} seed={21} at={0} from={[0, -30]} color="#FFFFFF" />
    <Paper x={60} y={760} w={1820} h={150} rot={-2} color={LIME} seed={22} at={8} />
    <CutText x={300} y={250} text="帧寻" size={300} at={14} gap={6} colors={[[INK, PAPER], [PAPER, INK]]} seed={23} />
    <div style={{position: 'absolute', left: 1040, top: 300, zIndex: 50}}>
      <Written text="GongJ!ng?" at={44} cps={14} sound={false} style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 120, color: INK}} />
    </div>
    <Paper x={1046} y={470} w={620} h={110} rot={-2} seed={24} at={80} color={PAPER}>
      <div style={{position: 'absolute', left: 34, top: 20, fontFamily: SC, fontWeight: 900, fontSize: 56, color: INK}}>教程卡点助手</div>
    </Paper>
    <div style={{position: 'absolute', left: 300, top: 790, zIndex: 50, fontFamily: SC, fontWeight: 900, fontSize: 70, color: INK}}>
      <Written text="看教程卡住了？" at={110} cps={12} style={{}} />
    </div>
    <Puppet poses={[[0, 'B1']]} x={1500} y={560} h={400} at={60} from={[0, 400]} z={45} />
    <SnakeActor x={1110} y={600} w={340} h={440} at={96} scale={1.4}
      pose={(t) => ({happy: beat(t, 0.4, 1.8), blink: Math.max(0, 1 - Math.abs(t - 2.4) * 8), tilt: beat(t, 2.6, 4) * 0.7, turn: -0.3})} />
    <Sfx name="pop" at={20} volume={0.3} />
    <Sfx name="pop" at={26} volume={0.3} rate={1.15} />
    <Sfx name="pop" at={80} volume={0.3} />
  </>
);

const STEPS_REC = stepsRec as Track;
const CARDS = markAt(STEPS_REC, 'cards');

/** 10–22 s: a link pasted, the tutorial becomes step cards, each with its picture and second. */
const Steps: React.FC = () => {
  const from = Math.max(0, CARDS - 0.6);
  const keys = follow(STEPS_REC, from, from + 12, {zoom: 2.4});
  return (
    <>
      <Head n="01" text="贴一个教程链接" at={0} />
      <Paper x={100} y={230} w={780} h={96} rot={-1} seed={51} at={16}>
        <Written text={LINK} at={22} cps={26} style={{position: 'absolute', left: 30, top: 24, fontFamily: CONSOLE, fontSize: 46, color: INK}} />
      </Paper>
      <Photo x={930} y={120} w={900} h={560} rot={1.5} at={70} seed={52} z={22}>
        <Sequence from={70} layout="none"><ShotIn name="steps" rec={STEPS_REC} from={from} rate={1.15} keys={keys} w={872} h={532} /></Sequence>
      </Photo>
      <Tape x={1380} y={128} w={220} rot={2} at={76} />
      {STEPS.map((s, i) => (
        <React.Fragment key={s.n}>
          <Paper x={110 + (i % 2) * 18} y={370 + i * 150} w={760} h={128} rot={(i % 2 ? 1 : -1) * 1.4} torn={false} color="#FFFFFF" seed={60 + i} at={150 + i * 34} from={[-260, 0]} z={30 + i}>
            <div style={{position: 'absolute', left: 16, top: 14, width: 168, height: 100, overflow: 'hidden', background: '#000'}}><Frame i={s.frame} step /></div>
            <div style={{position: 'absolute', left: 200, top: 14, fontFamily: CONSOLE, fontSize: 30, background: LIME, color: INK, padding: '0 8px'}}>{String(s.n).padStart(2, '0')}</div>
            <div style={{position: 'absolute', left: 200, top: 58, fontFamily: SC, fontWeight: 900, fontSize: 36, color: INK, whiteSpace: 'nowrap'}}>{s.action}</div>
            <div style={{position: 'absolute', right: 18, top: 14, fontFamily: CONSOLE, fontSize: 30, background: INK, color: PAPER, padding: '0 10px'}}>{s.time}</div>
          </Paper>
          <Sfx name="pop" at={150 + i * 34} volume={0.28} rate={1 + i * 0.06} />
        </React.Fragment>
      ))}
      <Puppet poses={[[0, 'G1'], [150, 'G4']]} x={1030} y={640} h={460} at={330} from={[0, 400]} z={74} />
      <Puppet poses={[[0, 'B3']]} x={1440} y={680} h={380} at={350} from={[0, 400]} flip z={75} />
      <Sfx name="swish" at={330} volume={0.25} />
      {/* not only Excel: the Blender sample lands on top */}
      <Photo x={940} y={170} w={720} h={540} rot={-3} at={500} from={[300, -200]} seed={58} z={60}>
        <Img src={staticFile('ad/frames/blender/render.jpg')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </Photo>
      <Tape x={1300} y={176} w={200} rot={4} at={506} />
      <Sfx name="whoosh" at={496} volume={0.3} />
      {BLENDER.map((b, i) => (
        <React.Fragment key={b.n}>
          <Paper x={1480 - i * 26} y={250 + i * 126} w={420} h={112} rot={(i % 2 ? -1 : 1) * 2} torn={false} color="#FFFFFF" seed={110 + i} at={540 + i * 22} from={[260, 0]} z={62 + i}>
            <div style={{position: 'absolute', left: 12, top: 12, width: 118, height: 88, overflow: 'hidden', background: '#000'}}>
              <Img src={staticFile(`ad/frames/blender/${b.frame}.jpg`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
            </div>
            <div style={{position: 'absolute', left: 144, top: 12, fontFamily: CONSOLE, fontSize: 26, background: LIME, color: INK, padding: '0 6px'}}>{String(b.n).padStart(2, '0')}</div>
            <div style={{position: 'absolute', right: 12, top: 12, fontFamily: CONSOLE, fontSize: 26, background: INK, color: PAPER, padding: '0 8px'}}>{b.time}</div>
            <div style={{position: 'absolute', left: 144, top: 54, fontFamily: SC, fontWeight: 900, fontSize: 28, color: INK, whiteSpace: 'nowrap'}}>{b.action}</div>
          </Paper>
          <Sfx name="pop" at={540 + i * 22} volume={0.26} rate={1.05 + i * 0.06} />
        </React.Fragment>
      ))}
      <Stamp x={1180} y={140} text="Blender 也一样" rot={-6} at={620} size={44} seed={17} />
    </>
  );
};

const EVID_REC = evidenceRec as Track;
const PLAYING = markAt(EVID_REC, 'playing');

/** 22–36 s: stuck again — a screenshot of her own screen says which step she's on, and opens the original there. */
const Screenshot: React.FC = () => {
  const from = Math.max(0, PLAYING - 0.4);
  // the original playing in the player (top right of the page): framed on its picture alone
  const keys: Key[] = [{t: from, zoom: 2.2, x: 2700, y: 600}, {t: from + 1, zoom: 4.2, x: 2754, y: 500}, {t: from + 9, zoom: 4.3, x: 2754, y: 500}];
  return (
    <>
      <Head n="02" text="卡住了？发张截图" at={0} />
      <Puppet poses={[[0, 'G3']]} x={70} y={230} h={820} at={10} from={[-300, 0]} z={40} />
      <Photo x={470} y={250} w={560} h={330} rot={-4} at={84} from={[-420, 60]} seed={71} z={30}>
        <Frame i={STUCK.frame} step />
      </Photo>
      <Pin x={750} y={262} at={92} />
      <Sfx name="whoosh" at={80} volume={0.35} />
      <Puppet poses={[[0, 'B4']]} x={760} y={430} h={300} at={140} from={[0, 300]} z={46} />
      <Paper x={460} y={640} w={640} h={330} rot={1.5} torn={false} color="#FFFFFF" seed={72} at={210} z={32}>
        <div style={{position: 'absolute', left: 36, top: 26, fontFamily: CONSOLE, fontSize: 30, color: INK2}}>帧寻</div>
        <div style={{position: 'absolute', left: 36, top: 70, fontFamily: SC, fontWeight: 900, fontSize: 76, color: INK}}>你在第 {STUCK.step} 步</div>
        <div style={{position: 'absolute', left: 38, top: 180, width: 570, fontFamily: PIXEL, fontSize: 40, color: INK, lineHeight: 1.35}}>下一步：{STUCK.next}</div>
      </Paper>
      <Tape x={780} y={646} w={170} rot={-3} at={216} />
      <Sfx name="pop" at={210} volume={0.35} />
      <Stamp x={930} y={930} text={`回到原片 ${STUCK.time}`} rot={-5} at={270} size={46} seed={11} />
      <Photo x={1130} y={240} w={720} h={430} rot={2} at={300} seed={73} z={28}>
        <Sequence from={300} layout="none"><ShotIn name="evidence" rec={EVID_REC} from={from} rate={0.78} keys={keys} w={692} h={402} /></Sequence>
      </Photo>
      <Pin x={1490} y={252} color="#FFFFFF" at={308} />
      <Thread a={[930, 930]} b={[1490, 252]} at={318} dur={0.7} />
      <Sfx name="swish" at={318} volume={0.2} />
      <TimeTag x={1160} y={690} text={`原片 · ${STUCK.time}`} at={330} bg={LIME} color={INK} />
      <SnakeActor x={1650} y={640} w={280} h={420} at={340} scale={1.4}
        pose={(t) => ({lift: beat(t, 0.5, 6), look: -0.5 * beat(t, 0.5, 6), tilt: 0.2, turn: -0.35, blink: Math.max(0, 1 - Math.abs(t - 3) * 8)})} />
      <CutText x={1130} y={810} text="点一下回到那一秒" size={54} at={470} gap={3} seed={77} />
    </>
  );
};

const COMPARE_REC = compareRec as Track;
const TABLE = markAt(COMPARE_REC, 'table');

/** 36–48 s: three tutorials of the same thing, lined up by operation: who explains it, who skips it. */
const Compare: React.FC = () => {
  const from = Math.max(0, TABLE - 0.3);
  const keys = follow(COMPARE_REC, from, from + 12, {zoom: 1.6});
  const LABEL = '甲乙丙';
  return (
    <>
      <Head n="03" text="几个教程，对成一张表" at={0} size={84} />
      {TUTORIALS.map((t, i) => (
        <React.Fragment key={t}>
          <Paper x={100} y={250 + i * 112} w={720} h={92} rot={(i - 1) * 1.6} seed={81 + i} at={20 + i * 14} from={[-200, 0]} z={30}>
            <div style={{position: 'absolute', left: 18, top: 16, width: 58, height: 58, display: 'grid', placeItems: 'center', background: INK, color: PAPER, fontFamily: SC, fontWeight: 900, fontSize: 38}}>{LABEL[i]}</div>
            <div style={{position: 'absolute', left: 96, top: 22, fontFamily: SC, fontWeight: 500, fontSize: 38, color: INK, whiteSpace: 'nowrap'}}>{t}</div>
          </Paper>
          <Sfx name="pop" at={20 + i * 14} volume={0.25} rate={1 + i * 0.08} />
        </React.Fragment>
      ))}
      <Photo x={900} y={150} w={940} h={560} rot={-1.2} at={60} seed={84} z={22}>
        <Sequence from={60} layout="none"><ShotIn name="compare" rec={COMPARE_REC} from={from} rate={1.1} keys={keys} w={912} h={532} /></Sequence>
      </Photo>
      <Tape x={1360} y={156} w={200} rot={-2} at={66} />
      {/* the table, as paper strips */}
      {ROWS.map((r, i) => (
        <React.Fragment key={r.op}>
          <Paper x={100} y={620 + i * 128} w={1060} h={110} rot={(i % 2 ? 1 : -1) * 0.8} torn={false} color="#FFFFFF" seed={90 + i} at={200 + i * 40} from={[0, 200]} z={33 + i}>
            <div style={{position: 'absolute', left: 26, top: 28, width: 330, fontFamily: SC, fontWeight: 900, fontSize: 44, color: INK, whiteSpace: 'nowrap'}}>{r.op}</div>
            {r.cells.map((c, k) => (
              <div key={k} style={{position: 'absolute', left: 370 + k * 228, top: 26, width: 210, height: 58, display: 'flex', alignItems: 'center', gap: 10,
                fontFamily: CONSOLE, fontSize: 34, color: c ? INK : RED}}>
                <span style={{display: 'inline-grid', placeItems: 'center', width: 44, height: 44, background: c ? INK : 'transparent', border: `3px solid ${c ? INK : RED}`, color: c ? PAPER : RED, fontFamily: SC, fontWeight: 900, fontSize: 28}}>{LABEL[k]}</span>
                {c ?? <span style={{fontFamily: SC, fontWeight: 900, fontSize: 34}}>没讲</span>}
              </div>
            ))}
          </Paper>
          <Sfx name="pop" at={200 + i * 40} volume={0.3} rate={0.95 + i * 0.07} />
        </React.Fragment>
      ))}
      <Puppet poses={[[0, 'B7']]} x={1240} y={640} h={420} at={300} from={[0, 400]} z={46} />
      <Stamp x={790} y={856} text="跳过了" rot={-9} at={352} size={46} color={RED} seed={13} />
      <Puppet poses={[[0, 'G1'], [120, 'G4']]} x={1600} y={620} h={440} at={330} from={[0, 400]} z={45} />
    </>
  );
};

/** 48–54 s: the line, on dark paper. */
const Slogan: React.FC = () => (
  <>
    <Paper x={40} y={60} w={1840} h={960} rot={-1} color={NIGHT} seed={101} at={0} from={[0, 0]} grain={0.14} />
    <Paper x={140} y={620} w={1500} h={34} rot={-2} color={LIME} seed={102} at={82} torn={false} z={39} />
    <div style={{position: 'absolute', left: 170, top: 210, zIndex: 50}}>
      <Written text="平台的总结，帮你看完。" at={32} cps={14} style={{fontFamily: SC, fontWeight: 900, fontSize: 92, color: CREAM}} />
    </div>
    <CutText x={170} y={400} text="帧寻帮你照着做完" size={120} at={92} gap={4} colors={[[LIME, INK], [CREAM, INK], [INK, LIME]]} seed={103} />
    <div style={{position: 'absolute', left: 176, top: 730, zIndex: 50, fontFamily: PIXEL, fontSize: 44, color: CREAM, opacity: 0.86}}>
      <Written text="步骤卡片 · 截图定位 · 多教程对照 · 每句都能回到原片" at={192} cps={20} style={{}} />
    </div>
    <Puppet poses={[[0, 'G6']]} x={1420} y={420} h={600} at={172} from={[0, 400]} z={45} />
    <Sfx name="pop" at={172} volume={0.3} />
  </>
);

/** 54–60 s: the lockup, back on white. */
const Lockup: React.FC = () => (
  <>
    <Paper x={80} y={80} w={1760} h={920} rot={0.6} seed={111} at={0} color="#FFFFFF" from={[0, -24]} />
    <CutText x={420} y={230} text="帧寻" size={260} at={10} gap={5} colors={[[INK, PAPER], [LIME, INK]]} seed={112} />
    <div style={{position: 'absolute', left: 1030, top: 280, zIndex: 50, fontFamily: DISPLAY, fontWeight: 900, fontSize: 112, color: INK, opacity: useStep(26) >= 0 ? 1 : 0}}>GongJ!ng?</div>
    <div style={{position: 'absolute', left: 1036, top: 420, zIndex: 50, fontFamily: SC, fontWeight: 900, fontSize: 52, color: INK2, opacity: useStep(34) >= 0 ? 1 : 0}}>教程卡点助手</div>
    <Paper x={420} y={640} w={760} h={96} rot={-1.5} color={LIME} seed={113} at={50} torn={false}>
      <div style={{position: 'absolute', left: 30, top: 18, fontFamily: CONSOLE, fontSize: 56, color: INK}}>linyi.work/ZhenXun</div>
    </Paper>
    <Puppet poses={[[0, 'B8']]} x={1360} y={520} h={420} at={40} from={[0, 400]} z={45} />
    <Puppet poses={[[0, 'G7']]} x={1160} y={560} h={420} at={64} from={[0, 400]} z={44} />
    <SnakeActor x={110} y={620} w={300} h={420} at={84} scale={1.4} pose={(t) => ({happy: beat(t, 0.6, 2.4), turn: 0.35, blink: Math.max(0, 1 - Math.abs(t - 3.4) * 8)})} />
    <Sfx name="pop" at={50} volume={0.3} />
  </>
);

const VIEWS: React.FC[] = [Stuck, Name, Steps, Screenshot, Compare, Slogan, Lockup];

export const Ad: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = deskCamera(frame);
  return (
    <AbsoluteFill style={{background: '#EAE6DD', overflow: 'hidden'}}>
      {/* the desk under everything: a faint grid that moves with the camera */}
      <div style={{position: 'absolute', inset: -400, backgroundImage: 'linear-gradient(#DCD7CC 1.5px, transparent 1.5px), linear-gradient(90deg, #DCD7CC 1.5px, transparent 1.5px)',
        backgroundSize: '96px 96px', backgroundPosition: `${-cam.x % 96}px ${-cam.y % 96}px`, opacity: 0.7}} />
      <div style={{position: 'absolute', left: 0, top: 0, width: W, height: H, transformOrigin: '50% 50%',
        transform: `scale(${cam.zoom}) rotate(${-cam.rot}deg) translate(${-cam.x}px, ${-cam.y}px)`}}>
        {BOARDS.map((b, i) => {
          const View = VIEWS[i];
          const start = Math.max(0, b.at - (b.lead ?? LEAD));
          const end = BOARDS[i + 1] ? BOARDS[i + 1].at + 10 : AD_FRAMES;
          return (
            <div key={i} style={{position: 'absolute', left: b.x, top: b.y, width: W, height: H, transform: `rotate(${b.rot}deg)`}}>
              <Sequence from={start} durationInFrames={end - start} layout="none"><View /></Sequence>
            </div>
          );
        })}
      </div>
      {BOARDS.slice(1).map((b) => <Sfx key={b.at} name="whoosh" at={b.at - MOVE} volume={0.22} />)}
      {/* film grain over everything */}
      <svg width={W} height={H} style={{position: 'absolute', inset: 0, mixBlendMode: 'multiply', opacity: 0.07, pointerEvents: 'none'}}>
        <filter id="adgrain"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={Math.floor(frame / 5)} /><feColorMatrix type="saturate" values="0" /></filter>
        <rect width={W} height={H} filter="url(#adgrain)" />
      </svg>
    </AbsoluteFill>
  );
};
