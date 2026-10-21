import React from 'react';
import {Composition} from 'remotion';
import {Sample} from './Sample';
import {FPS} from './theme';

export const Root: React.FC = () => (
  <>
    <Composition id="Sample" component={Sample} durationInFrames={480} fps={FPS} width={1920} height={1080} />
  </>
);
