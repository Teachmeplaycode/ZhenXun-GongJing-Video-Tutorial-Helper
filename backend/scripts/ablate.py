"""Which lessons of a kind actually help: answer that kind's validation questions once without each lesson.

    uv run python scripts/ablate.py --kind 动作重复了几次 [--experience data/bench/experience-r2.json] [--n 60]

For the kind's MotionBench type, each lesson is left out in turn (a copy of the experience file without it)
and the type's validation questions are answered with config D3 at temperature 0; then without the whole
kind, and with every lesson. Accuracy is compared with the full set on the same questions (paired test):
a lesson whose removal *raises* accuracy is doing harm. Validation questions never overlap the test split
or the training runs the lessons came from.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bench import BENCH, RESULTS, mcnemar  # noqa: E402
from experience import KINDS  # noqa: E402

TYPE_OF = {kind: t for t, kind in KINDS.items()}


def run(config: str, exp: Path, kind_type: str, n: int, seed: int, tag: str) -> dict:
    before = set((RESULTS / "val").glob("*.json"))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "bench.py"), "--config", config, "--val", "--n", str(n), "--seed", str(seed),
                    "--tag", "val", "--types", kind_type, "--set", "LLM_TEMPERATURE=0", "--set", f"EXPERIENCE_FILE={exp}"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    new = sorted(set((RESULTS / "val").glob("*.json")) - before)
    result = json.loads(new[-1].read_text())
    new[-1].rename(new[-1].with_name(f"{new[-1].stem}-ablate-{tag}.json"))
    if any("余额不足" in (r.get("error") or "") for r in result["results"]):
        raise SystemExit("模型账户余额不足，停止")
    return {r["uid"]: r["correct"] for r in result["results"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kind", required=True, choices=sorted(TYPE_OF))
    parser.add_argument("--experience", type=Path, default=BENCH / "experience-r2.json")
    parser.add_argument("--n", type=int, default=60)
    parser.add_argument("--seed", type=int, default=31)
    args = parser.parse_args()

    data = json.loads(args.experience.read_text())
    lessons = data["lessons"][args.kind]
    folder = BENCH / "ablation" / time.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)

    def variant(name: str, kept: list[str] | None) -> Path:
        copy = json.loads(json.dumps(data))
        if kept is None:
            copy["lessons"].pop(args.kind)
        else:
            copy["lessons"][args.kind] = kept
        path = folder / f"{name}.json"
        path.write_text(json.dumps(copy, ensure_ascii=False, indent=1))
        return path

    kind_type = TYPE_OF[args.kind]
    print(f"{args.kind}（{kind_type}）：{len(lessons)} 条经验，每次在 {args.n} 道验证题上作答")
    full = run("D3", variant("all", lessons), kind_type, args.n, args.seed, "all")
    rows = [("全部经验", full)]
    rows.append(("去掉这一类全部经验", run("D3", variant("none", None), kind_type, args.n, args.seed, "none")))
    for i, lesson in enumerate(lessons):
        rows.append((f"去掉第 {i + 1} 条", run("D3", variant(f"minus{i + 1}", lessons[:i] + lessons[i + 1:]), kind_type, args.n, args.seed, f"minus{i + 1}")))

    uids = sorted(full)
    report = []
    for name, got in rows:
        acc = sum(got[u] for u in uids) / len(uids)
        only_full, only_this, p = mcnemar([full[u] for u in uids], [got[u] for u in uids])
        report.append({"variant": name, "acc": acc, "only_full": only_full, "only_this": only_this, "p": p})
        print(f"  {name:<12} {acc * 100:5.1f}%   只有全部经验对 {only_full:2}，只有这个版本对 {only_this:2}，p = {p:.2f}")
    for i, lesson in enumerate(lessons):
        print(f"  第 {i + 1} 条：{lesson[:90]}…")
    (folder / "report.json").write_text(json.dumps({"kind": args.kind, "lessons": lessons, "rows": report}, ensure_ascii=False, indent=1))
    print(f"结果：{folder / 'report.json'}")


if __name__ == "__main__":
    main()
