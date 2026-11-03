# Windows 和本机浏览器版

保留网页服务部署方式，新增本机启动入口，默认仅监听 127.0.0.1

## 准备环境

- Python 3.12 或更高，Windows 安装时勾选 Add Python to PATH（后端虚拟环境固定使用 3.12）
- Node.js 20 或更高的 LTS 版（含 npm）
- uv：`pip install uv`
- ffmpeg / ffprobe：安装后将 bin 目录加入 PATH

Windows 双击仓库根目录的 `start.cmd`，首次安装依赖需要联网，完成后自动打开本机浏览器
macOS / Linux 使用 `python3 start.py`，均复用同一套首页和设置
如果 Windows 安全软件询问网络访问，只需要本机回环访问

## 设置模型和平台账号

首页右上角「设置」分为模型与 API、平台账号、本地运行

- 云端模型：选择 DeepSeek / OpenAI 兼容，填写服务地址、模型名、API Key
- 本机模型：选择 Ollama，安装支持图片输入的模型，再填写其模型名和地址
- 服务地址、模型名留空时使用当前模型服务的默认值，服务商需支持项目使用的图片输入和工具调用能力
- B 站、视频号、小红书等原有扫码和 Cookie 功能集中在「平台账号」中
- 密钥不回传到页面，不放入 localStorage，关闭设置会丢弃未保存密钥/Cookie 并取消扫码
- 清除本地密钥只删除设置面板的覆盖项，环境变量或 .env 中的旧密钥仍可能生效

配置优先级为系统环境变量 > backend/.env.local > backend/.env.accounts > backend/.env
面板会说明来源及环境变量覆盖情况，公开演示站点不会暴露或允许改动服务器模型配置
`.env.local` 和 `.env.accounts` 只保存在本机后端目录，不要提交或分享这两个文件

Windows / Linux 安装包含 faster-whisper 和 RapidOCR，Mac 使用对应平台后端
首次语音转写可能下载 Whisper 权重，模型大小和内存取决于所选模型
扫码需要 Playwright 浏览器组件，启动器会尝试安装，失败时可再次启动补装
未配置模型密钥时仍能进入首页配置，但无法进行模型问答

## 启动和停止

```text
python start.py --check         只检查工具和端口
python start.py --no-browser    启动但不自动开浏览器
python start.py --skip-install  已安装依赖时跳过联网安装
```

Windows 同样可以在终端执行 `start.cmd --check`
正常停止使用启动窗口中的 Ctrl+C，启动器只停止自己创建的前后端进程
端口已被占用时会报错退出，不会关闭已有程序，可通过 API_PORT 和 WEB_PORT 环境变量换端口
运行数据默认在 backend/data，可用 GONGJING_DATA_DIR 指向独立目录

当前为源码一键启动版，需要预装上述工具，还不是内含 Python/Node 的免安装 exe

## 维护验收

CI 的 Windows job 使用带中文和空格的真实工作目录，检查 start.cmd、锁定依赖、ASR/OCR 导入、设置接口、本地启动、视频抽帧及退出清理
`scripts/local_launcher_smoke.py` 不调用付费模型、不下载识别模型，临时禁用 OCR 并使用无音轨视频，配置文件原值在 finally 中恢复
真实语音识别效果和各平台扫码需要独立业务验收
