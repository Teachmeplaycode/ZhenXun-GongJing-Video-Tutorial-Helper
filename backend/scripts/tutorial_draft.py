"""Draft questions for the held-out software tutorials (evals/tutorial.json), four per video, for a
person to confirm. Drafts are marked reviewed: false and eval.py leaves them out unless --drafts.

    uv run python scripts/tutorial_draft.py              # every video that has no questions yet
    uv run python scripts/tutorial_draft.py --only cad   # videos whose key contains this

Per video: imported in the eval backend (data/evals, shared with eval.py), then the model reads its
speech and on-screen text with times and writes one question of each kind:

  locate   which step, which button or menu, at about which second (needs the picture or the
           on-screen text, not the speech alone)
  reason   why a step is done that way, or where following along goes wrong
  summary  the steps in order
  absent   something a viewer might ask that the video does not cover; the right answer says so

with a reference answer, the seconds it rests on, and the words a right answer has to contain.
The person reviewing checks these against the video: the model drafting them may be wrong.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval as qa  # noqa: E402
from evals.schema import validate  # noqa: E402

SET = ROOT / "evals" / "tutorial.json"
SPEECH_CHARS, SCREEN_CHARS = 5000, 5000
ABSENT_WORDS = ["没有", "没讲", "未提到", "没提到", "未涉及", "找不到", "不包含", "并未", "无法从视频"]

SYSTEM = """你在为一个「视频理解助手」编写软件教程验收题。给你一个教程视频带时间的语音转写和画面文字（每秒识别的界面上的字）。
出 4 道题，每种题型一道：
- locate：问某个具体操作在第几秒、点了哪个按钮或菜单、选了哪个选项。必须要看画面或画面文字才能答准，光听语音答不全。
- reason：问为什么这样做、这一步的作用，或者跟着做时哪一步容易出错、出错会怎样。答案要在视频里有依据。
- summary：问完成某件事的完整步骤（按顺序）。
- absent：问一个看这个视频的人可能会问、但视频里确实没讲的内容（同一软件的相关功能或相关操作）。正确答案是「视频里没有讲」。
每道题给出：
- question：自然的提问，像真实用户那样问，不写时间点，不超过 40 字；
- answer：参考答案，简洁具体，写出依据的时间（mm:ss）；absent 题写「视频没有讲……」并说明视频讲的是什么；
- evidence：答案依据的时间点，写成 "mm:ss" 字符串数组（1～4 个，例如 ["05:56","06:36"]），必须是转写或画面文字里出现过的时间；absent 题给空数组；
- keywords：正确回答必须包含的关键词组，数组的数组，每组里任一词出现即可（例如 [["报表布局"],["以表格形式显示","表格形式"]]），用界面上的原名；absent 题给空数组。
只依据给出的转写和画面文字，不要编造视频里没有的按钮名或时间。
只返回 JSON：{"cases":[{"qtype":"locate","question":"…","answer":"…","evidence":[…],"keywords":[[…]]}, …]}"""


def clock(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def spread(lines: list[str], budget: int) -> list[str]:
    if sum(len(x) + 1 for x in lines) <= budget:
        return lines
    keep = max(1, budget // max(1, sum(len(x) + 1 for x in lines) // len(lines)))
    step = len(lines) / keep
    return [lines[int(i * step)] for i in range(keep)]


async def material(client: httpx.AsyncClient, job_id: str, title: str) -> str:
    speech = (await client.get(f"/api/link-jobs/{job_id}/transcript")).json().get("segments") or []
    screen = (await client.get(f"/api/link-jobs/{job_id}/screentext")).json().get("segments") or []
    said = [f"[{clock(s['start'])}] {s['text'].strip()}" for s in speech if s.get("text", "").strip()]
    seen, shown = set(), []
    for c in screen:
        text = c.get("text", "").strip()
        if text and text not in seen:
            seen.add(text)
            shown.append(f"[{clock(c['start'])}] {text}")
    return (f"视频标题：{title}\n\n语音转写：\n" + "\n".join(spread(said, SPEECH_CHARS))
            + "\n\n画面文字：\n" + "\n".join(spread(shown, SCREEN_CHARS)))


def stamp(value) -> float | None:
    """"05:56" → 356.0; a bare number is taken as seconds; anything else → None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value >= 0 else None
    parts = str(value).strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return None
    total = 0.0
    for p in parts:
        total = total * 60 + int(p)
    return total


def to_cases(key: str, drafted: list[dict]) -> list[dict]:
    cases = []
    for d in drafted:
        qtype = d.get("qtype")
        if qtype not in ("locate", "reason", "summary", "absent") or any(c["qtype"] == qtype for c in cases):
            continue
        question, answer = str(d.get("question", "")).strip(), str(d.get("answer", "")).strip()
        if not question or not answer:
            continue
        evidence = [t for t in (stamp(x) for x in d.get("evidence") or []) if t is not None][:4]
        groups = [[str(w).strip() for w in g if str(w).strip()] for g in d.get("keywords") or [] if isinstance(g, list)]
        groups = [g for g in groups if g][:3]
        checks: dict = {}
        if qtype == "absent":
            checks = {"contains_any": [ABSENT_WORDS]}
            evidence = []
        else:
            checks["citations_ok"] = True
            if groups and qtype in ("locate", "summary"):  # UI names; a reason can be put many ways: the judge grades it
                checks["contains_any"] = groups
            if qtype in ("locate", "summary"):
                checks["timestamps"] = True
            if qtype == "locate" and evidence:
                checks["near"] = True
        case = {"id": f"{key}-{qtype}", "video": key, "qtype": qtype, "question": question,
                "rubric": f"参考答案：{answer}", "checks": checks, "reviewed": False}
        if evidence:
            case["evidence"] = evidence
        cases.append(case)
    return cases


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="videos whose key contains this")
    parser.add_argument("--batch", type=int, default=4, help="videos imported at the same time")
    args = parser.parse_args()
    spec = json.loads(SET.read_text())
    have = {c["video"] for c in spec["cases"]}
    todo = {k: v for k, v in spec["videos"].items() if k not in have and (not args.only or args.only in k)}
    if not todo:
        print("每个视频都有题了")
        return
    from modules.llm import LLMConfig, Usage, create_client
    llm = create_client(LLMConfig.from_env())

    async def draft(text: str) -> list[dict]:
        for _ in range(2):  # one more try on a reply that isn't JSON
            chunks = []
            async for delta in llm.stream([{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
                                          Usage(), max_tokens=2000):
                chunks.append(delta)
            raw = "".join(chunks)
            start, end = raw.find("{"), raw.rfind("}")
            try:
                return json.loads(raw[start:end + 1]).get("cases") or []
            except (ValueError, AttributeError):
                continue
        return []

    with qa.Backend() as backend:
        async with httpx.AsyncClient(base_url=backend.base, timeout=60) as client:
            keys = list(todo)
            for n in range(0, len(keys), args.batch):
                batch = keys[n:n + args.batch]
                print(f"导入 {', '.join(batch)}")
                ids = await qa.prepare(client, {k: {"url": todo[k]["url"]} for k in batch})
                for key in batch:
                    if key not in ids:
                        print(f"  ✗ {key}: 没有导入成功")
                        continue
                    snap = (await client.get(f"/api/link-jobs/{ids[key]}")).json()
                    cases = to_cases(key, await draft(await material(client, ids[key], snap["video"]["title"])))
                    spec["cases"] = [c for c in spec["cases"] if c["video"] != key] + cases
                    if errors := validate(spec):
                        print(f"  ✗ {key}: 草稿不合格式：{errors[:2]}")
                        spec["cases"] = [c for c in spec["cases"] if c["video"] != key]
                        continue
                    SET.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
                    print(f"  ✓ {key}: {len(cases)} 题 · " + " / ".join(c["question"][:18] for c in cases))
    await llm.aclose()


if __name__ == "__main__":
    asyncio.run(main())
