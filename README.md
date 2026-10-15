# GongJ!ng? 视频理解工作台

贴一个视频链接（B 站、视频号）或上传本地视频，系统读取画面和语音，然后可以就视频内容提问。回答时模型会按需搜索语音转写、细看某一段画面、联网查资料或检索论文，每一步都在对话里按顺序展示，可以展开查看细节。

## 跑起来

需要 macOS（Apple Silicon，语音转写用 mlx-whisper）、[uv](https://docs.astral.sh/uv/)、Node.js、ffmpeg：

```bash
brew install uv node ffmpeg
```

在 `backend/.env` 写入配置（见下表，至少要有问答模型），然后：

```bash
./dev.sh          # 检查环境 → 安装依赖 → 同时启动后端和前端，打开 http://localhost:5173
./dev.sh --check  # 只检查，不启动
```

`dev.sh` 会做这些事：

- 检查工具、`.env` 里的配置（只看有没有，不显示值）、Ollama 和决策模型；缺少必需项时停下并说明。
- 后端依赖有变化时执行 `uv sync`，前端缺依赖时执行 `npm install`。
- 8000 / 5173 上如果还跑着之前启动的本项目服务，先停掉再启动，保证运行的是最新代码；被别的程序占用则报出进程并退出，不会动它。
- 后端带 `--reload` 运行，**改代码或 `.env` 都会自动重载**；两边的日志合在一个窗口里，用 `[api]`、`[web]` 区分；Ctrl+C 两边一起停。
- 想同时跑第二份（例如测试）而不影响正在用的：`API_PORT=8011 WEB_PORT=5191 GONGJING_DATA_DIR=/某个临时目录 ./dev.sh`。

## 配置（`backend/.env`）

`.env` 已被 git 忽略。环境变量与 `.env` 同名时，环境变量优先。

| 配置 | 必需 | 作用 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 二选一 | 问答模型（默认 `deepseek-flash`，可用 `LLM_BASE_URL` / `LLM_MODEL` 换成其他 OpenAI 兼容服务） |
| `LLM_PROVIDER=ollama` | 二选一 | 改用本机 Ollama 做问答（默认 `qwen3.5:9b`），不需要 key，但慢得多 |
| `TAVILY_API_KEY` | 建议 | 联网搜索首选，每月 1000 次免费；没有时退到博查或免费的 ddgs |
| `BOCHA_API_KEY` | 可选 | 博查搜索，作为联网搜索的备用 |
| `OPENALEX_API_KEY` | 建议 | 论文检索；不带 key 每天约 100 次，带免费 key 约 1000 次 |
| `YUANBAO_COOKIE` | 视频号需要 | 腾讯元宝登录态 `hy_user=…; hy_token=…`，用来解析视频号链接；会过期 |
| `DECISION` / `DECISION_MODEL` | 可选 | 决策模块（本机 Ollama，默认开启、`qwen3.5:9b`）：过滤搜索结果、拦截网页注入、判断是否需要查资料；Ollama 没开时自动退回简单规则 |

其余配置项（转写模型、搜索引擎顺序、工具轮数等）见 [backend/README.md](backend/README.md)。

## 目录

```
dev.sh            一键检查与启动
backend/          FastAPI 后端：链接解析、抽帧、语音转写、问答与工具调用、决策模块、会话存储
  README.md       后端说明：接口、每个模块的做法与实测结果、全部配置项
front/            React + Vite 前端：导入、解析、对话、时间轴、历史
docs/
  design.md       最初的需求说明
  design_2.md     前端设计规范（视觉 token、组件、动效、对话界面）
datas/            测试数据（解析器用例）与开发过程中导出的对话记录
```

运行时数据（抽到的帧、会话数据库 `sessions.sqlite3`）在 `backend/data/`，不进 git。

## 测试

```bash
cd backend && uv run pytest               # 后端单元测试，不联网
cd backend && uv run python scripts/check_links.py   # 用 datas/ 里的真实链接验证 B 站解析（联网）
cd front && npm run build                 # 前端构建检查
```

前端目前没有自动化测试。
