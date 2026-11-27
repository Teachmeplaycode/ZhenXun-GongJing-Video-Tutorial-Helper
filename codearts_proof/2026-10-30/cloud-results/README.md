# CodeArts 云端复现记录（2026-10-30）

- **复现对象**：MyTargetProject 主线 main，原始版本 `0a17ddd8def71d92b5c67505b6349061628e37a5`（0a17ddd，"README: the full demo video and a GIF per feature (#110)"，2026-10-30 20:29 +0800）
- **执行环境**：华为云 CodeArts 沙箱（openEuler 22.03 aarch64，Python 3.12.13，Node 22）；uv 不可用，按 uv.lock 关键包版本用 pip 手动安装（见下"依赖口径"）
- **实际执行时间**：2026-10-30 21:50 – 2026-10-31 00:55 (+0800)
- **分支**：`codex/codearts-repro-20261030`（自 0a17ddd 切出；本目录为该分支第二个提交；`fix-question-last.patch` 为第一个提交的补丁原文）

## 本次做了什么

1. **沿主线分阶段复现**（1d9590f 初版 → 9c38a51 工具调用 → 93bcda8 Markdown 时间戳 → b7e6abc 联网检索 → 089cd2d OCR+慢放复看 → 3f3e130/bee488a 代码核对 → 0a17ddd 全量实跑）：每个阶段的测试、构建、smoke 与诊断详见 `REPRODUCTION.md`（含全部实际命令与原始退出码）。
2. **诊断脚本**（`tests/`，均不改原始代码）：工具循环收尾边界、Markdown 时间戳误识别、联网工具失败路径、慢放采样密度（真实 ffmpeg 短片）。
3. **修复一个实际 bug**（`fix-question-last.patch`，回归测试 6 项）：预看注入曾用 `pop()` 取末条 user 消息的"最后一项"当作问题——有截图附件时最后一项是附件，导致截图标签/图片/定位说明被挪到复看帧之后。修复为 build_messages 增加 `prelook` 参数按命名分组组装，不再扫描文案前缀也不猜位置。
4. **环境对照**：ffmpeg 旧构建（npm @ffmpeg-installer N-49006，2019）不支持 `-stats_period` → test_cuts 1 例失败；经 PyPI `imageio-ffmpeg` 渠道取得 **ffmpeg 7.0.2 aarch64**（持久化于沙箱 `/workspace/tools/imageio/ffmpeg`，二进制不入库）→ **后端全量 1205 passed, 4 skipped, 0 failed**（`logs/stage08-pytest-full-v2.log`）。fps 滤镜低速率取帧偏移经新旧两版对照确认行为一致（非版本问题）。

## 依赖口径（重要）

pip 实装 73 包与 uv.lock（102 包，含全平台）**关键 28 包逐一对齐**（`pip-freeze-installed.txt` 为实际清单）；未装 29 包为 darwin 专属 / uvicorn 可选加速器等。**这是"关键包版本对齐 + 1205 项测试通过"的手动 pip 复现，不等价于 `uv sync --locked` 的完整锁文件复现。**

## 未完成项（如实）

1. Playwright Chromium 未安装：4 项 browser 测试 skip、前端 e2e 未跑
2. 无 LLM_API_KEY：真实模型问答链路（图片/工具调用/流式）未实测，仅 MockTransport 验证
3. faster-whisper small 可导入但模型权重未下载：真实语音转写效果未知
4. ddgs 联网搜索：出口对多数引擎域名不可达（原因未查明，日志保留实际错误）
5. 沙箱 kill 信号无效：四个测试进程（127.0.0.1:17431/17432/14331/17433）TERM+KILL 均无法终止，已核对 PID/cmdline/cwd 确认属于本次测试目录（见 `logs/stage09-cleanup.log`），均绑定 127.0.0.1 不影响外部

## 目录

- `REPRODUCTION.md`：分阶段复现文档（口径纪律：估算/实测/代码核对分别标注）
- `tests/`：4 个诊断脚本（附运行方式注释）
- `logs/`：43 个原始日志（pytest 退出码直捕、构建、smoke、诊断输出、失败-修复前后分开留存）
- `pip-freeze-installed.txt`：实装依赖清单
- `fix-question-last.patch`：run.py 修复补丁（即本分支第一个提交）

Gitee 推送：本分支推送至 `git@gitee.com:Teachmeplaycode/MyTargetProject.git` 的 `codex/codearts-repro-20261030`；`main` 保持 `0a17ddd` 不动。推送使用专用 ed25519 部署密钥（公钥指纹 `SHA256:P7ZrkYYv2yfW7ggIU+RLs/pxgX2FfRnHRJcDd+c4TBs`，私钥不入库不出对话）。
