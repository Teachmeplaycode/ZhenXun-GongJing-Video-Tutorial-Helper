import React from 'react';
import {Composition} from 'remotion';
import {Sample} from './Sample';
import {OPENING_FRAMES, PV, PV_FRAMES} from './pv/PV';
import {FPS} from './theme';
import {DEMO_FRAMES, DemoCut} from './films/DemoCut';
import {PRODUCT_FRAMES, ProductFilm} from './films/ProductFilm';
import {REEL_FRAMES, Reel} from './films/Reel';
import {SnakeLoop, SnakeSheet} from './ad/SnakeSheet';
import {StyleFrame} from './ad/StyleFrame';

export const Root: React.FC = () => (
  <>
    <Composition id="Sample" component={Sample} durationInFrames={480} fps={FPS} width={1920} height={1080} />
    {/* The PV's first ten seconds, ending on the name (cut into the deck on its own). */}
    <Composition id="Opening" component={PV} durationInFrames={OPENING_FRAMES} fps={FPS} width={1920} height={1080} />
    {/* The whole PV: the opening, then the rest (60 s). */}
    <Composition id="PV" component={PV} durationInFrames={PV_FRAMES} fps={FPS} width={1920} height={1080} />
    {/* The live site, feature by feature, from the recordings: camera following the cursor. */}
    <Composition id="DemoCut" component={DemoCut} durationInFrames={DEMO_FRAMES} fps={FPS} width={1920} height={1080} />
    {/* A quiet product film in the manner of the Claude / Codex launch films. */}
    <Composition id="ProductFilm" component={ProductFilm} durationInFrames={PRODUCT_FRAMES} fps={FPS} width={1920} height={1080} />
    {/* Every feature from the recordings, in the field-manual layout, moved by graphic means only. */}
    <Composition id="Reel" component={Reel} durationInFrames={REEL_FRAMES} fps={FPS} width={1920} height={1080} />
    {/* The ad's lead, the mascot snake as anime (三渲二): a character sheet and a short loop. */}
    <Composition id="SnakeSheet" component={SnakeSheet} durationInFrames={240} fps={FPS} width={1920} height={1080} />
    <Composition id="SnakeLoop" component={SnakeLoop} durationInFrames={480} fps={FPS} width={1920} height={1080} />
    <Composition id="StyleFrame" component={StyleFrame} durationInFrames={300} fps={FPS} width={1920} height={1080} />
  </>
);
