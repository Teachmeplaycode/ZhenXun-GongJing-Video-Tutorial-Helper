# 码道使用证明与验证脚本

### 评审查看顺序

1. **网页版码道，10 月 30 日**：[原始截图 01–05](screenshots/)。记录首轮提问、FFmpeg 失败定位、修复前回归、修复后全量测试和消息分组重构。对照[修复前回归](results/web-codearts-regression-before.txt)、[修复后回归](results/web-codearts-regression-after.txt)及[全量后端测试](results/web-codearts-backend-final.txt)。
2. **CodeArts IDE 插件，10 月 31 日**：[原始截图 06–08](screenshots/)。记录插件阅读核心代码、生成并采纳截图附件与预看顺序的边界测试。对照[基线测试](results/ide-plugin-baseline.txt)和[修复后测试](results/ide-plugin-patched.txt)。
3. **网页版码道，11 月 2–3 日**：[原始截图 09–10](screenshots/)。记录 Windows 本机版需求和启动器实现。最终交付可查[合并 PR](https://github.com/Teachmeplaycode/ZhenXun-GongJing-Video-Tutorial-Helper/pull/111)和[独立验收 CI](https://github.com/Teachmeplaycode/ZhenXun-GongJing-Video-Tutorial-Helper/actions/runs/41561246382)。

### 脚本用途

| 脚本 | 用途 |
| --- | --- |
| [diagnose_replay_frame_sampling.py](scripts/diagnose_replay_frame_sampling.py) | 比较普通抽帧与慢放复看的真实采样结果。 |
| [diagnose_agent_tool_loop.py](scripts/diagnose_agent_tool_loop.py) | 验证 Agent 工具循环中的末轮调用、错误回传和异常路径。 |
| [diagnose_web_search_and_fetch.py](scripts/diagnose_web_search_and_fetch.py) | 分别记录模拟工具路径和真实网页搜索、抓取结果。 |
| [diagnose_markdown_timestamps.mjs](scripts/diagnose_markdown_timestamps.mjs) | 验证 Markdown 时间戳的识别与跳转回调。 |
| [test_prelook_attachment_edges.py](scripts/test_prelook_attachment_edges.py) | IDE 插件生成的截图附件与预看组合边界回归。 |

脚本是当时验证所用的原件，文件名按用途整理。它们引用对应历史版本的源码和依赖。这里展示的是公开评审所需的截图和结果摘选，测试日志为当时的实际运行记录。
