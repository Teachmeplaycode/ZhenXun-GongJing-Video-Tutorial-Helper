// Edit this file to tune copy, quick tasks and the two background animations.
// Project name: 帧寻 (finding the answer in the frames), English GongJ!ng? (dialect for "真的吗？").
// URLs and file names use the plain slug.
export const BRAND = {
  name: '帧寻 GongJ!ng?',
  confirmed: '帧寻 GongJ!ng!',
  slug: 'gongjing',
  gloss: '真的吗？',
  tag: '方言',
  product: '教程卡点助手',
}

export const WORKSPACE_CONTENT = {
  // Platforms' summaries help you finish watching; 帧寻 helps you finish doing what the tutorial shows.
  title: ['跟着教程，卡住就截图'], // the closing dot is drawn in the accent colour (workspace.css)
  subtitle: '照着教程做，卡住了截个图',
  description: '导入教程视频，卡住时发一张屏幕截图：帧寻说出你在第几步、下一步点哪，带你回到原视频那一秒。每句话都有出处。',
  issue: 'FIELD NOTES / 001',
  capabilities: [
    { label: '操作步骤', title: '列出步骤', description: '按顺序列出每一步，标上时间，点一下回到那一秒。', task: '按顺序列出这个教程的操作步骤，每步标上时间', mark: '01' },
    { label: '关键片段', title: '总结内容', description: '找到人物、产品和场景出现的时间点。', task: '总结这份内容的主题和主要观点', mark: '02' },
    { label: '跨帧对照', title: '核查说法', description: '逐条核对视频里的说法，给出依据。', task: '核查这份内容中的主要说法，并给出依据', mark: '03' },
  ],
  suggestions: [
    { title: '操作步骤', description: '按顺序列出每一步和时间', question: '按顺序列出操作步骤，每步标上时间' },
    { title: '快速理解', description: '梳理主题、人物和主要事件', question: '总结这段视频的主要内容' },
    { title: '生成报告', description: '按时间顺序整理关键片段', question: '整理关键片段并写成分析报告' },
  ],
  // The same three for a picture set (stages/PictureStage.jsx).
  pictureSuggestions: [
    { title: '读懂这组图', description: '逐张说清每张图讲了什么', question: '逐张总结这组图片的内容' },
    { title: '核查说法', description: '图里的说法有没有依据、是否夸大', question: '核查图片里的说法是否属实' },
    { title: '整理要点', description: '提炼成可以直接保存的清单', question: '把这组图片的要点整理成清单' },
  ],
}

export const SCULPTURE_SETTINGS = {
  count: 250,
  lowCount: 200,
  frame: { w: 22, h: 12 },
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

