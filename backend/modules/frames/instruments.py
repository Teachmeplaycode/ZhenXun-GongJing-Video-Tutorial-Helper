"""Perception instruments: turn change over time into evidence a model that only sees still images can read.

Video LLMs tend to "lack inter-frame differencing and average or ignore subtle visual cues" (MotionSight,
ICLR 2026). Rather than more frames, these measure the change directly, on a dense low-resolution decode
the model never sees (up to 15 frames/s over up to 30 s): what moves where, how the camera moves, how often
a motion repeats; plus two pictures that put the motion into a single image (a heat map and a trail).
Plain OpenCV/NumPy on the Mac; no model, no training.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .grabber import input_args
from ..video_source import Stream

# How far each reading can be trusted, measured on MotionBench training questions (never the test set),
# 2026-10-17, by scripts in the experiment log: the agent is told these with every reading.
CALIBRATION = {
    "camera": "这项估计在 41 道训练题上和标准答案一致约 54%（推近常被误判成平移，向上倾斜常测不出），只作参考，以画面为准",
    "count": "在 57 道训练题上，用峰值数的一半去选最接近的选项能选对 53%（直接用峰值数 18%，随机猜约 25%）",
}

LABEL_NAMES = {"static": "静止", "shake": "晃动", "left": "向左", "right": "向右", "up": "向上", "down": "向下",
               "in": "推近", "out": "拉远", "unknown": "无法估计"}


def reading_labels(camera: str) -> set[str]:
    """A camera reading as labels, the key of the learned calibration table (scripts/calibrate.py)."""
    out = set()
    if camera.startswith("基本静止"):
        out.add("static")
    if camera.startswith("轻微晃动"):
        out.add("shake")
    for word, label in (("镜头向左", "left"), ("镜头向右", "right"), ("镜头向上", "up"), ("镜头向下", "down"), ("推近", "in"), ("拉远", "out")):
        if word in camera:
            out.add(label)
    return out


def learned() -> dict | None:
    """The calibration table learned from practice questions (CALIBRATION_FILE), or None."""
    import json
    from modules.settings import settings

    path = settings().get("CALIBRATION_FILE", "").strip()
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def camera_note(camera: str) -> str:
    """What the right answer turned out to be when this reading came up in practice; the fixed note otherwise."""
    table = (learned() or {}).get("camera") or {}
    key = "+".join(sorted(reading_labels(camera))) or "unknown"
    row = (table.get("readings") or {}).get(key)
    if not row:
        return CALIBRATION["camera"] if not table else (
            f"这种读数在练习题里出现得太少，没有统计；总体上读数和标准答案一致约 {table.get('agreement', 0):.0%}，只作参考")
    dist = "、".join(f"{LABEL_NAMES.get(k, k)} {v:.0%}" for k, v in row["truth"].items())
    return f"在 {row['n']} 道出现过这种读数的练习题里，正确答案是：{dist}（一题可能同时属于几类）"


def count_note(peaks: int) -> tuple[str, int | None]:
    """A count estimate from the peaks, with the learned spread; (sentence, estimate)."""
    table = (learned() or {}).get("count") or {}
    if not table:
        return f"约 {round(peaks / 2)} 次——一个来回的动作通常产生两个运动峰，所以按峰值数的一半估计（{CALIBRATION['count']}）", round(peaks / 2)
    est = max(1, round(peaks * table["ratio_median"]))
    lo, hi = max(1, round(peaks * table["ratio_q1"])), max(1, round(peaks * table["ratio_q3"]))
    return (f"约 {est} 次（多半在 {lo}–{hi} 次之间）——在 {table['n']} 道练习题里，真实次数约为峰值数的 {table['ratio_median']} 倍"
            f"（一半的题落在 {table['ratio_q1']}–{table['ratio_q3']} 倍）；用这个估计选最接近的选项选对 {table['pick_with_median']:.0%}，"
            f"随机猜约 {table['chance']:.0%}"), est


MAX_SPAN = 30.0
MAX_FPS = 15.0
MAX_FRAMES = 300
WIDTH = 320            # analysis resolution
DIFF_THRESHOLD = 18    # gray levels below which a pixel change counts as noise
BLOCKS = 12            # energy curve buckets shown to the model


@dataclass
class Reading:
    start: float
    end: float
    fps: float
    frames: int
    camera: str
    camera_detail: list[str]
    energy: list[float]                # motion per bucket, 0–1 relative to the busiest
    bucket: float                      # seconds per bucket
    peaks: list[float]                 # times of motion peaks
    period: float | None               # seconds, from autocorrelation
    region: str
    images: list[tuple[str, Path]] = field(default_factory=list)


async def decode(stream: Stream, start: float, end: float, fps: float, folder: Path, timeout: float = 60) -> list[Path]:
    """Low-resolution frames at `fps` for [start, end), one seek."""
    folder.mkdir(parents=True, exist_ok=True)
    *before, i, url = input_args(stream)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *before, "-ss", f"{start:.3f}", i, url,
        "-t", f"{end - start:.3f}", "-an", "-vf", f"fps={fps},scale={WIDTH}:-2", "-q:v", "3", str(folder / "%04d.jpg"),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    try:
        await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
    return sorted(folder.glob("[0-9][0-9][0-9][0-9].jpg"))


def where(mask: np.ndarray) -> str:
    """Rough place of the moving pixels, in words."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return "几乎没有运动"
    h, w = mask.shape
    cx, cy = xs.mean() / w, ys.mean() / h
    col = "左" if cx < 0.38 else "右" if cx > 0.62 else "中"
    row = "上" if cy < 0.38 else "下" if cy > 0.62 else "中"
    spread = (xs.std() / w + ys.std() / h)
    size = "大范围" if spread > 0.45 else "局部" if spread < 0.25 else "较大范围"
    if col == row == "中":
        place = "中央"
    elif row == "中":
        place = f"{col}侧"
    elif col == "中":
        place = f"{row}部"
    else:
        place = f"{col}{row}"  # 左下, 右上 …
    return f"主要在画面{place}（{size}）"


CUT = 0.6           # colour-histogram correlation between two frames below which it's a cut. Not the share of
                    # changed pixels: a pan changes nearly every pixel but keeps the colours (found by a test).
CONSISTENT = 0.6    # |sum| / sum(|step|): how much the steps agree in direction
TRUST = 0.5         # RANSAC inlier share below which a step is not used


def cuts_between(colors: list[np.ndarray]) -> list[bool]:
    hists = []
    for c in colors:
        h = cv2.calcHist([cv2.cvtColor(c, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256])
        hists.append(cv2.normalize(h, h).flatten())
    return [cv2.compareHist(a, b, cv2.HISTCMP_CORREL) < CUT for a, b in zip(hists, hists[1:])]


def camera(grays: list[np.ndarray], times: list[float], cut: list[bool], changed: list[float]) -> tuple[str, list[str]]:
    """How the camera moves, from tracked corners and a similarity fit between frames.

    Per step: shift (in frame widths), log scale and rotation. A component counts as camera motion only
    when the steps agree in direction (summing noisy steps alone makes a still camera look like it pans);
    small steps that keep changing direction are shake. Cuts and steps with few consistent points are skipped.
    """
    w = grays[0].shape[1]
    steps, cuts = [], 0
    for k, (a, b) in enumerate(zip(grays, grays[1:])):
        if cut[k]:
            cuts += 1
            continue
        pts = cv2.goodFeaturesToTrack(a, maxCorners=300, qualityLevel=0.01, minDistance=7)
        if pts is None or len(pts) < 12:
            continue
        nxt, ok, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, None)
        good = ok.reshape(-1) == 1
        m, inliers = (cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
                      if good.sum() >= 12 else (None, None))
        if m is None or float(inliers.mean()) < TRUST:
            # Nothing lines up with the previous frame though most pixels changed: a cut with similar colours.
            if changed[k] > 0.45 and (m is None or float(inliers.mean()) < 0.2):
                cuts += 1
            continue
        steps.append((k, m[0, 2] / w, m[1, 2] / w, math.log(math.hypot(m[0, 0], m[1, 0])), math.degrees(math.atan2(m[1, 0], m[0, 0]))))
    cut_note = f"；检测到 {cuts} 处剪辑切镜，已跳过" if cuts else ""
    if len(steps) < max(3, (len(grays) - 1) // 3):
        return "无法可靠估计（能跟踪的特征点太少、主体自己在大幅运动或频繁切镜）" + cut_note, []

    def judge(part) -> str:
        if not part:
            return "无法估计"
        words = []
        for idx, thresh, label in ((1, 0.05, "x"), (2, 0.05, "y"), (3, math.log(1.06), "z"), (4, 5.0, "r")):
            vals = [s[idx] for s in part]
            net, total = sum(vals), sum(abs(v) for v in vals) or 1e-9
            if abs(net) < thresh or abs(net) / total < CONSISTENT:
                continue
            if label == "x":  # content moves left → the camera turns / moves right
                words.append(f"镜头向{'右' if net < 0 else '左'}平移（画面内容一致地向{'左' if net < 0 else '右'}移动，共约 {abs(net):.2f} 个画面宽）")
            elif label == "y":
                words.append(f"镜头向{'下' if net < 0 else '上'}移动（画面内容向{'上' if net < 0 else '下'}移动，共约 {abs(net):.2f} 个画面宽）")
            elif label == "z":
                factor = math.exp(net)
                amount = ("超过 3 倍" if factor > 3 else f"共 {factor:.2f} 倍") if net > 0 else ("缩到不足 1/3" if factor < 1 / 3 else f"共 {factor:.2f} 倍")
                words.append(f"{'推近 / 放大' if net > 0 else '拉远 / 缩小'}（{amount}）")
            else:
                words.append(f"{'顺' if net > 0 else '逆'}时针转动约 {abs(net):.0f}°")
        if words:
            return "；".join(words)
        jitter = float(np.median([abs(s[1]) + abs(s[2]) for s in part]))
        return "轻微晃动（有小幅抖动，但没有持续的平移、缩放或旋转）" if jitter > 0.004 else "基本静止"

    overall = judge(steps)
    detail = []
    if len(steps) >= 6:
        mid = len(grays) // 2
        for label, part, t0, t1 in (("前半段", [s for s in steps if s[0] < mid], times[0], times[mid]),
                                    ("后半段", [s for s in steps if s[0] >= mid], times[mid], times[-1])):
            detail.append(f"{label}（{t0:.1f}–{t1:.1f}s）：{judge(part)}")
    return overall + cut_note, detail


def peaks_of(signal: np.ndarray, times: list[float], min_gap: float) -> list[float]:
    if len(signal) < 3 or signal.max() <= 0:
        return []
    smooth = np.convolve(signal, np.ones(3) / 3, mode="same")
    floor = smooth.mean() + 0.3 * smooth.std()
    found, last = [], -1e9
    for i in range(1, len(smooth) - 1):
        if smooth[i] >= smooth[i - 1] and smooth[i] > smooth[i + 1] and smooth[i] > floor and times[i] - last >= min_gap:
            found.append(round(times[i], 2))
            last = times[i]
    return found


def period_of(signal: np.ndarray, fps: float) -> float | None:
    x = signal - signal.mean()
    if len(x) < 8 or not x.any():
        return None
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    ac /= ac[0]
    lo = max(2, int(0.2 * fps))
    best = None
    for lag in range(lo, len(ac) // 2):
        if ac[lag] > ac[lag - 1] and ac[lag] >= ac[lag + 1] and ac[lag] > 0.3:
            best = lag
            break
    return round(best / fps, 2) if best else None


def analyze(files: list[Path], start: float, fps: float, out: Path) -> Reading:
    colors = [cv2.imread(str(f)) for f in files]
    colors = [c for c in colors if c is not None]
    grays = [cv2.GaussianBlur(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), (5, 5), 0) for c in colors]
    times = [start + i / fps for i in range(len(grays))]
    diffs = [cv2.absdiff(a, b) for a, b in zip(grays, grays[1:])]
    moving = [(d > DIFF_THRESHOLD) for d in diffs]
    energy = np.array([m.mean() for m in moving]) if moving else np.zeros(1)
    heat = np.sum([m.astype(np.float32) for m in moving], axis=0) if moving else np.zeros(grays[0].shape, np.float32)

    # Energy in BLOCKS buckets, relative to the busiest one.
    buckets = np.array_split(energy, min(BLOCKS, len(energy))) if len(energy) else []
    levels = np.array([b.mean() for b in buckets]) if len(buckets) else np.zeros(1)
    rel = (levels / levels.max()).round(2).tolist() if levels.max() > 0 else [0.0] * len(levels)
    span = (len(grays) - 1) / fps

    cam, cam_detail = camera(grays, times, cuts_between(colors), [m.mean() for m in moving])
    out.mkdir(parents=True, exist_ok=True)
    images = []
    if heat.max() > 0:
        norm = (heat / heat.max() * 255).astype(np.uint8)
        overlay = cv2.addWeighted(colors[len(colors) // 2], 0.55, cv2.applyColorMap(norm, cv2.COLORMAP_JET), 0.45, 0)
        cv2.imwrite(str(out / "heat.jpg"), overlay)
        images.append(("运动热力图（红黄 = 这段时间里动得最多的地方，蓝 = 不动）", out / "heat.jpg"))
    step = max(1, len(colors) // 8)
    picked = colors[::step][:8]
    if len(picked) >= 2:
        weights = np.linspace(0.3, 1.0, len(picked))
        trail = sum(w * c.astype(np.float32) for w, c in zip(weights, picked)) / weights.sum()
        cv2.imwrite(str(out / "trail.jpg"), trail.astype(np.uint8))
        images.append(("运动轨迹叠影（同一段的 8 帧叠在一起，越清晰的越晚，模糊拖影 = 移动路径）", out / "trail.jpg"))
    region = where(heat > max(1.0, 0.3 * heat.max())) if heat.max() > 0 else "几乎没有运动"
    return Reading(round(start, 2), round(start + span, 2), fps, len(grays), cam, cam_detail, rel,
                   round(span / max(1, len(rel)), 2), peaks_of(energy, times[1:], min_gap=0.25), period_of(energy, fps), region, images)


def bar(levels: list[float]) -> str:
    ticks = "▁▂▃▄▅▆▇█"
    return "".join(ticks[min(7, int(v * 7.999))] for v in levels)
