"""Cheap, deterministic response planning; original evidence stays available through tools."""
from __future__ import annotations

import re
from pathlib import Path

SUMMARY = re.compile(r"总结|概括|摘要|要点|主要内容|核心内容|讲了什么")
DETAIL = re.compile(r"逐[帧页步句字]|每一?[页帧步]|参数|细节|详细|完整|全文|操作|步骤|按钮|菜单|公式|推导|慢放|复看|"
                    r"查证|核实|核查|验证|联网|上网|搜索|搜一下|网页|论文|文献|资料|出处|来源|最新|"
                    r"对不对|真假|正确|可靠|可信|能信吗|科学吗|谣言|骗|诈|风险|引流|第.{1,4}[章页节步]")
SUMMARY_SPEECH_CHARS = 12000
SUMMARY_SCREEN_CHARS = 6000
SUMMARY_OUTPUT_TOKENS = 2048
SUMMARY_GUIDE = ("本次是视频内容概览：先根据已有原始画面和文字，直接给出3–5点简明要点及依据时间；"
                 "所给文字是覆盖已有时间范围的摘取，不代表逐字完整转写。已有证据足够时直接回答，"
                 "需要补充或核对具体内容时仍可用工具读取；不能把派生章节摘要冒充原始证据。")


def is_summary(question: str) -> bool:
    return bool(SUMMARY.search(question or "")) and not DETAIL.search(question or "")


def rows(state):
    for item in getattr(state, "segments", ()) or ():
        if isinstance(item, (tuple, list)):
            a, b, text = item[0], item[1], item[2]
        else:
            a, b, text = item.start, item.end, item.text
        if str(text).strip():
            yield float(a), float(b), str(text)


def has_evidence(job, requested=None, images=None, ranges=None, window=10):
    if any(Path(path).is_file() for path in images or ()):
        return True
    wanted = set(requested or ())
    scoped = bool(wanted) or ranges is not None
    spans = ([(slot.time - window, slot.time + window) for slot in job.slots if slot.index in wanted]
             if wanted else ranges or [])
    def near(a, b):
        return not scoped or any(b >= start and a <= end for start, end in spans)
    if any(slot.status == "ok" and (not wanted or slot.index in wanted) and near(slot.time, slot.time)
           and job.frame_path(slot.index).is_file() for slot in job.slots):
        return True
    return any(near(a, b) for state in (job.transcript, job.screentext) for a, b, _ in rows(state))


def summary_images(job):
    speech, screen = list(rows(job.transcript)), list(rows(job.screentext))
    duration = job.video.duration or 0
    partial = bool(speech and duration and (min(a for a, _, _ in speech) > duration * .2
                                           or max(b for _, b, _ in speech) < duration * .8))
    return 16 if not (speech or screen) or partial else 12


def balanced_lines(lines: list[str], budget: int) -> list[str]:
    """Bound the prompt across its complete time range, preserving both ends and timestamps."""
    if sum(len(line) + 1 for line in lines) <= budget:
        return lines
    count = min(len(lines), max(2, budget // 240))
    if not count:
        return []
    picked = ([lines[0]] if count == 1 else
              [lines[round(i * (len(lines) - 1) / (count - 1))] for i in range(count)])
    width = max(1, budget // count - 1)
    return [line if len(line) <= width else line[:max(0, width - 1)] + "…" for line in picked]


def chapter_context(job):
    from modules.chapters import load
    record = load(job.root)
    if not record or record.get("status") != "done" or not record.get("chapters"):
        return ""
    lines = [f"[{c['start']}–{c['end']}秒] {str(c.get('title', ''))[:40]}：{str(c.get('summary', ''))[:100]}"
             for c in record["chapters"][:15]]
    return ("已有章节目录（派生摘要，只用于导航，可能仍在补充；不是原始证据。"
            "引用时必须核对本次提供的画面、语音或画面文字，必要时用工具补读）：\n" + "\n".join(lines))


class SummaryText:
    """Release normal text at once; retain only possible tool-markup prefixes across deltas."""
    starts = ("<｜", "<|", "<tool", "<function", "dsml｜", "dsml|")

    def __init__(self):
        self.pending = ""
        self.blocked = False

    def feed(self, delta):
        if self.blocked:
            return ""
        text = self.pending + delta
        lower = text.lower()
        found = [lower.find(prefix) for prefix in self.starts if prefix in lower]
        if found:
            self.blocked, self.pending = True, ""
            return text[:min(found)]
        keep = max((n for n in range(1, min(len(text), max(map(len, self.starts))) + 1)
                    if any(prefix.startswith(lower[-n:]) for prefix in self.starts)), default=0)
        self.pending = text[-keep:] if keep else ""
        return text[:-keep] if keep else text

    def finish(self):
        pending, self.pending = self.pending, ""
        if pending.startswith("<"):
            self.blocked = True
        return "" if self.blocked else pending
