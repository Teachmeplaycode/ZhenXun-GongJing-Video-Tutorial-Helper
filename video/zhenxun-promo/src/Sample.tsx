import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import opening from '../public/rec/opening.json';
import {Key, Track} from './camera';
import {Caption, Tag} from './Caption';
import {HudFrame} from './hud/Frame';
import {Shot} from './Shot';
import {DiagonalWipe, Flash, Halftone} from './Transitions';

// The 8-second sample: typing the link in close-up, Enter, then the homepage pulled out into view.
const rec = opening as Track;
const click = rec.track.find((e) => e.type === 'click')!;
const press = rec.track.find((e) => e.type === 'press')!;
const box = click.box!;
const keysTyped = rec.track.filter((e) => e.type === 'key');

// Close-up on the field; the camera rides the caret (about 17 recording px a character).
const textX = box.x + 64;
const typing: Key[] = [
  {t: keysTyped[9].t, zoom: 3.1, x: textX + 260, y: box.y + box.height / 2},
  ...keysTyped.filter((_, i) => i % 6 === 0).map((e, i) => ({t: e.t, zoom: 3.1, x: textX + 260 + Math.max(0, i * 6 * 17 - 360), y: box.y + box.height / 2})),
  {t: press.t, zoom: 3.4, x: textX + keysTyped.length * 17 - 120, y: box.y + box.height / 2},
];
// From the ninth character on: before 'https://w' the site says it sees no link yet (red), not for the film.
const TYPE_FROM = keysTyped[9].t;
const TYPE_RATE = (press.t + 0.05 - TYPE_FROM) / 3; // the typing in three seconds

// The homepage: from the wordmark out to the whole page.
const WIDE_FROM = 4.6;
const wide: Key[] = [
  {t: WIDE_FROM, zoom: 2.6, x: 840, y: 330},
  {t: WIDE_FROM + 0.32, zoom: 1, x: 1920, y: 1080},
  {t: 99, zoom: 1, x: 1920, y: 1080},
];

export const Sample: React.FC = () => (
  <AbsoluteFill style={{background: '#F5F3EF'}}>
    <Sequence durationInFrames={180}>
      <Shot name="opening" rec={rec} from={TYPE_FROM} rate={TYPE_RATE} keys={typing} />
      <HudFrame />
      <Caption text="看到哪，问到哪。" at={24} sticker="lime" mark="<<<" size={60} x={120} y={820} />
    </Sequence>
    <Sequence from={180} durationInFrames={300}>
      <Shot name="opening" rec={rec} from={WIDE_FROM} rate={0.5} keys={wide} />
      <Halftone opacity={0.12} />
      <HudFrame flare={0.4} />
      <Tag label="01 <<<" at={40} />
      <Caption text="帧寻 · 视频理解" at={70} size={72} x={120} y={840} />
      <DiagonalWipe at={282} />
    </Sequence>
    <Flash at={180} />
  </AbsoluteFill>
);
