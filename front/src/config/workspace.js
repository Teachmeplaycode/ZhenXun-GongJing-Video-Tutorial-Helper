// Edit this file to tune copy, quick tasks and the two background animations.
// Project name: hometown dialect for "真的吗？". URLs and file names use the plain slug.
export const BRAND = {
  name: 'GongJ!ng?',
  confirmed: 'GongJ!ng!',
  slug: 'gongjing',
  gloss: '真的吗？',
  tag: '方言',
  product: '视频理解工作台',
}

export const WORKSPACE_CONTENT = {
  title: ['画面之内。', '答案之间。'],
  subtitle: '从视频素材到有据可查的回答',
  description: '展开时间，拆解画面。让关键帧、片段与细节，成为你下一次提问的依据。',
  issue: 'FIELD NOTES / 001',
  capabilities: [
    { label: '关键片段', title: '定位画面变化', description: '找到人物、产品和场景出现的时间点。', task: '找出视频中人物、产品和场景变化的时间点', mark: '01' },
    { label: '跨帧对照', title: '比较前后细节', description: '选择多张关键帧，追踪变化与事件顺序。', task: '比较视频前后关键画面的变化，按时间顺序说明', mark: '02' },
    { label: '分析报告', title: '整理完整叙事', description: '串联片段、总结信息，生成可复用的报告。', task: '整理关键片段并写成包含时间点的分析报告', mark: '03' },
  ],
  suggestions: [
    { title: '快速理解', description: '梳理主题、人物和主要事件', question: '总结这段视频的主要内容' },
    { title: '查找信息', description: '核实画面中出现的产品信息', question: '搜索视频里提到的产品信息' },
    { title: '生成报告', description: '按时间顺序整理关键片段', question: '整理关键片段并写成分析报告' },
  ],
}

export const SCULPTURE_SETTINGS = {
  count: 500,
  lowCount: 250,
  frame: { w: 22, h: 13.5 },
  sideOffset: 6, // the left loop passes behind the glass import slide
  // An occasional PV-style signal distortion on the model only (no inversion), homepage only.
  // Frame looks and burst rhythm live in lib/useModelGlitch.js, the shader in lib/postPass.js.
  glitch: {
    enabled: true,
    firstDelay: 2.8,
    minInterval: 9,
    maxInterval: 15,
    tempo: 1, // >1 slows every burst down, <1 speeds it up
  },
  // Slow expansion plus waves travelling around the Möbius ribbon.
  mobiusMotion: {
    period: 6.4,
    radiusBreath: 0.075,
    radialWave: 0.55,
    ridge: 0.7,
    lift: 0.65,
    twist: 0.26,
    widthBreath: 0.14,
    flowSpeed: 0.9,
  },
  ribbonMotion: { period: 7.2, breath: 0.05, wave: 0.4, twist: 0.22, widthBreath: 0.12 },
  // Maximum dispersal in each cycle; full dispersal joins the shapes smoothly.
  scatter: { amount: 1, width: 23, height: 11, depth: 8, scale: 0.2 },
  scatterText: {
    words: ['Loading...', 'Hello!', 'Waiting...', '率厚', '定xiu哇', '加载中...'],
    height: 10,
    padding: 48,
    mobilePadding: 24,
    footerSpace: 128,
    depth: 0.08,
    plateSize: 0.9,
    drift: 0.025,
    inkMix: 0.48,
  },
  morph: {
    shapes: ['infinity', 'mobius', 'trefoil', 'waveRing'],
    scatterDuration: 1.8,
    scatterHold: 3,
    assembleDuration: 2,
    shapeHold: 5,
  },
}

export const CONTOUR_SETTINGS = {
  // Full-screen terrain is cropped at the viewport edges.
  width: 0.95,
  height: 1.25,
  tilt: 0.72,
  relief: 0.22,
  centerY: 0.62,
  levels: 42,
  cycle: 2.4,
  hold: 0.7,
  fade: 0.4,
}

