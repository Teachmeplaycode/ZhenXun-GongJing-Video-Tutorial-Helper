# 演示视频素材

素材来自项目 `feat/promo-video` 分支对应的宣传片工程。找到的本地文件保存在相邻目录 `MyTargetProject-visitors/video/zhenxun-promo/`；原录屏与成片是未纳入 Git 的本地资产，本次将精选的压缩版复制进当前仓库，README 不依赖外部工作目录。

| 当前文件 | 原文件（相对宣传片工程） | 时长 | 处理 |
| --- | --- | --- | --- |
| `zhenxun-demo-cut.mp4` | `out/v4/zhenxun-demo-cut.mp4` | 78.229 秒 | 1080p → 720p，保留完整时长与音轨 |
| `zhenxun-reel.mp4` | `out/v4/zhenxun-reel.mp4` | 87.317 秒 | 1080p → 720p，保留完整时长与音轨 |
| `demo-cut-poster.jpg` | 实机操作剪辑 | 第 22 秒 | 从原片提取 |
| `reel-poster.jpg` | 功能巡览 | 第 10 秒 | 从原片提取 |

打开 [index.html](index.html) 可本地播放两部影片；GitHub README 使用封面链接到 MP4，具体内嵌播放支持取决于 Markdown 阅读器。

两部成片沿用原有配乐、字幕、加速和镜头运动。源录屏拍摄于 2026-10-22，不能将加速演示视为实际响应速度；当前功能入口和文案可能已变化。对应原工程的音效来源说明保存在 `feat/promo-video:video/zhenxun-promo/public/sfx/CREDITS.md`。

压缩命令（对每部原片执行）：

```bash
ffmpeg -i SOURCE.mp4 -vf scale=1280:-2 -c:v libx264 -preset fast -crf 26 \
  -c:a aac -b:a 96k -movflags +faststart OUTPUT.mp4
```

`manifest.json` 记录原素材相对路径、静帧位置和 SHA-256，可核对来源。原文件没有改动。
