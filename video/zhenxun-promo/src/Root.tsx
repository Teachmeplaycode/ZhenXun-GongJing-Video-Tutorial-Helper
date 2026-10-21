import React from 'react';
import {Composition} from 'remotion';
import {Sample} from './Sample';
import {Opening} from './pv/Opening';
import {PV, PV_FRAMES} from './pv/PV';
import {FPS} from './theme';

export const Root: React.FC = () => (
  <>
    <Composition id="Sample" component={Sample} durationInFrames={480} fps={FPS} width={1920} height={1080} />
    {/* The PV's first ten seconds, ending on the name (cut into the deck on its own). */}
    <Composition id="Opening" component={Opening} durationInFrames={600} fps={FPS} width={1920} height={1080} />
    {/* The whole PV: the opening, then the rest (60 s). */}
    <Composition id="PV" component={PV} durationInFrames={PV_FRAMES} fps={FPS} width={1920} height={1080} />
  </>
);
