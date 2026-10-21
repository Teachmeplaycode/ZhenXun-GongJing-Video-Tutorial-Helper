import {loadFont} from '@remotion/google-fonts/NotoSansSC';

// 帧寻's colours, as on the site (front/src/styles/tokens.css), and the type of the film.
export const INK = '#1A1A1A';
export const PAPER = '#F5F3EF';
export const LIME = '#C8F04A';
export const FPS = 60;

const {fontFamily} = loadFont('normal', {weights: ['900', '700', '500']});
export const HEAVY = `${fontFamily}, "PingFang SC", sans-serif`;
export const MONO = '"JetBrains Mono", "SF Mono", Menlo, monospace';
