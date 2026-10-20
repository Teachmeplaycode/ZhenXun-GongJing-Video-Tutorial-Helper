# 华为 AI 开发者空间部署

## 已读取的云环境（2026-10-17）

- openEuler 22.03 LTS，Linux aarch64，7 个可用 CPU，约 12 GiB 内存，无 swap。
- `/root` 所在盘约 100 GiB，初次检查约 90 GiB 可用；平台声明 `/root` 持久化。
- Python 3.11.16、Node.js 22.23.3、npm、uv、git 已提供。PyPI 与 npm 连通性检查返回 200。
- 未找到 NVIDIA / Ascend 设备节点，也未找到 nvidia-smi / npu-smi。当前按 CPU 环境部署。
- 平台显示按核时计量，关闭标签页不会立即关机；需要时从平台执行关机。
- “环境管理 → 创建 → 手动搭建”支持 bwrap 沙箱、启动脚本、读写/只读挂载以及 Web UI 端口。页面建议使用 17000–17999。
- DevBridge 能创建公网隧道。应用含上传、会话与账户接口，在访问控制确认前不要创建公开隧道。

这些信息来自当前已打开的开发者空间；尚未读取比赛完整规则，不能据此断言外部模型 API 或评审访问方式满足赛规。

## 运行结构

浏览器 → 平台的受控服务入口 → `17080` → FastAPI API + Vite 构建产物。

- 代码：`/root/workspace/gongjing`。
- 数据：普通启动脚本默认为 `/root/gongjing-data`；本轮创建的平台卡片覆盖为 `/root/runtime/gongjing/data`。由 `GONGJING_DATA_DIR` 指定，与本机历史数据隔离。
- ASR：faster-whisper，CPU int8，默认 small、4 线程、单识别任务。首次使用需要下载模型；速度与中文效果需在云端实测。
- 当前云环境访问 Hugging Face 下载失败，改用 ModelScope 的 `pengzhendong/faster-whisper-small`，约 464 MiB，落盘到 `/root/runtime/gongjing/models/whisper-small`。平台启动脚本显式使用本地路径。
- OCR：RapidOCR ONNX，默认 2 线程；保留原有 Line、字幕时间线和合并逻辑。
- Mac 原有 mlx-whisper / Vision 默认路径保留。
- 本机 Ollama 决策服务及 Playwright 浏览器工具在云启动脚本中默认关闭，待单独部署验证后开启。
- 主问答使用比赛允许且支持图片输入、工具调用与流式输出的模型服务；本项目不把平台编程助手直接当作应用模型接口。

## 准备与启动

源码包采用显式白名单，只含后端代码、前端代码、测试、依赖清单与部署脚本。

```bash
# 本机打包，生成 /private/tmp/gongjing-cloud-source.tar.gz
python3 deploy/huawei/bundle.py

# 平台资源管理器上传到 /root/workspace 后，在平台命令行运行
cd /root/workspace
tar -xzf gongjing-cloud-source.tar.gz
# 系统 ffmpeg 需含 ffprobe；ARM openEuler 上使用官方系统仓库
dnf install -y ffmpeg
bash gongjing/deploy/huawei/prepare.sh
bash gongjing/deploy/huawei/download-asr.sh
nohup bash gongjing/deploy/huawei/start.sh > gongjing-server.log 2>&1 < /dev/null &
curl --fail http://127.0.0.1:17080/api/health
```

平台卡片请使用 `platform-start.sh` 的内容作为启动脚本；它同时设置本地 ASR 权重路径与沙箱持久化数据目录。上面的普通 `start.sh` 启动方式，若也要使用已下载权重，需要设置 `ASR_MODEL=/root/runtime/gongjing/models/whisper-small`。

### 依赖解析：headless Linux 上不能让 rapidocr 拉入 opencv-python（2026-10-20 实测）

rapidocr-onnxruntime 声明依赖非 headless 的 `opencv-python`：它需要 libGL（无显示器的服务器没有），且与项目主依赖 `opencv-python-headless` 都安装 `cv2` 目录，两者共存互相破坏（后装者覆盖，卸载时又会删掉共用文件，必须强制重装才能修复）。干净 openEuler aarch64（无 libGL）上直接 `pip install rapidocr-onnxruntime` 的结果是 `import cv2` 报 `ImportError: libGL.so.1`（退出码 1，已实测复现）。

修复已固化，两条路径都不需要手动卸装：

- **有 uv**（`prepare.sh` 主路径）：`backend/pyproject.toml` 的 `[tool.uv] exclude-dependencies = ["opencv-python"]` 把它从解析中排除，规则会记录在锁文件中，后续 `uv sync --locked --extra cloud` 继续排除 GUI 包；需要支持该配置的 uv（本地验证版本 0.12.9）。Linux 沙箱没有 uv，云端只验证了下述 pip 路径。
- **无 uv**（`prepare.sh` 自动 fallback，venv 内 pip，非全局）：先装 `opencv-python-headless`，再 `--no-deps` 装 `rapidocr-onnxruntime`，最后显式补上它的真实依赖 `onnxruntime numpy Pillow pyclipper PyYAML Shapely six tqdm`。该序列已在干净 venv 实测：`import cv2`、`import rapidocr_onnxruntime`、`RapidOCR` 实例化与识别（conf 0.98）全部通过。

回归保障：`backend/tests/test_cloud_deps.py` 离线锁定这些声明（主依赖保持 headless、cloud 组不含 opencv-python、uv exclusion 存在、prepare.sh 安装顺序正确）。

主模型配置项：`LLM_PROVIDER=deepseek`（本项目通用 OpenAI 兼容客户端名称）、`LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。密钥在云端单独配置，不从本机代码包迁移；切勿写进前端或提交到仓库。先确认服务支持 `image_url` 与工具调用；仅文字模型不能承担视频画面问答。

`start.sh` 的配置从进程环境读取；后端也能读取 `backend/.env` 中的模型配置。ASR/OCR 的后端选择优先由启动进程设置。无主模型密钥时 `/api/health` 仍返回 `ok=true`、`model=null`，只代表 Web/API 已启动。

## 验证清单

1. `ffmpeg` / `ffprobe` 可用，能够实际编码和解码短测试视频。
2. 页面、静态资源与 `/api/health` 可访问，未知 `/api/*` 返回 404。
3. 使用合成测试视频验证上传、抽帧、SSE 进度、OCR、会话持久化。
4. 使用公开或已授权的带语音素材验证 ASR 时间戳和耗时。无语音合成视频只能验证静音处理，不能证明转写准确。
5. 接入赛规允许的主模型后，验证图片 + 转写输入、工具调用、回答时间戳及流式输出。
6. 验证平台入口的登录控制与评审访问方式，再安排分享。

本轮本地验证：29 项相关测试通过，前端 production build 通过，单端口入口的页面、API、资源及 API 404 检查通过。

## 本轮云端已验证的结果

- 平台卡片名称：GongJing 视频理解工作台，bwrap 运行时，17080 端口。启动脚本模板位于 `/root/template/gongjing/start.sh`，额外读写挂载 `/root/workspace/gongjing`。
- 已实际通过平台 WebUI 按钮，经华为登录入口打开前端，并完成合成视频上传。
- 9 秒、83 KiB 的合成视频：48/48 帧成功，OCR 读出 `GONGJING TEST 123`，会话保存成功。
- 用户明确授权后，仅迁移 DeepSeek 模型配置到云端 `backend/.env`（0600 权限），未迁移账号 Cookie。临时传输文件已移出上传目录，本机临时凭证文件已删除。
- 实际图片问答成功：界面显示约 2.8 秒、11,431 输入 token、335 输出 token。模型正确识别圆形和文字，对实际水平右移误述为“右上”，因此该测试只证明调用链可用，不能视为动作方向准确性验收通过。
- 初次 ASR 因 Hugging Face 下载不可达报 `LocalEntryNotFoundError`；已从 ModelScope 下载本地模型并更新平台启动脚本。重启后的合成素材测试中 ASR 返回 `empty`，与测试音无口播相符。尚未用真实口播验证中文转写准确率和长视频速度。
- 重启后执行 `smoke.py`，任务 `aa3145d5168d`：页面、健康接口、未知 API 的 404、上传、48/48 帧、JPEG 数据、OCR、SSE 事件及会话列表检查全部通过。OCR 字幕覆盖 0–9 秒，内容为 `GONGJING TEST 123`。云端日志：`/root/workspace/gongjing-smoke-result.log`。

ModelScope 来源：[faster-whisper-small](https://modelscope.cn/models/pengzhendong/faster-whisper-small)。在此部署中仅使用转换后的权重及分词文件。
