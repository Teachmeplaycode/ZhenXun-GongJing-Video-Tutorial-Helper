"""Summarize the structured logs (modules/log.py): answers, speed, tokens, tools, failures.

    uv run python scripts/log_stats.py            # last 7 days
    uv run python scripts/log_stats.py --days 1
    uv run python scripts/log_stats.py --errors   # also list the latest failures in full

Reads <data>/logs/*.jsonl (GONGJING_DATA_DIR, as the server).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

DATA_ROOT = Path(os.environ.get("GONGJING_DATA_DIR") or Path(__file__).resolve().parents[1] / "data")


def load(days: float) -> list[dict]:
    since = time.time() - days * 86400
    records = []
    for path in sorted((DATA_ROOT / "logs").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("ts", 0) >= since:
                records.append(r)
    return records


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(q * (len(values) - 1) + 0.5))]


def secs(ms: float) -> str:
    return f"{ms / 1000:.1f}s"


def report(records: list[dict], show_errors: bool) -> str:
    out = []
    by = defaultdict(list)
    for r in records:
        by[r["event"]].append(r)

    answers = by["answer"]
    out.append(f"## 回答  {len(answers)} 次")
    if answers:
        status = Counter(a["status"] for a in answers)
        out.append("状态：" + "  ".join(f"{k} {v}" for k, v in status.most_common()))
        done = [a for a in answers if a["status"] == "done"]
        times = [a["elapsed_ms"] for a in done]
        if times:
            out.append(f"耗时（完成的）：中位 {secs(pct(times, 0.5))}  P90 {secs(pct(times, 0.9))}  最长 {secs(max(times))}")
        def token_stat(field, label):
            full = [a[field] for a in answers if a.get(field) is not None]
            # A partial record has a known lower bound. Never add it twice to a full total.
            known = [a[field] if a.get(field) is not None else a.get("known_" + field) for a in answers]
            known = [n for n in known if n is not None]
            total = f"{sum(known)} tokens" if known else "未知（无已知计数）"
            average = f"{sum(full) / len(full) / 1000:.1f}k" if full else "未知"
            return f"{label}已知共 {total}（完整字段均值 {average}，完整 {len(full)}/{len(answers)}）"

        incomplete = sum(a.get("usage_complete") is False or a.get("prompt_tokens") is None
                         or a.get("completion_tokens") is None for a in answers)
        out.append(f"token（已知下界；不完整 {incomplete}/{len(answers)} 次）："
                   + token_stat("prompt_tokens", "输入") + "  " + token_stat("completion_tokens", "输出"))
        models = Counter(a.get("model") for a in answers if a.get("model"))
        if models:
            out.append("模型：" + "  ".join(f"{k} {v}" for k, v in models.most_common()))
        codes = Counter(a.get("code") for a in answers if a["status"] == "error")
        if codes:
            out.append("失败原因：" + "  ".join(f"{k} {v}" for k, v in codes.most_common()))

        tools = defaultdict(list)
        for a in answers:
            for t in a.get("tools") or []:
                tools[t["name"]].append(t)
        if tools:
            out.append("\n## 工具")
            out.append(f"{'工具':<28}{'次数':>6}{'失败':>6}{'中位耗时':>10}{'P90':>8}")
            for name, ts in sorted(tools.items(), key=lambda kv: -len(kv[1])):
                ms = [t["ms"] for t in ts if t.get("ms") is not None]
                fails = sum(1 for t in ts if t.get("ok") is False)
                out.append(f"{name:<28}{len(ts):>6}{fails:>6}{secs(pct(ms, 0.5)):>10}{secs(pct(ms, 0.9)):>8}")

    resolves = by["link.resolve"]
    if resolves:
        failed = [r for r in resolves if not r.get("ok")]
        out.append(f"\n## 链接解析  {len(resolves)} 次，失败 {len(failed)}")
        platforms = Counter(r.get("platform") for r in resolves if r.get("ok"))
        out.append("平台：" + "  ".join(f"{k} {v}" for k, v in platforms.most_common()))
        if failed:
            out.append("失败原因：" + "  ".join(f"{k} {v}" for k, v in Counter(r.get("code") for r in failed).most_common()))
    frames = by["link.frames"]
    if frames:
        missing = sum(1 for f in frames if f.get("missing"))
        out.append(f"抽帧：{len(frames)} 次，中位 {secs(pct([f['ms'] for f in frames], 0.5))}，有缺帧 {missing} 次")
    transcripts = by["transcript"]
    if transcripts:
        st = Counter(t.get("status") for t in transcripts)
        out.append(f"转写：{'  '.join(f'{k} {v}' for k, v in st.most_common())}，中位 {secs(pct([t['ms'] for t in transcripts], 0.5))}")

    logins = by["account.login"]
    if logins:
        out.append("\n## 扫码登录  " + "  ".join(f"{p}/{s} {n}" for (p, s), n in Counter((l["platform"], l["state"]) for l in logins).most_common()))

    errors = by["error"] + [r for r in by["request.failed"]]
    out.append(f"\n## 异常  {len(by['error'])} 个未处理，{len(by['request.failed'])} 个请求失败")
    if errors:
        where = Counter((e.get("where") or e.get("path"), e.get("type") or e.get("code")) for e in errors)
        for (w, t), n in where.most_common(8):
            out.append(f"  {n:>3} × {w}  {t}")
    if show_errors:
        failures = [r for r in records if r["event"] == "error" or (r["event"] == "answer" and r["status"] == "error")]
        for r in failures[-10:]:
            when = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            out.append(f"\n--- {when} {r['event']} {r.get('where') or r.get('code') or ''}")
            out.append(str(r.get("message") or ""))
            if r.get("trace"):
                out.append(r["trace"].rstrip())
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--errors", action="store_true", help="list the latest failures in full")
    args = parser.parse_args()
    records = load(args.days)
    if not records:
        print(f"{DATA_ROOT / 'logs'} 里最近 {args.days:g} 天没有日志。")
        return
    print(f"# 最近 {args.days:g} 天，{len(records)} 条记录\n")
    print(report(records, args.errors))


if __name__ == "__main__":
    main()
