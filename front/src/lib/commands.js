// Selected tasks remain metadata; the user's draft contains only their own question.
export const COMMANDS = [
  { key: '总结', hint: '分点总结视频内容', text: '总结这个视频的主要内容，分 3–5 点，每点注明时间点。' },
  { key: '时间线', hint: '按时间列出关键事件', text: '按时间顺序列出视频里的关键事件和画面变化，每条注明时间点。' },
  { key: '卡点', hint: '拆解关键过程、衔接与卡点', text: '结合我的问题和实际素材，按顺序拆解视频中的关键过程、前后衔接和容易卡住的地方，每项注明时间点。软件讲操作，课程讲推导，影视讲镜头与剪辑表达。' },
  { key: '科普核查', kind: 'skill', hint: '技能：逐条核查视频里的说法', text: '用科普核查技能，逐条核查这个视频里的健康和科学说法。' },
  { key: '反诈识别', kind: 'skill', hint: '技能：识别诈骗与引流风险', text: '用反诈识别技能，看看这个视频有没有诈骗或引流风险。' },
  { key: '核实', hint: '查资料核实某个说法', text: '核实视频里的主要说法是否正确，请查资料并给出来源链接。' },
  { key: '论文', hint: '找相关的学术论文', text: '找几篇和这个视频主题相关的学术论文，说明它们和视频内容的关系。' },
  { key: '细看', hint: '仔细看某一段画面', text: '仔细看 00:00 到 00:30 这段画面，描述具体发生了什么。' },
  { key: '慢放', hint: '慢放复看几秒钟，看清动作', text: '慢放复看 00:00 到 00:02，一帧一帧看清楚这段动作是怎么发生的。' },
  { key: 'GIF', hint: '截一段做成 GIF 或 MP4（表情包、存片段）', text: '我要这段的 GIF' },
]

export function commandFor(value) {
  const key = typeof value === 'string' ? value : value?.key
  return COMMANDS.find((command) => command.key === key) || null
}
