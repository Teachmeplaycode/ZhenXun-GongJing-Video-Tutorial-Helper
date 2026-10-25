# README 界面截图

本目录包含两批真实界面素材：2026-10-25 本机截图，以及从宣传片工程中 2026-10-22 线上录屏提取的静帧。

## 当前本机界面

以下三张截图来自本机前端（`http://localhost:5173`）和真实后端，未使用 mock API 或合成界面。

| 文件 | 内容 | 复现入口 |
| --- | --- | --- |
| `home.jpg` | 教程导入首页 | 打开首页，等待模型与字体加载完成 |
| `workbench.jpg` | 对话、章节与时间轴 | 从历史打开教程会话，展开工作台，选择章节 |
| `node-canvas.jpg` | Blender 节点画布 | 在「抄作业」结果中点击「打开节点画布」 |

工作台与画布取自本机已有的《【Blender教程】用几何节点还原众生行记PV特效》会话。分析文字与节点图属于模型生成的实际结果，可能存在错误和待确认项；仅用于展示界面和交互能力。截图不包含账号凭证。

更新时运行当前前后端，使用已有的教程会话进入相同页面，等待内容加载完成后重新截图并替换同名文件。保留产品原始界面，不修改页面文字伪装分析结果；不要截入账号、Cookie 或密钥。若更换示例教程，同步更新此处与根 README 的来源说明。

## 宣传片工程实机录屏

来源：相邻工作目录 `MyTargetProject-visitors/video/zhenxun-promo/public/rec/`。`feat/promo-video` 分支的 `record/SHOTS.md` 说明录屏来自 `linyi.work/ZhenXun`，使用「帧寻演示」账号。录屏文件不在 Git 中，因此本次将精选静帧纳入当前仓库。文件名中的数字是源录屏秒数。

| 文件 | 源录屏 | 提取时间 |
| --- | --- | --- |
| `ask-29.jpg` | `ask.mp4` | 29 秒 |
| `evidence-28.jpg` | `evidence.mp4` | 28 秒 |
| `replay-27.jpg` | `replay.mp4` | 27 秒 |
| `screenshot-46.jpg` | `screenshot.mp4` | 46 秒 |
| `notes-30.jpg` | `notes.mp4` | 30 秒 |
| `phone-22.jpg` | `phone.mp4` | 22 秒 |
| `phone-notes.jpg` | `phone.mp4` | 37 秒 |
| `gif-35.jpg` | `gif.mp4` | 35 秒 |
| `import-20.jpg` | `import.mp4` | 20 秒 |

桌面静帧等比缩至宽 1600 像素，手机静帧缩至宽 585 像素，以 JPEG 保存；没有修改界面文字或拼接分析结果。录屏是较早版本，入口和文案以当前运行版本为准。视频成片与来源校验记录见 [媒体说明](../media/README.md)。
