# 实机分镜素材

线上网站 linyi.work/ZhenXun 的真实操作录屏，演示账号「帧寻演示」，示例视频是 Excel VLOOKUP 教程（tut-vlookup）。
每个功能一个镜头，供剪辑使用。录屏为 2 倍分辨率（桌面 3840×2160，手机 1170×2532），推近 2 倍仍清晰。
每个 mp4 旁边有同名 json：鼠标移动、点击、按键的时间和坐标（录屏像素），可用来做镜头跟随（src/camera.ts）。

文件在 `video/zhenxun-promo/public/rec/`（不进 git）。重录：`node record/record.mjs <镜头名…>`（会弹出 Chrome 窗口自动操作）。

| 文件 | 时长 | 尺寸 | 内容 | 关键时刻（点击 / 按键 / 标记） |
|---|---|---|---|---|
| `home.mp4` | 15s | 3840×2160 | 首页：字标与雕塑，鼠标划过导航 |  |
| `import.mp4` | 33s | 3840×2160 | 粘贴 VLOOKUP 教程链接 → 开始解析 → 等高线加载/解析进度 → 进入对话 | 6.2s wide；7.1s click；13.2s click；13.3s analysing；27.1s ready；29.3s click |
| `ask.mp4` | 23s | 3840×2160 | 打字提问「按哪个键做绝对引用」→ 回答带证据标签 | 5.6s click；7.4s click；11.0s click；14.0s press；14.0s asked |
| `evidence.mp4` | 22s | 3840×2160 | 点证据标签 → 原片跳到那一刻播放 | 6.1s click；7.9s click；12.3s click；12.4s seek；20.4s click |
| `timeline.mp4` | 22s | 3840×2160 | 鼠标沿时间轴划过，薄片逐个抬起、预览画面 | 5.7s click；7.5s click |
| `replay.mp4` | 25s | 3840×2160 | 在时间轴上拖一段 → 直接慢放，逐帧展开 | 6.4s click；8.7s click；15.7s click；15.8s replay |
| `screenshot.mp4` | 27s | 3840×2160 | 附一张卡住时的截图、不写字发送 → 回答第几步 | 5.5s click；7.8s click；15.5s attached；18.0s click；18.1s press |
| `tab.mp4` | 19s | 3840×2160 | 打几个字，灰字补全，按 Tab 采纳 | 5.6s click；8.0s click；11.5s click；16.4s press；16.4s completed |
| `notes.mp4` | 135s | 3840×2160 | 工作台 → 笔记 → 生成（约 100 秒等待，可加速）→ 预览导出 | 5.9s click；7.8s click；11.4s click；13.2s click；15.1s click；25.6s notes；28.1s click；35.7s press |
| `history.mp4` | 13s | 3840×2160 | 历史会话面板 | 7.8s click |
| `profile.mp4` | 12s | 3840×2160 | 「我的」：套餐、今日用量、平台账号 | 7.0s click |
| `docs.mp4` | 15s | 3840×2160 | 文档弹窗，滚动 | 7.0s click |
| `phone.mp4` | 35s | 1170×2532 | 手机竖屏：首页 → 会话 → 工作台章节 → 笔记 → 存为长图 | 8.0s click；10.2s click；13.5s click；15.1s click；17.9s click；19.4s click；21.5s click；23.2s click |

剪辑提示：
- 每段开头一两秒是页面加载，可以裁掉；import 输入链接时会短暂出现红字「没有识别到链接」（输入未完成），可剪掉。
- notes 的等待段（生成笔记约 100 秒）建议加速；桌面端「存为长图」没录上，长图效果用 phone 镜头。
- 导入用的是服务器上已有缓存的视频，所以解析只用了半分钟左右；真实首次导入大约 80 秒。
