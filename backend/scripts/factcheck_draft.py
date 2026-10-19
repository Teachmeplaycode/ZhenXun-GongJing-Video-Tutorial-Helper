"""Draft items for evals/factcheck.json: find a video per health topic, write down its claims, and
suggest a label from authoritative sources. A person then confirms every label (reviewed: true).

    uv run python scripts/factcheck_draft.py                      # every topic in TOPICS not drafted yet
    uv run python scripts/factcheck_draft.py --topic "空腹喝醋 降血压"
    uv run python scripts/factcheck_draft.py --url https://www.bilibili.com/video/BV… --key vinegar
    uv run python scripts/factcheck_draft.py --review             # write the review sheet only

Per topic: Bilibili search (with the saved login) → the most-played video of 1–10 minutes →
imported in the eval backend (data/evals-factcheck) → its speech and on-screen text → the model lists
the 2–4 health claims a viewer would take away, quoting the video → DeepSeek search (authority ≥ 3)
for each → the model suggests a label from those sources only. Drafts never count until reviewed.

Why a person must confirm: the suggestion comes from the same kind of model the fact check uses, so
an unreviewed label would partly grade the system against itself. The review sheet
(docs/evals/factcheck-review.md) lists each claim with its quote, the suggested label, the reason
and the sources, ready to accept or change.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eval as qa  # noqa: E402
import factcheck_eval as fe  # noqa: E402

REVIEW = ROOT.parent / "docs" / "evals" / "factcheck-review.md"
MIN_SECONDS, MAX_SECONDS = 60, 600
# Health topics older viewers meet often: rumours, half-truths and sound advice, so every label occurs.
TOPICS = {
    "vinegar-bp": "空腹喝醋 降血压", "leftovers": "隔夜菜 致癌", "acid-alkaline": "酸碱体质", "bone-soup": "喝骨头汤 补钙",
    "brown-sugar": "红糖 补血", "pig-trotter": "猪蹄 胶原蛋白", "egg-yolk": "鸡蛋黄 胆固醇", "msg": "味精 致癌",
    "microwave": "微波炉 辐射", "mung-bean": "绿豆汤 排毒", "onion-wine": "洋葱泡红酒 软化血管", "bp-drugs": "降压药 停不了",
    "grapefruit": "柚子 降压药", "morning-exercise": "晨练 越早越好", "sugar-free": "无糖食品 血糖", "supplements": "保健品 降血糖",
    "iv-drip": "输液 疏通血管", "black-sesame": "黑芝麻 白发", "breakfast": "不吃早饭 胆结石", "eight-glasses": "每天八杯水",
    "vitamin-c": "维生素C 感冒", "moderate-drinking": "少量饮酒 有益", "ejiao": "阿胶 补血", "fish-oil": "鱼油 降血脂",
    "whole-grains": "粗粮 越多越好", "salt-bp": "吃盐 高血压", "honey-cough": "蜂蜜 咳嗽", "sun-calcium": "晒太阳 补钙",
    "breathing-bp": "60秒 降血压", "ginger-hair": "生姜 生发",
}


def key_of(text: str) -> str:
    """A key for a topic not in TOPICS, or for a link: stable across runs."""
    import hashlib
    return "x" + hashlib.sha1(text.encode()).hexdigest()[:6]


def seconds(duration: str) -> int:
    parts = [int(p) for p in str(duration).split(":") if p.isdigit()]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


async def search_bilibili(topic: str) -> dict | None:
    """The most-played video of 1–10 minutes for the topic: {url, title, author, plays, seconds}."""
    from modules.settings import settings
    from modules.video_source.bilibili import BilibiliResolver
    r = BilibiliResolver()
    try:
        data = await r._api("/x/web-interface/wbi/search/type", {"search_type": "video", "keyword": topic, "page": 1},
                            login=settings().get("BILIBILI_COOKIE", ""))
    finally:
        await r.aclose()
    found = [{"url": f"https://www.bilibili.com/video/{v['bvid']}", "title": re.sub(r"<[^>]+>", "", v.get("title", "")),
              "author": v.get("author", ""), "plays": int(v.get("play") or 0), "seconds": seconds(v.get("duration", ""))}
             for v in (data.get("data") or {}).get("result") or [] if v.get("bvid")]
    fit = [v for v in found if MIN_SECONDS <= v["seconds"] <= MAX_SECONDS]
    return max(fit, key=lambda v: v["plays"]) if fit else None


async def content(client: httpx.AsyncClient, job_id: str) -> str:
    """Speech and on-screen text, in time order, as numbered lines the model can quote."""
    speech = (await client.get(f"/api/link-jobs/{job_id}/transcript")).json().get("segments") or []
    screen = (await client.get(f"/api/link-jobs/{job_id}/screentext")).json().get("segments") or []
    lines = [(s.get("start", 0), f"[语音] {s.get('text', '').strip()}") for s in speech if s.get("text")]
    lines += [(s.get("start", 0), f"[画面] {s.get('text', '').strip()}") for s in screen if s.get("text")]
    return "\n".join(t for _, t in sorted(lines))[:9000]


CLAIMS_SYSTEM = """你在为「健康科普核查」评测集起草题目。给你一个视频的语音转写和画面文字。
列出观众（尤其是中老年人）看完会记住、并可能照着做的 2 到 4 条健康说法：
- 必须是视频里明确说出或写出的，可以核实对错的具体主张；不要客套话、不要观点。
- 按视频自己的立场写：视频在辟谣时，写它的结论（如「喝醋不能降血压」），不要把被辟谣的说法当成视频的主张。
- 每条说一件不同的事，不要两条换个说法讲同一件事。
- claim 用一句话中性地复述主张（不加“视频说”）；quote 摘录视频原话（20 字以内）。
- query 是核实这条说法用的中文搜索词（10 字以内）。
只返回 JSON：{"claims":[{"claim":"…","quote":"…","query":"…"}]}"""

LABEL_SYSTEM = """你在为健康科普核查评测集给一条说法建议标签。只依据给你的来源（权威度 0–4），不要用自己的知识补充。
标签：correct 与权威来源一致；partial 大体对但夸大、遗漏条件；wrong 与权威来源矛盾；unverifiable 来源不足以判断。
只返回 JSON：{"label":"…","reason":"40 字以内，指出依据","evidence":["用到的来源 url"]}"""


async def draft_claims(llm, text: str) -> list[dict]:
    raw = await fe.ask_json(llm, CLAIMS_SYSTEM, text)
    return [c for c in (raw or {}).get("claims") or [] if isinstance(c, dict) and c.get("claim")][:4]


async def suggest(llm, claim: dict) -> dict:
    from modules.agent import web
    try:
        found = [r for r in await web.search(claim.get("query") or claim["claim"], 8) if (r.authority or 0) >= 3][:5]
    except web.WebError:
        found = []
    sources = [{"url": r.url, "title": r.title, "site": r.site, "authority": r.authority, "summary": r.snippet[:300]} for r in found]
    if not sources:
        return {"label": "unverifiable", "reason": "没有搜到权威度 ≥3 的来源", "evidence": [], "sources": []}
    raw = await fe.ask_json(llm, LABEL_SYSTEM, json.dumps({"claim": claim["claim"], "sources": sources}, ensure_ascii=False)) or {}
    label = raw.get("label") if raw.get("label") in fe.LABELS else "unverifiable"
    urls = {s["url"] for s in sources}
    return {"label": label, "reason": str(raw.get("reason") or "")[:120],
            "evidence": [u for u in raw.get("evidence") or [] if u in urls], "sources": sources}


def review_sheet(spec: dict) -> str:
    out = ["# 科普核验评测：待确认标签", "",
           "每条说法给了建议标签和依据。确认无误就在 `backend/evals/factcheck.json` 里把该条目的 `reviewed` 改成 `true`；",
           "标签不对就改 `label`，并在 `evidence` 里放你依据的权威链接。也可以直接把修改意见发给 Claude。", "",
           "标签：正确 correct · 部分正确 partial · 错误 wrong · 无法核实 unverifiable", ""]
    for key, item in spec["items"].items():
        mark = "✅ 已确认" if item.get("reviewed") else "⬜ 待确认"
        out += [f"## {mark} · {key} · {item.get('title', '')}", "", f"{item['url']}（{item.get('note', '')}）", ""]
        for c in item["claims"]:
            out.append(f"- **{c['id']}** {c['claim']}")
            out.append(f"  - 原话：「{c.get('quote', '')}」")
            out.append(f"  - 标签：**{fe.NAMES[c['label']]}**（{c['label']}）— {c.get('reason', '')}")
            for u in c.get("evidence") or []:
                out.append(f"  - 出处：{u}")
        out.append("")
    return "\n".join(out)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--topic", action="append", help="search this topic or TOPICS key (repeatable); default: all TOPICS")
    parser.add_argument("--url", action="append", help="draft this link instead of searching (repeatable)")
    parser.add_argument("--key", action="append", help="item key for each --url, in the same order")
    parser.add_argument("--review", action="store_true", help="only rewrite the review sheet")
    args = parser.parse_args()

    spec = json.loads(fe.ITEMS.read_text()) if fe.ITEMS.exists() else {"items": {}}
    if not args.review:
        drafted_topics = {i.get("topic") for i in spec["items"].values()}
        drafted_urls = {i["url"] for i in spec["items"].values()}
        picks: dict[str, dict] = {}
        if args.url:
            keys = args.key or []
            for n, url in enumerate(args.url):
                key = keys[n] if n < len(keys) else key_of(url)
                if key not in spec["items"] and url not in drafted_urls:
                    picks[key] = {"url": url, "topic": "", "title": ""}
        else:
            wanted = [(t, TOPICS[t]) if t in TOPICS else (next((k for k, v in TOPICS.items() if v == t), key_of(t)), t)
                      for t in args.topic] if args.topic else [(k, t) for k, t in TOPICS.items() if t not in drafted_topics]
            for key, topic in wanted:
                if key in spec["items"]:
                    continue
                video = await search_bilibili(topic)
                if not video or video["url"] in drafted_urls:
                    print(f"  · {topic}: 没有合适的视频")
                    continue
                print(f"  · {topic}: {video['title'][:30]}（{video['author']} · {video['plays']} 播放）")
                picks[key] = {**video, "topic": topic}
                await asyncio.sleep(1)  # gently: one search a second
        if picks:
            from modules.llm import LLMConfig, create_client
            qa.VIDEOS = fe.DATA / "videos.json"
            with qa.Backend({"GONGJING_DATA_DIR": str(fe.DATA)}) as backend:
                async with httpx.AsyncClient(base_url=backend.base, timeout=60) as client:
                    ids = await qa.prepare(client, {k: {"url": v["url"]} for k, v in picks.items()})
                    llm = create_client(LLMConfig.from_env())
                    for key, pick in picks.items():
                        if key not in ids:
                            continue
                        claims = await draft_claims(llm, await content(client, ids[key]))
                        if not claims:
                            print(f"  ✗ {key}: 没有可核实的健康说法")
                            continue
                        rows = []
                        for n, c in enumerate(claims, 1):
                            s = await suggest(llm, c)
                            rows.append({"id": f"c{n}", "claim": c["claim"], "quote": c.get("quote", ""), "label": s["label"],
                                         "reason": s["reason"], "evidence": s["evidence"], "suggested": s["label"]})
                        title = pick.get("title") or (await client.get(f"/api/link-jobs/{ids[key]}")).json()["video"]["title"]
                        spec["items"][key] = {"url": pick["url"], "title": title, "topic": pick.get("topic", ""),
                                              "note": f"{pick.get('author', '')} · {pick.get('plays', 0)} 播放".strip(" ·"),
                                              "reviewed": False, "claims": rows}
                        fe.ITEMS.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
                        print(f"  ✓ {key}: {len(rows)} 条说法 · 建议 " + "、".join(fe.NAMES[r['label']] for r in rows))
                    await llm.aclose()
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text(review_sheet(spec))
    print(f"待确认清单：{REVIEW.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    asyncio.run(main())
