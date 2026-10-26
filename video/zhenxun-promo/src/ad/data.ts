// What the ad shows of the real product: the VLOOKUP tutorial's step cards and the comparison of three
// VLOOKUP tutorials, as the live site gave them for the recordings (record/record.mjs: steps, compare).

export const LINK = 'bilibili.com/video/BV1M34y1C7HZ';

/** Four of the tutorial's eight step cards as the site made them (session af460e4a4714): number, action
 *  (shortened to fit a card), time, and its keyframe (public/ad/frames/steps/<frame>.jpg). */
export const STEPS: {n: number; action: string; time: string; frame: number}[] = [
  {n: 2, action: '第一参数选姓名单元格', time: '00:44', frame: 9},
  {n: 3, action: '从姓名列框选数据范围', time: '01:38', frame: 21},
  {n: 4, action: '按 F4 做绝对引用', time: '02:00', frame: 26},
  {n: 5, action: '第三参数输入列号 2', time: '02:17', frame: 30},
];

/** The step the screenshot is matched to, and what to do next. */
export const STUCK = {step: 4, time: '02:00', frame: 26, next: '第三参数填 2'};

/** The comparison: three tutorials, two of its rows. */
export const TUTORIALS = ['vlookup 函数使用方法详解', '手把手教你 vlookup 两表匹配', '巧用 vlookup 秒配两表数据'];
export const ROWS: {op: string; cells: (string | null)[]}[] = [
  {op: '输入函数', cells: ['00:41', '00:09', '00:12']},
  {op: '绝对引用 F4', cells: ['01:32', null, '00:31']},
  {op: '跨表框选', cells: [null, '00:24', '00:20']},
];

/** The Blender sample (「11分钟学会blender从0到渲染出图」, session 70b8e95778af): three of its 45 cards, and
 *  its frames read at 1080p (public/ad/frames/blender/<name>.jpg). */
export const BLENDER: {n: number; action: string; time: string; frame: string}[] = [
  {n: 18, action: 'Shift+A 添加「猴头」', time: '05:09', frame: 'monkey'},
  {n: 34, action: '加「表面细分」修改器', time: '09:42', frame: 'subdiv'},
  {n: 40, action: '「渲染」→「渲染图像」', time: '10:57', frame: 'render'},
];
