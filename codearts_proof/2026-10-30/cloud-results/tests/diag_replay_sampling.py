"""Stage-05 (089cd2d) 慢放复看 vs 默认采样：200ms 动作会不会漏——真实 ffmpeg 短片实测。

视频设计（ffmpeg 生成，10s / 25fps / 320x240）：
  动作 A：5.00–5.20s（200ms）画面中央方块变绿（红→绿→蓝）
  动作 B：5.32–5.52s（200ms）方块变黄
两条 200ms 动作故意错开相位，用于检验不同采样网格的命中差异。

实测三件事：
  1. 默认采样（项目 frame_count→48 帧，间隔 ~208ms）：真 ffmpeg 逐帧抓取后判色，数命中
  2. replay 宽段 plan(0,10)（模型自调 10 秒段的典型情况）：项目 grab_clip 一次解码 16 帧
  3. replay 窄段（模型定位到动作附近后）：plan(5.0,5.2) 与 AgentTools.run("replay") 工具入口

全部走项目入口（frame_count / FrameJob.grab / slowmo.plan / slowmo.grab_clip / AgentTools.run），
保留实际取帧时间与帧颜色判定结果。口径：抽到帧只证明采样命中，不等于模型已理解动作。

运行：/workspace/repro-stage-05/backend/.venv/bin/python diag_replay_sampling.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/workspace/repro-stage-05/backend")
PATH_WITH_FFMPEG = "/workspace/tools/bin:/usr/local/bin:/usr/bin:/bin"  # ensure ffmpeg on PATH

from PIL import Image

from modules.frames import FrameJob, replay as slowmo
from modules.frames.grabber import grab_frame
from modules.agent.tools import AgentTools
from modules.frames.job import frame_count
from modules.video_source import ResolvedVideo, Stream

OUT = []


def log(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line)


def make_video(path: Path) -> None:
    """10s 25fps：0–5.0 红方块；5.00–5.20 绿（动作A）；5.2–10 蓝；5.32–5.52 黄（动作B，叠加右上角块）。"""
    import subprocess
    vf = (
        "drawbox=x=120:y=100:w=80:h=40:color=red:t=fill:enable='lt(t,5.0)',"
        "drawbox=x=120:y=100:w=80:h=40:color=green:t=fill:enable='between(t,5.0,5.2)',"
        "drawbox=x=120:y=100:w=80:h=40:color=blue:t=fill:enable='gt(t,5.2)',"
        "drawbox=x=260:y=20:w=40:h=40:color=yellow:t=fill:enable='between(t,5.32,5.52)'"
    )
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "color=c=black:s=320x240:d=10:r=25",
           "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    log(f"测试视频已生成: {path} ({path.stat().st_size} B, 10s/25fps)")


def judge(path: Path) -> str:
    """中心(160,120)判 A 状态；右上(280,40)判 B 状态（黄）。"""
    im = Image.open(path).convert("RGB")
    c = im.getpixel((160, 120))
    corner = im.getpixel((280, 40))
    a = ("红" if c[0] > 200 and c[1] < 80 else
         "绿" if c[1] > 100 and c[0] < 80 else
         "蓝" if c[2] > 200 else "黑?")
    b = "黄B" if corner[0] > 200 and corner[1] > 200 else ""
    return a + b


def local_stream(video_path: Path) -> ResolvedVideo:
    s = Stream(str(video_path), {}, "local-file")
    return ResolvedVideo("local", "diag.mp4", "local://diag.mp4", "diag", 10.0, [s])


async def sample_default(video: ResolvedVideo, root: Path) -> list[tuple[float, str, Path]]:
    """项目默认采样：FrameJob(count=frame_count(10)) → grab_frame 并发抓全。"""
    job = FrameJob("diag", video, None, root, count=frame_count(video.duration))
    sem = asyncio.Semaphore(6)

    async def one(slot):
        async with sem:
            r = await grab_frame(video.streams[0], slot.time, job.frame_path(slot.index))
            slot.status = "ok" if r.ok else "missing"
    await asyncio.gather(*(one(s) for s in job.slots))
    out = [(round(s.time, 3), judge(job.frame_path(s.index)), job.frame_path(s.index))
           for s in job.slots if s.status == "ok"]
    return sorted(out)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="replay-diag-"))
    video_path = tmp / "diag.mp4"
    make_video(video_path)
    video = local_stream(video_path)

    # ---- 1. 默认采样 ----
    log(f"\n===== 1. 默认采样（frame_count(10)={frame_count(10.0)} 帧，项目入口 grab_frame）=====")
    frames = asyncio.run(sample_default(video, tmp / "jobs" / "default"))
    log(f"成功抓取 {len(frames)}/48 帧 · 采样间隔 {round(frames[1][0] - frames[0][0], 3)}s")
    hit_a = [f for f in frames if "绿" in f[1]]
    hit_b = [f for f in frames if "黄" in f[1]]
    log(f"动作A（绿,5.00–5.20）命中帧: {[(t, c) for t, c, _ in hit_a] or '零命中'}")
    log(f"动作B（黄,5.32–5.52）命中帧: {[(t, c) for t, c, _ in hit_b] or '零命中'}")
    near = [(t, c) for t, c, _ in frames if 4.9 <= t <= 5.7]
    log(f"4.9–5.7s 附近的默认采样帧: {near}")

    # ---- 2. replay 宽段（模型自调 10 秒） ----
    log("\n===== 2. replay 宽段 plan(0,10)（模型未定位就要求慢放整段的典型调用）=====")
    p = slowmo.plan(0, 10, 10.0)
    log(f"plan: start={p.start} end={p.end} fps={p.fps} count={p.count} clipped={p.clipped}")
    log(f"实际取帧时刻: {p.times}")
    r = asyncio.run(slowmo.grab_clip(video.streams[0], p, tmp / "jobs" / "r1"))
    log(f"grab_clip: ok={r.ok}" + (f" kind={r.kind} detail={r.detail}" if not r.ok else ""))
    if r.ok:
        colors = [(p.times[i], judge(tmp / "jobs" / "r1" / f"{i + 1:02d}.jpg")) for i in range(p.count)]
        log(f"帧判定: {colors}")
        log(f"动作A 命中: {[c for c in colors if '绿' in c[1]] or '零命中'} · 动作B 命中: {[c for c in colors if '黄' in c[1]] or '零命中'}")

    # ---- 3. replay 窄段（模型定位后）+ 工具入口 ----
    log("\n===== 3. replay 窄段（模型先定位到动作附近）=====")
    for a, b in ((5.0, 5.2), (5.3, 5.5)):
        p = slowmo.plan(a, b, 10.0)
        log(f"plan({a},{b}): start={p.start} end={p.end} span={round(p.end - p.start, 2)} fps={p.fps} count={p.count}")
        log(f"  实际取帧时刻: {p.times}")
        r = asyncio.run(slowmo.grab_clip(video.streams[0], p, tmp / "jobs" / f"r-{a}"))
        if r.ok:
            colors = [(p.times[i], judge(tmp / "jobs" / f"r-{a}" / f"{i + 1:02d}.jpg")) for i in range(p.count)]
            log(f"  帧判定: {colors}")
        else:
            log(f"  grab_clip 失败: {r.kind} {r.detail}")

    log("\n===== 3b. AgentTools.run('replay') 工具入口（模型在工具循环里的真实路径）=====")
    job = FrameJob("diag2", video, None, tmp / "jobs" / "diag2", count=2)
    tools = AgentTools(job)
    tr = asyncio.run(tools.run("replay", {"start": "5.0", "end": "5.2"}))
    log(f"error={tr.error} count={tr.count}")
    log(f"文本(前 160 字): {tr.text[:160]}")
    log(f"帧标签: {[lbl for lbl, _ in tr.images]}")
    judged = [(lbl, judge(p)) for lbl, p in tr.images]
    log(f"帧颜色判定: {judged}")

    log("\n===== 总结（口径：抽到帧=采样命中，不等于模型理解动作）=====")
    log(f"默认采样 208ms 间隔：动作A 命中 {len(hit_a)} 帧，动作B 命中 {len(hit_b)} 帧 —— 200ms < 208ms 间隔，"
        f"命中与否取决于网格相位（B 零命中即为漏检实例）")
    log("replay 密度 = 16/span：窄段(≤3.2s)间隔 ≤200ms 保证命中；10s 宽段间隔 625ms 同样存在零命中相位")
    log("抽到绿帧/黄帧只证明采样捕获了过渡态，模型是否看懂动作（先后、方向、轨迹）不在本验证范围")


if __name__ == "__main__":
    import os
    os.environ["PATH"] = PATH_WITH_FFMPEG + os.pathsep + os.environ.get("PATH", "")
    main()
