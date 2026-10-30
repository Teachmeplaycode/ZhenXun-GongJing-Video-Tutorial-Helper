# 演示视频素材

| 文件 | 来源 | 处理 |
| --- | --- | --- |
| `zhenxun-demo.mp4` | 项目作者剪辑的完整演示（2560×1440，120 fps，177 秒） | 压缩为 1080p、30 fps，保留完整时长与音轨 |
| `zhenxun-demo-poster.jpg` | 同上，第 9 秒 | 静帧 |
| `gif/01-…gif` – `gif/14-…gif` | 宣传片工程 `feat/promo-video` 的 `DemoClip01`–`DemoClip14` 合成（`out/demo3/clip-*.mp4`），每段一个功能 | 完整时长，560 px 宽、6 fps、96 色；不含音效 |

录屏于 2026-10-27 在线上站 linyi.work/ZhenXun 用 `record/record.mjs` 的 `sc-*` 场景录制，演示视频来自 `datas/yanshi.txt` 的案例；操作按原速播放，等待解析或生成的时间被剪去。

`manifest.json` 记录每个文件的来源路径与 SHA-256。处理命令：

```bash
# 完整演示
ffmpeg -i 完整了.mp4 -vf "fps=30,scale=1920:-2:flags=lanczos" -c:v libx264 -preset slow -crf 25 \
  -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart zhenxun-demo.mp4
# 每段 GIF
ffmpeg -i clip-NN.mp4 -an -vf "fps=6,scale=560:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" NN-name.gif
```
