import {Config} from '@remotion/cli/config';

// The sculpture is WebGL (three.js); ANGLE renders it on the GPU when rendering.
Config.setChromiumOpenGlRenderer('angle');
