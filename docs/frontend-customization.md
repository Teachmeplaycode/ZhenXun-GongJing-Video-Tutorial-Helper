# 前端自行调整指南

## 本地预览

在 `front` 目录运行 `npm run dev`，浏览器打开 http://127.0.0.1:5173。
修改源码后 Vite 会自动更新。正式构建使用 `npm run build`。

## 最常改的文件

| 调整内容 | 文件 | 修改位置 |
| --- | --- | --- |
| 项目名 GongJ!ng?、方言注释、产品副名 | `front/src/config/workspace.js` | `BRAND`（字标结构在 `front/src/components/Wordmark.jsx`） |
| 首页字标、副标题字号 | `front/src/styles/workspace.css` | `.magazine-hero__brand` / `.magazine-hero__title` / `.wordmark*` |
| 首页副标题、说明文字 | `front/src/config/workspace.js` | `WORKSPACE_CONTENT.title` / `description` |
| 可选分析任务中的快捷预设及填入内容 | `front/src/config/workspace.js` | `WORKSPACE_CONTENT.capabilities` |
| 对话页任务卡和实际问题 | `front/src/config/workspace.js` | `WORKSPACE_CONTENT.suggestions` |
| 首页标题大小、栏宽、上传区位置、卡片间距 | `front/src/styles/workspace.css` | `.magazine-hero` / `.magazine-hero__title` / `.import-slide` / `.import-entry` |
| 页面颜色、字体和整体字号 | `front/src/styles/tokens.css` | `--bg-*` / `--text-*` / `--accent-*` / `--font-*` |
| 上传区的控件和文字 | `front/src/stages/ImportPanel.jsx` | `.import-control` / `.import-options` |
| 模型的大小和水平位置 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.frame` / `sideOffset` |
| 首页模型的偶发故障失真：开关、间隔、节奏 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.glitch` |
| 故障失真的每帧强度和闪断顺序 | `front/src/lib/useModelGlitch.js` | `LOOKS` / `BURSTS` |
| 故障失真和玻璃折射的着色器 | `front/src/lib/postPass.js` | `fragmentShader`（`lens` 折射强度、`uBevel` 倒角宽度、`uBlur` 模糊） |
| 上传玻片外观（染色、细线、角标、字号） | `front/src/styles/workspace.css` | `.import-slide` / `.import-slide__label` / `.import-control__*` |
| 点击开始解析后的展开过渡、上传结束的上卷过渡 | `front/src/App.jsx` | `idle_to_uploading` 的 `useLayoutEffect` / `exitMask` |
| 首页点缀线条、四角星、点阵（位置、数量、闪烁） | `front/src/components/HeroOrnaments.jsx`、`front/src/styles/workspace.css` | `.ornament-*` |
| 无穷环的长宽和薄片粗壮程度 | `front/src/lib/sculptureMath.js` | `LOBE_X` / `LOBE_Y` / `CROSS_Z` / `SHEET` |
| 散开范围、单片大小 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.scatter` |
| 散片组成的方言文字、字高、单片大小及颜色 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.scatterText` |
| 形状顺序和循环节奏 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.morph` |
| 莫比乌斯环的磁流体呼吸、波峰、扭动强度 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.mobiusMotion` |
| 三叶结、双扭波环的呼吸幅度、扭动速度 | `front/src/config/workspace.js` | `SCULPTURE_SETTINGS.ribbonMotion` |
| 莫比乌斯环、三叶结、双扭波环的几何结构 | `front/src/lib/sculptureShapes.js` | `mobiusPose` / `ribbonPoint` / `buildRibbonPoses` |
| 等高线地图覆盖范围、密度、速度 | `front/src/config/workspace.js` | `CONTOUR_SETTINGS` |
| 等高线地形本身 | `front/src/components/ContourLoader.jsx` | `buildField` / `rawHeight` |
| 上传覆盖层文字和进度位置 | `front/src/stages/UploadMask.jsx`、`front/src/styles/workspace.css` | `.upload-mask__header` / `.upload-mask__status` |
| 时间轴薄片高度、厚度、悬停角度 | `front/src/components/TimelineSculpture.jsx` | `CARD_HEIGHT` / `CARD_DEPTH` / `REST_ANGLE` / `HOVER_ANGLE` |

## 首页排版

首页保留大标题和原有动态薄片模型。上传区是一条合并操作栏：左侧选择文件，右侧开始解析；分析任务默认折叠，展开后可填写或选择预设。移除了档案编号、重复流程说明和底部任务卡。模型几何及散开重组动画保持原样。

`workspace.css` 控制这次新增的排版；`app.css` 保留工作台基础布局；`tokens.css` 统一管理主题。
移动端样式在 `workspace.css` 的 `@media (max-width: 860px)` 中。首页在手机上使用纵向滚动布局。

首页模型会偶发一次约 0.3 秒的信号故障：几帧硬切的横向切片错位、RGB 色散、轻微波形扭曲和扫描线，中间夹着干净帧形成闪断节奏，然后恢复。效果只作用在模型像素上，不反色，背景、标题和上传控件都不受影响。`SCULPTURE_SETTINGS.glitch.enabled` 可关闭效果，`firstDelay` 为首次延迟，`minInterval` / `maxInterval` 为每次恢复后的随机等待范围（秒），`tempo` 整体放慢（>1）或加快（<1）每次故障。每帧的扭曲 `warp`、切片比例 `slice`、错位幅度 `tear`、色散像素 `rgb`、数据条 `blocks`、扫描线 `scan` 在 `useModelGlitch.js` 的 `LOOKS` 中调整，帧序列和每帧毫秒数在 `BURSTS` 中调整。只有首页播放；进入上传、解析、对话，隐藏页面或开启减少动态效果时停止；低性能设备不播放。

## 视频链接解析

首页玻片可以直接粘贴视频链接或分享文本，也可以选择或拖入本地文件；识别到链接后，按钮变为「解析链接」。链接由后端解析并在远程抽帧，需要先启动后端（见 `backend/README.md`），开发时 Vite 会把 `/api` 代理到 `127.0.0.1:8000`。

- 解析失败（不支持的平台、视频不存在、需要权限等）会回到首页，并在玻片下方显示原因。
- 抽满 16 帧后，解析页会出现「先进入对话 · 其余画面后台继续」。
- 帧不全也会正常完成：解析页和时间轴显示缺失数量和时间段；时间轴上的缺失帧为橙色斜纹，悬停显示原因，不能选中；可以点击「补抓」。对话会说明哪些时段没有画面。
- 前端代码：接口在 `front/src/api/client.js`（`createLinkJob` / `streamLinkJob` / `retryLinkJob`），流程在 `front/src/App.jsx`（`runLink` / `followLinkJob` / `retryMissing`）；提前进入对话所需的帧数为 `EARLY_CHAT_FRAMES`。

## 项目名

项目名 `GongJ!ng?` 是家乡方言「真的吗？」。网址、仓库和文件名使用不带标点的 `gongjing`（`BRAND.slug`）。
首页最大的字是字标，字体为 Unbounded 700（`tokens.css` 的 `--font-display`，仅字标使用），`!` 和 `?` 使用黄绿色 `--accent-active`，顶栏小字号用更深的 `--accent-active-dim` 以保证可读；「画面之内。答案之间。」降为副标题。
字标的 `?` 在模型故障失真的那几帧会闪成 `!`；解析完成后，顶栏的项目名会变为 `GongJ!ng!`，意思是「真的！」。

## 上传玻片与过渡

首页上传框是一块「玻片」：模型左环从它后面经过时，会被轻微放大、在倒角处弯折，边缘带一点色散和高光。折射在模型的 WebGL 后期处理里完成（`postPass.js`），各浏览器效果一致；DOM 只负责半透明染色、细线和四角刻度。低性能设备不做折射，只保留染色。模型停放位置 `SCULPTURE_SETTINGS.sideOffset` 决定有多少模型经过玻片。

点击「开始解析」或「使用示例素材」后，玻片打开成一个窗口并扩展到全屏，窗口里逐渐显出等高线地形；左上角标签从 `01 / IMPORT` 接续为 `02 / UPLOAD`。同时标题依次上移淡出，模型后退淡出。上传结束时，上传屏像幕布一样向上卷起，露出下面的解析场景。缓动统一使用 `EASE.expand`（`lib/motion.js`）。开启减少动态效果时直接切换。

## 返回上一级

上传屏左上角、解析页和对话页顶部均提供「返回上一级」。上传或解析时返回导入页会中断当前任务，并保留已选文件和填写的分析任务；对话页返回解析完成页，保留关键帧、选帧、对话和输入草稿，同时停止尚未完成的回答。再次进入对话可继续使用。

按钮外观在 `front/src/components/BackButton.jsx` 和 `workspace.css` 的 `.btn--back` 中调整；返回逻辑在 `front/src/App.jsx` 的 `goBack` / `reset` 中调整。

## 第三场景的形状循环

第三场景指示例素材上传结束后的解析模型界面，代码状态为 `analyzing` / `ready`。
导航栏的三步名称仍是「导入视频 / 解析时间轴 / 对话分析」。

环形模型依次循环：无穷环 → 莫比乌斯环 → 三叶结 → 双扭波环。每次切换先散成一句问候，再重组成下一种环形模型。
问候独立轮换：「你好」→「率厚哇」→「歪哈」→「平潭」→「诶嗨咩」。文字由同一批三维薄片排列，不是叠加文字图片。

```js
morph: {
  shapes: ['infinity', 'mobius', 'trefoil', 'waveRing'],
  scatterDuration: 1.8, // 散开耗时，秒
  scatterHold: 3,      // 文字排列状态停留，秒
  assembleDuration: 2, // 重新组成耗时，秒
  shapeHold: 5,        // 完整形状展示，秒
}
```

每次切换的两个环形模型共享同一句文字的位置，散开和组装之间不会跳位。下一次切换才轮换到下一句。
`scatterText.words` 修改文字及顺序；`padding` / `mobilePadding` 控制桌面和手机上的四周留白（像素）；`footerSpace` 为底部操作按钮预留空间；`plateSize` 控制笔画网格的覆盖比例；`depth` / `drift` 控制细微错落和漂浮；`inkMix` 控制字形的灰度。当前薄片恢复平面字形，相机按每句话实际笔画的宽高自动缩放，尽量铺满可用画面，同时保留 padding 和原始文字比例。`height` 是生成字形的基础世界尺寸，屏幕尺寸由自动适配决定。文字展示的三秒内暂时隐藏进度卡和帧条，避免遮字；解析完成后「进入对话分析」始终可见、可点击，顶部返回按钮保留。字体采样和自动适配在 `front/src/lib/sculptureWords.js`，启动时只生成一次。默认使用本机中文黑体字体。
原来的 `scatter.width` / `height` / `scale` 保留为无法生成字形时的随机散片回退；WebGL 场景优先使用文字排列。

三叶结和双扭波环都沿闭合曲线排列薄片，保持带状、镂空、扭转的风格。`ribbonMotion` 控制两者的呼吸周期、环体起伏和带宽变化。`ribbonPoint` 控制环形曲线，`buildRibbonPoses` 中的带宽倍率控制各形状的粗壮程度。

莫比乌斯环展示时会缓慢舒展、收拢，并有沿环流动的波峰、横向起伏和薄片扭动。`mobiusMotion.period` 控制呼吸周期，`radiusBreath` / `widthBreath` 控制环半径和带宽的呼吸幅度，`radialWave` / `ridge` 控制波浪和磁流体状隆起，`lift` 控制空间起伏，`twist` 控制薄片扭动，`flowSpeed` 控制波峰流速。实际播放速度还会乘以解析场景的速度倍率。散开重组仍使用相同目标位置；减少动态效果时不播放这些变形。
增大 `frame.w` / `frame.h` 会缩小画面中的模型。`SHEET.height` 越大，带状结构越宽。
系统开启「减少动态效果」时，模型保持静止无穷环；没有 WebGL 时使用静态 SVG 回退。

## 第二场景的全屏地图

上传层通过 React Portal 挂到页面根部，`position: fixed; inset: 0` 覆盖整个浏览器视口。
`CONTOUR_SETTINGS.width` 和 `height` 决定地形投影范围。当前默认值会将地形边缘裁到屏幕外，形成满屏等高线。
`levels` 控制层数，`cycle` 控制从底层到顶层的时间，`relief` 控制立体起伏。较低性能设备自动减少层数。

## React Bits

已实际接入 [React Bits](https://reactbits.dev/) 的 `SpotlightCard`、`AnimatedContent`、`CountUp`：

- `front/src/components/react-bits/`：上游组件源码、来源版本和许可。
- `front/src/stages/AnalyzeHud.jsx`：精简解析进度和关键帧计数动画。
- `front/src/stages/ChatStage.jsx`：对话任务卡。

首页上传框已改为自绘的玻片（见「上传玻片与过渡」），不再使用 `SpotlightCard`。

组件的颜色、光斑强度、动画距离和持续时间可以在使用它们的位置通过 props 调整。
例如 `SpotlightCard` 的 `spotlightColor`、`intensity`、`spotlightSize`；`AnimatedContent` 的 `distance`、`duration`。
这是 React 项目，没有引入 Vue 运行时。
