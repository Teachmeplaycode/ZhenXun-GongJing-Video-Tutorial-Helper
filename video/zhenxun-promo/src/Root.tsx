import React from 'react';
import {Composition} from 'remotion';
import {Sample} from './Sample';
import {OPENING_FRAMES, PV, PV_FRAMES} from './pv/PV';
import {FPS} from './theme';
import {DEMO_FRAMES, DemoCut} from './films/DemoCut';
import {PRODUCT_FRAMES, ProductFilm} from './films/ProductFilm';

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
  </>
);
