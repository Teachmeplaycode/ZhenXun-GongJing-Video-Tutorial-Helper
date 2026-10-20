# 帧见复现指南

帧见是可回到原片的视频理解助手。本文对应源码 `34b38f0f74a1b85dd1cba167a4063a6642eab44f`，C 工作线只增加参赛文档；比赛日期按用户提供的 **11 月 10 日**，年份及赛程尚未核实。

## 验证边界

CodeArts Linux 会话生成了初稿；主会话在 macOS Apple Silicon 的独立 `docs/competition` 工作区核对了源码、JSON 数量、三个评测脚本的 `--help`。下列从零安装、真实视频导入、ASR/OCR、模型问答及浏览器演示尚未完整实跑。不得把命令帮助通过算成端到端验收通过。实际命令结果见 [PROCESS.md](PROCESS.md)。

## macOS Apple Silicon 从零准备

需要 Git、Python >=3.11、uv、Node.js 和 ffmpeg。首次模型下载、浏览器下载及依赖安装需要网络。

```bash
brew install uv node ffmpeg
git clone https://github.com/Teachmeplaycode/MyTargetProject.git MyTargetProject-reproduce
cd MyTargetProject-reproduce
git switch --detach 34b38f0f74a1b85dd1cba167a4063a6642eab44f
(cd backend && uv sync)
(cd front && npm ci)
(cd backend && uv run playwright install --only-shell chromium)
```

上述安装命令是复现步骤，本轮未在全新系统上执行。无仓库访问权限时由仓库所有者开通正常 GitHub 访问；不要把 token 写进 URL 或文档。

在新副本的 `backend/.env` 中由用户配置问答模型。只列变量名称，不放真实值：

| 变量 | 作用 |
| --- | --- |
| `DEEPSEEK_API_KEY` 或 `LLM_API_KEY` | 默认 OpenAI 兼容问答服务的凭据 |
| `LLM_BASE_URL`、`LLM_MODEL` | 自定义兼容服务地址与模型 |
| `LLM_PROVIDER=ollama` | 改用本机 Ollama；无需远程问答密钥，需用户自行准备服务与模型 |
| `DECISION`、`DECISION_MODEL`、`DECISION_URL` | 本地决策模块；不可用时的行为以对应代码版本为准 |
| `SCREENTEXT`、`ASR_MODEL`、`ASR_LANGUAGE` | 画面文字和语音转写设置 |
| `BROWSER`、`TAVILY_API_KEY`、`OPENALEX_API_KEY` | 浏览器、搜索备用、论文检索 |
| `YUANBAO_COOKIE`、`BILIBILI_COOKIE` | 平台登录；优先用页面的扫码登录流程 |

完整配置见 [后端说明](../../backend/README.md)。`.env` / `.env.accounts` 只留在本地，勿提交、截图或上传。不要复制主工作区的配置到云沙箱。

## 独立服务与视频导入

从新副本根目录运行：

```bash
export GONGJING_DATA_DIR="$(mktemp -d /tmp/gongjing-reproduce.XXXXXX)"
export API_PORT=8024 WEB_PORT=5204
./dev.sh --check
./dev.sh
```

打开 <http://localhost:5204>。如端口被占用，换一对空闲端口；不要停止用户现有 8000/5173 服务。退出时 Ctrl+C 只结束本次前台启动的副本。保留临时目录以检查结果，需清理时先确认其内容。

1. 导入用户有权使用的软件教程链接或本地视频，记录链接、时长、解析/抽帧/转写状态及耗时。
2. 等待推荐问题，点一个真实步骤问题，查看结论是否带原声、画面文字或画面时间证据。
3. 点时间引用回看原片，检查时间位置和播放器状态；缺原片时必须如实显示缓存/不可用状态。
4. 问视频未涉及的内容，检查是否承认证据不足。

本地上传的视频可保留原片供回放；主动删除原片后，缓存画面和文本仍可用，原片回放不可用。平台视频也可能因链接过期、权限或网络限制无法回放。以 `backend/app.py` 的 media/source API 及实际 UI 状态为准，勿沿用旧注释中“处理即删”的表述。人工验收集 D 由用户选片、确认答案，本文不代填。

## 自动检查与真实评测

在副本中运行：

```bash
(cd backend && uv run pytest)
(cd front && npm run build)
(cd front && npm run test:e2e)
(cd backend && uv run python scripts/eval.py --help)
(cd backend && uv run python scripts/factcheck_eval.py --help)
(cd backend && uv run python scripts/bench.py --help)
```

前端现有 Playwright 配置使用独立 5199，mock 所有 API，不调用真实模型；若已占用，需要在不提交的临时配置中换端口，不复用其他服务。单元测试/E2E 通过也不能证明模型准确率。

以下为真实评测命令说明，**本轮未执行真实评测**，运行前需确认费用和数据。科普评测必须先由用户完成至少一条标准答案复核、在 `backend/evals/factcheck.json` 中标记 reviewed，再运行默认命令。当前 reviewed=0，直接执行会在启动后端/模型前退出并提示“没有要跑的条目”；这是前置条件未满足，不是一次真实评测。`--drafts` 仅供诊断，不能代替人工标签。

```bash
cd backend
uv run python scripts/eval.py --judge
uv run python scripts/factcheck_eval.py
uv run python scripts/bench.py --config E --n 100
uv run python scripts/bench.py --config E --val --n 60 --seed 31 --set LLM_TEMPERATURE=0
```

`eval.py` 当前是 11 个视频、47 道题（旧 README 的 7/29 已过时）。`factcheck_eval.py` 是独立脚本，没有 `eval.py --factcheck` 参数；默认只评测人工标为 reviewed 的条目，目前 42 条草稿、165 条说法、reviewed=0。`--drafts` 可跑草稿，仅供诊断，不能当人工确认的准确率。

这些评测脚本分别使用 `backend/data/evals`、`backend/data/evals-factcheck`、`backend/data/bench` 等目录，部分路径由脚本常量指定；不能仅设 `GONGJING_DATA_DIR` 就声称全部结果已重定向。请在新副本运行并保留结果，不触碰用户主工作区的数据。MotionBench 需要准备对应视频、题目和校准表；命令语法正确不保证外部数据可取得。

## Linux 与待验证事项

Linux 适配由 [Issue #8](https://github.com/Teachmeplaycode/MyTargetProject/issues/8)、`feat/cloud-adapters` 工作线负责。其 PR 尚待建立/验证，不能把本指南的 macOS 启动步骤直接当成当前 main 已通过的 Linux 流程。适配分支计划增加 faster-whisper/RapidOCR，可用性与安装命令以 A 分支实际 PR 为准。

待验证：全新 Mac 安装；指定真实视频的 ASR/OCR/问答/回看；Linux 容器或实际 Linux 流程；真实模型准确率与费用；多浏览器演示；人工验收集 D。记录机器、源码 SHA、命令、退出码、耗时与数据来源后再更新完成状态。
