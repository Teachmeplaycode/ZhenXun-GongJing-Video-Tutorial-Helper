"""What kind of question this is, decided before the agent starts, so each kind is answered its way.

  tutorial  a software or how-to video: which step, which button at which second, why it fails
  content   what the video says or shows
  science   whether the video's health / science claims as a whole are right → the 科普核查 skill runs first
  verify    one particular claim or figure to look up (searching is quicker than the whole check)
  fraud     whether it is a scam or drawing people off-platform → the 反诈识别 skill runs first
  chat      nothing to do with the video

The local decision model (modules/decide) picks one with probabilities; without it, keywords do.
A skill a question plainly asks for runs as the answer's first step instead of waiting for the
model to think of it; a tutorial question gets the step-by-step way of answering; the rest is
answered as before. An uncertain decision (the top option below CONFIDENT) changes nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CRITERIA = {
    "tutorial": "软件或操作教程类问题：问某一步怎么操作、第几秒点了哪个按钮或菜单、输入了什么、设置在哪里、为什么报错或卡住",
    "content": "视频内容问答：问视频讲了什么、某段画面、台词、人物、事件或细节",
    "science": "核查整个视频：问这个视频的健康、医学、营养、科学说法整体对不对、靠不靠谱，或要求把视频的说法都核查、辟谣一遍",
    "verify": "核实某一个具体说法或数据：问视频里某句话、某个数字、某个出处是否属实，需要查资料",
    "fraud": "诈骗风险：问视频是不是骗局、能不能信、有没有风险、会不会被骗，是不是在引流或卖假货",
    "chat": "和这个视频无关的闲聊或一般问题",
}
QUESTION = "用户在看一个视频时提出了下面的问题。这个问题属于哪一类？"
NAMES = {"tutorial": "教程操作", "content": "视频内容", "science": "科普核查", "verify": "核实说法", "fraud": "反诈识别", "chat": "与视频无关"}
SKILL = {"science": "check_science", "fraud": "check_fraud"}
CONFIDENT = 0.6

KEYWORDS = [  # order matters: the first that matches wins
    ("fraud", re.compile(r"骗|诈|传销|引流|能信吗|可信吗|有没有风险|割韭菜|杀猪盘|理财陷阱")),
    ("science", re.compile(r"科普核查|(视频|这个|整个|全部|这些|它|博主|作者).{0,8}(说得对|对不对|靠谱|科学吗|伪科学|谣言|核查|辟谣)|"
                           r"(核查|辟谣).{0,6}(视频|这个|全部|一遍)")),
    ("verify", re.compile(r"核实|核查|可靠吗|是真的吗|真的假的|有没有(科学)?依据|出处|来源|靠谱吗|说法对吗")),
    ("tutorial", re.compile(r"按钮|菜单|点击|点了|点哪|第几秒|哪一步|步骤|怎么操作|怎么设置|在哪设置|快捷键|报错|出错|卡住|选项|输入了|界面")),
]

TUTORIAL_NOTE = ("这是软件或操作教程类问题。按操作顺序回答：每一步写清第几秒、点了哪个按钮或菜单、输入了什么，"
                 "按钮和菜单的名字照画面上的文字原样写；界面细节以画面和画面文字为准，语音只作补充；"
                 "关键一步只有一两张关键帧或看不清时，先用 view_frames 补看再回答；问到出错或卡住时，指出最可能出错的一步和原因。")
CHAT_NOTE = "这个问题和视频内容无关：简短回答，并说明你主要是根据这个视频来回答问题的。"


@dataclass
class Intent:
    kind: str
    p: float | None          # the decision model's probability for it; None when keywords decided
    probabilities: dict
    how: str                 # 决策模型 / 关键词

    @property
    def sure(self) -> bool:
        return self.p is None or self.p >= CONFIDENT

    @property
    def skill(self) -> str | None:
        return SKILL.get(self.kind) if self.sure else None

    @property
    def note(self) -> str:
        if not self.sure:
            return ""
        return {"tutorial": TUTORIAL_NOTE, "chat": CHAT_NOTE}.get(self.kind, "")

    def as_data(self) -> dict:
        return {"kind": self.kind, "name": NAMES[self.kind], "p": self.p, "probabilities": self.probabilities,
                "how": self.how, "sure": self.sure, "skill": self.skill}


def by_keywords(question: str) -> Intent:
    kind = next((k for k, pattern in KEYWORDS if pattern.search(question or "")), "content")
    return Intent(kind, None, {}, "关键词")


async def classify(question: str, decider=None) -> Intent:
    """The question's kind: the decision model's pick, else keywords. Never raises."""
    if decider is not None:
        try:
            from modules.decide import questions as dq
            decision = await decider.choice(dq.question_state(question), QUESTION, CRITERIA, task="intent")
            probs = {k: round(v, 3) for k, v in decision.probabilities.items()}
            return Intent(decision.choice, probs[decision.choice], probs, "决策模型")
        except Exception:  # noqa: BLE001 — the decision model is optional
            pass
    return by_keywords(question)
