"""Canonical composer tasks, separate from the user's own supplement and saved message text."""
from __future__ import annotations

import math
import re
from typing import Literal

CommandKey = Literal['总结', '时间线', '卡点', '科普核查', '反诈识别', '核实', '论文', '细看', '慢放', 'GIF']

INSTRUCTIONS = {
    '总结': '总结这个视频的主要内容，分 3–5 点，每点注明时间点。',
    '时间线': '按时间顺序列出视频里的关键事件和画面变化，每条注明时间点。',
    '卡点': '结合我的问题和实际素材，按顺序拆解视频中的关键过程、前后衔接和容易卡住的地方，每项注明时间点。软件讲操作，课程讲推导，影视讲镜头与剪辑表达。',
    '科普核查': '用科普核查技能，逐条核查这个视频里的健康和科学说法。',
    '反诈识别': '用反诈识别技能，看看这个视频有没有诈骗或引流风险。',
    '核实': '核实视频里的主要说法是否正确，请查资料并给出来源链接。',
    '论文': '找几篇和这个视频主题相关的学术论文，说明它们和视频内容的关系。',
    '细看': '仔细看 00:00 到 00:30 这段画面，描述具体发生了什么。',
    '慢放': '慢放复看 00:00 到 00:02，一帧一帧看清楚这段动作是怎么发生的。',
    'GIF': '我要这段的 GIF',
}
TIMED_INSTRUCTIONS = {
    '细看': '仔细看用户指定时间的画面，描述具体发生了什么。',
    '慢放': '慢放复看用户指定时间的画面，一帧一帧看清楚这段动作是怎么发生的。',
}
USER_TIME = re.compile(r'\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?|\d+(?:\.\d+)?\s*秒')
SECONDS_RANGE = re.compile(r'(\d+(?:\.\d+)?)\s*秒\s*(?:到|至|~|～|-|–|—)\s*(\d+(?:\.\d+)?)\s*秒')
SECONDS_POINT = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)\s*秒')
COMPOUND_TIME = re.compile(r'[零一二三四五六七八九十两\d.]\s*分')
FORCED_KINDS = {key: 'content' for key in INSTRUCTIONS}
FORCED_KINDS.update({'卡点': 'tutorial', '科普核查': 'science', '反诈识别': 'fraud'})
RESEARCH_COMMANDS = {'核实', '论文'}


def command_label(command) -> str:
    """Ignore unknown legacy metadata; new request keys are validated before reaching this point."""
    return command if isinstance(command, str) and command in INSTRUCTIONS else ''


def _clock(value: str) -> str | None:
    seconds = round(float(value), 2)
    if not math.isfinite(seconds):
        return None
    hours, rest = divmod(seconds, 3600)
    minutes, second = divmod(rest, 60)
    tail = f'{int(minutes):02d}:' + f'{second:05.2f}'.rstrip('0').rstrip('.')
    return f'{int(hours)}:' + tail if hours else tail


def compose_question(command: str | None, question: str) -> str:
    """The effective model request; the persistent/user-visible message keeps `question` untouched."""
    key = command_label(command)
    if not key:
        return question
    instruction = (TIMED_INSTRUCTIONS[key] if key in TIMED_INSTRUCTIONS and USER_TIME.search(question)
                   else INSTRUCTIONS[key])
    # view_frames' automatic reader accepts clock notation; replay already understands seconds.
    if key == '细看' and not re.search(r'\d+:\d{2}', question) and not COMPOUND_TIME.search(question):
        seconds = SECONDS_RANGE.search(question)
        if seconds:
            clocks = [_clock(seconds[1]), _clock(seconds[2])]
            if all(clocks):
                instruction += f'\n画面时间：{clocks[0]} 到 {clocks[1]}。'
        else:
            point = SECONDS_POINT.search(question)
            clock = _clock(point[1]) if point else None
            if clock:
                instruction += f'\n画面时间：{clock}。'
    supplement = question.strip()
    return instruction + ('\n\n用户补充：' + supplement if supplement else '')
