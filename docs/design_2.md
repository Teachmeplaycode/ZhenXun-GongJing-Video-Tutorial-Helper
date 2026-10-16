
```yaml
agent_instructions:
  scope: "本项目所有前端界面组件、动效、交互"
  rules:
    - "所有颜色必须使用 Section 1 定义的语义 Token，禁止硬编码 hex"
    - "所有间距必须使用 Section 3 定义的间距刻度"
    - "所有动效必须包含 duration + easing，参考 Section 8"
    - "雕塑必须使用 InstancedMesh，参数见 Section 7"
    - "流式事件必须按 Section 9 的事件类型映射到组件"
    - "工具调用按发生顺序折叠为步骤组（StepGroup），与回答文字交错排列；主消息流只展开回答文字，步骤详情点开才看"
    - "若需求未在本文件定义，生成前先提问，禁止自行发挥"
  priority: "本文件 > 现有代码 > 通用最佳实践"
  output_language: "界面文案中文，代码注释英文"
```

---

## 1. Visual Identity（视觉 Token）

### 1.1 设计意图（人类阅读）

整体采用**精密科研工具**气质：暖灰白底、近黑文字、细线网格、简洁技术标签、局部黑色信息块。荧光黄绿表示活动或成功，橙色表示需要处理的问题。所有装饰性细节保持克制。

视觉语言源自 Bilibili 视频 `BV1pEa66NEGA` 中 A 方案的背景 3D 薄片雕塑：参数化结构、连续扭转、米白哑光材质、柔光层次。该雕塑应用于视频理解工作台的各个阶段，隐喻视频帧沿时间轴排列。

### 1.2 颜色 Token（Agent 执行）

```yaml
colors:
  background:
    canvas: "#F5F3EF"        # 暖灰白主背景
    surface: "#FFFFFF"       # 组件表面
    surface_alt: "#FAF8F5"   # 次级表面
    inverse: "#1A1A1A"       # 黑色信息块
    grid_line: "#EDEAE5"     # 网格线

  text:
    primary: "#1A1A1A"       # 近黑主文字
    secondary: "#6B6B6B"     # 次要文字
    tertiary: "#9B9B9B"      # 元数据
    inverse: "#FFFFFF"       # 黑色块上的文字

  accent:
    active: "#C8F04A"        # 荧光黄绿：活动/成功
    active_dim: "#A8CC3A"    # 活动态按压缩放
    processing: "#F5A623"    # 橙色：需要处理的问题
    error: "#E5484D"         # 错误
    success: "#5A9E3A"       # 完成

  border:
    default: "#E0DDD8"       # 常规边框
    strong: "#C8C4BD"        # 强调边框
    focus: "#1A1A1A"         # 聚焦边框

  sculpture:
    light_material: "#F0EDE8"  # 米白哑光（空闲态）
    dark_material: "#2A2A2A"   # 深色（导入后）
    shadow: "#D8D4CE"          # 柔和阴影
```

### 1.3 深色主题（2026-10-16 新增）

同一套暖灰色调的夜间版本：表面和文字互换，强调色不变。默认跟随系统，右上角按钮在"跟随系统 / 浅色 / 深色"之间切换（存在本机浏览器里）。实现见 `front/src/styles/tokens.css` 的 `:root[data-theme='dark']`，主题在首帧之前由 `index.html` 设置，不会闪。

```yaml
dark:
  background: { canvas: "#141413", surface: "#1C1C1A", surface_alt: "#232321", inverse: "#EDEAE4", grid: "#252523" }
  text: { primary: "#EDEAE4", secondary: "#A8A49D", tertiary: "#7A766F", inverse: "#141413" }
  border: { default: "#34332F", strong: "#4C4A45", focus: "#EDEAE4" }
  accent: { active: "#C8F04A", processing: "#F5A623", error: "#F2555A", success: "#7CC35A" }
  sculpture: { light: "#8F8A82", shadow: "#050505" }   # 雕塑：黑底上的暗灰薄片，不抢文字
  rules:
    - "荧光黄绿上的文字永远用 --text-on-accent（#1A1A1A），两种主题都一样"
    - "深色按钮（--bg-inverse）在深色主题里变成浅色按钮，悬停色用 --bg-inverse-hover"
    - "二维码保持白底，深浅主题都一样（扫码需要）"
```

---

## 2. Typography（字体尺度）

### 2.1 设计意图

中文使用清晰黑体；标题使用无衬线字体；时间戳、运行编号和参数使用等宽字体。正文不小于 14px，次要元数据不小于 12px。标题、正文、元数据具有明确尺度差异。

### 2.2 字体定义（Agent 执行）

```yaml
typography:
  font_families:
    sans: "Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    mono: "'JetBrains Mono', 'SF Mono', 'Roboto Mono', Menlo, monospace"

  scale:
    display:
      size: 32px
      weight: 600
      line_height: 1.2
      letter_spacing: -0.02em
      family: sans
    h1:
      size: 24px
      weight: 600
      line_height: 1.3
      family: sans
    h2:
      size: 18px
      weight: 600
      line_height: 1.4
      family: sans
    body:
      size: 15px
      weight: 400
      line_height: 1.6
      family: sans
    body_sm:
      size: 14px
      weight: 400
      line_height: 1.5
      family: sans
    caption:
      size: 12px
      weight: 400
      line_height: 1.4
      family: sans
    mono:
      size: 13px
      weight: 400
      line_height: 1.5
      family: mono
    mono_sm:
      size: 12px
      weight: 400
      line_height: 1.4
      family: mono

  usage_rules:
    - "时间戳、运行编号、参数值 → mono"
    - "标题 → sans, h1 或 display"
    - "正文不小于 14px，元数据不小于 12px"
    - "标题与正文的尺度比不低于 1.5"
    - "等宽字体不用于长段正文"
```

---

## 3. Spacing & Grid（间距与网格）

```yaml
spacing:
  scale: [0, 2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96]
  unit: px

  semantic:
    inline_xs: 4px
    inline_sm: 8px
    inline_md: 12px
    block_sm: 16px
    block_md: 24px
    block_lg: 32px
    section: 48px

  radius:
    none: 0
    xs: 2px
    sm: 4px
    md: 6px
    lg: 8px       # 上限，禁止超过
    pill: 999px   # 仅用于状态标签与小型开关/浮动按钮（输入栏开关、时间轴收起、回到底部）

  border:
    hairline: 1px solid var(--border-default)
    strong: 1px solid var(--border-strong)
    focus: 2px solid var(--border-focus)

  layout:
    page_max_width: 1440px
    page_padding: 24px
    wireframe_container_padding: 24px
    content_max_width: 960px
    chat_max_width: 1120px   # 对话区更宽：回答里有步骤组、列表和来源卡片（2026-10-15 调整）
```

---

## 4. Component Registry（组件清单）

| 组件名 | 用途 | 所在 Section |
|---|---|---|
| `WireframeContainer` | 页面主容器，细线框包围 | 5 |
| `SculptureCanvas` | Three.js 薄片雕塑画布 | 7 |
| `UploadMask` | 上传时的等高线遮罩 | 6, 7 |
| `ContourLoader` | 等高线地形绘制动画 | 6 |
| `ChatThread` | 对话主容器 | 10 |
| `MessageBubble` | 用户/AI 消息气泡 | 10 |
| `Avatar` | 圆角矩形头像 | 10 |
| `StepGroup` | 连续工具调用折叠成一行（基于 React Bits ThoughtLine 改造），运行时显示当前步骤 | 9 |
| `StepRow` / `StepDetail` | 步骤组里的一行，点开后显示该步的可视化细节 | 9 |
| `DiffViewer` | 文件改动 diff 展示（在 StepDetail 内） | 9 |
| `Composer` | 输入栏：自动增高、`/` 命令、联网/论文开关、选帧、发送/停止 | 10 |
| `Sources` | 回答引用的来源卡片 | 10 |
| `MessageFooter` | 回答底部的统计行与操作（复制、重新回答） | 10 |
| `BrowserViewport` | Computer Use 浏览器视口 | 11 |
| `TimelineSculpture` | 薄片时间轴 | 8 |
| `SheetPreview` | 薄片 hover 预览卡 | 8 |

---

## 5. Layout & Wireframe（布局与线框）

```yaml
wireframe_container:
  description: "页面主体使用一个大线框容器，内部留有小 padding"
  style:
    border: "1px solid #E0DDD8"
    background: "#F5F3EF"
    padding: 24px
    radius: 0
  children:
    - "SculptureCanvas 或 ChatThread 或 TimelineSculpture（按阶段切换）"
    - "阶段切换时通过遮罩刷新，不出现空白"

flow_stages:
  stage_0_idle:
    name: "空闲态"
    primary_view: SculptureCanvas
    overlay: "视频导入入口（按钮 + 拖拽区域）"
    sculpture_state: "light material, slow rotation"
  stage_1_uploading:
    name: "上传中"
    primary_view: ContourLoader
    overlay: "上传进度 + 关键帧抓取状态"
    mask: "遮罩盖住雕塑，等高线动画"
  stage_2_analyzing:
    name: "分析中"
    primary_view: SculptureCanvas (dark)
    overlay: "时间轴数据获取进度"
    sculpture_state: "dark material, fast rotation"
  stage_3_chat:
    name: "对话"
    primary_view: ChatThread
    below: "TimelineSculpture（可收起，见 Section 8 fold）"
    sculpture_state: "timeline distributed below wireframe"
```

---

## 6. ContourLoader（等高线加载动画）

```yaml
contour_loader:
  description: "参考 /Users/linyi/project/videoComprehensive 中的等高线模型"
  animation:
    type: "从最底部绘制整个地形"
    direction: "bottom to top"
    loop: true
    cycle_duration: "2.4s"
    easing: "power1.inOut"
    line_style: "1px stroke, #9B9B9B"
    fill: "无填充，仅等高线描边"
    height_map: "预生成的噪声高度图（Perlin / Simplex）"
  mask_behavior:
    enter:
      duration: 0.6s
      easing: "power2.inOut"
      from: "opacity 0"
      to: "opacity 1"
    exit:
      duration: 0.8s
      easing: "power2.inOut"
      delay: "0.2s"
  performance:
    canvas_size: "自适应容器，上限 1024x1024"
    reduce_on_low_end: "降低等高线密度 50%"
    pause_on_hidden: true
```

---

## 7. Three.js Sculpture Spec（雕塑规格）

### 7.1 几何参数

```yaml
sculpture:
  geometry:
    instance_count: 400              # 范围 300–500
    instance_count_low_end: 200      # 低端设备
    curve_type: "CatmullRomCurve3"
    curve_control_points: 24         # 预计算，形成环形带状
    curve_closed: true
    sheet:
      width: 0.8
      height: 4.0
      thickness: 0.02
      segments: 1
    material:
      type: "MeshStandardMaterial"
      roughness: 0.85
      metalness: 0.0
      side: "DoubleSide"
      flat_shading: false

  animation:
    twist:
      type: "沿曲线切线的连续旋转"
      speed: 0.15                    # rad/s
      axis: "local tangent"
    multi_axis_rotation:
      x: 0.05                        # rad/s
      y: 0.08
      z: 0.03
    breathing:
      type: "沿曲线法线展开与收拢"
      amplitude: 0.3
      period: "8s"
      easing: "sine.inOut"

  interaction:
    parallax:
      trigger: "mousemove"
      camera_offset_max: 0.02        # 世界单位
      damping: 0.95
      lerp_speed: 0.08

  performance:
    use_instanced_mesh: true
    frustum_culling: false
    pause_on_hidden: true
    respect_prefers_reduced_motion: true
    webgl_fallback: "static SVG contour rendering"
    max_dpr: 2

  state_transitions:
    idle_to_uploading:
      mask_enter:
        target: "sculpture"
        opacity: { from: 1, to: 0 }
        duration: 0.6
        easing: "power2.inOut"
      contour_enter:
        target: "ContourLoader"
        opacity: { from: 0, to: 1 }
        duration: 0.8
        delay: 0.6
    uploading_to_analyzing:
      mask_exit:
        target: "ContourLoader"
        opacity: { from: 1, to: 0 }
        duration: 0.8
        easing: "power2.inOut"
      sculpture_enter:
        target: "sculpture"
        opacity: { from: 0, to: 1 }
        duration: 1.0
        delay: 0.4
      darken:
        property: "material.color"
        from: "#F0EDE8"
        to: "#2A2A2A"
        duration: 1.2
        easing: "power2.inOut"
      rotation_speed:
        multiplier: { from: 1.0, to: 3.0 }
        duration: 1.2
        easing: "power2.inOut"
    analyzing_to_chat:
      sculpture_distribute:
        description: "薄片按时间顺序展开为时间轴"
        target: "TimelineSculpture"
        duration: 1.4
        easing: "power3.inOut"
```

### 7.2 Agent 约束

```yaml
agent_constraints:
  - "禁止为每个薄片创建独立 Mesh，必须使用 InstancedMesh"
  - "禁止使用 MeshBasicMaterial 或 flat 材质"
  - "禁止超过 500 个实例，除非有性能测试支持"
  - "页面不可见时必须 pause（requestAnimationFrame 停止）"
  - "必须响应 prefers-reduced-motion：仅保留极慢旋转，禁用 breathing"
```

---

## 8. Timeline Sculpture（薄片时间轴）

```yaml
timeline_sculpture:
  description: "雕塑薄片按视频时间顺序排列为时间轴，位于线框容器下方"
  source: "sculpture 的 InstancedMesh 实例"
  layout:
    axis: "horizontal"
    sheet_spacing: "均匀，对应关键帧时间间隔"
    curve_preserved: true

  interaction:
    hover_sheet:
      properties:
        y_offset: -8px
        scale: 1.05
        border_color: "#C8F04A"
      duration: 0.2s
      easing: "power2.out"
    hover_neighbors:
      radius: 3
      y_offset: -3px
      duration: 0.25s
      easing: "power2.out"
      curve_preservation: "CatmullRom 插值计算邻片偏移"
    selection:
      trigger: "click"
      visual:
        border: "2px solid #C8F04A"
        marker: "右上角小圆点"
      max_select: "无上限，超过 5 片时显示 '已选 N 帧' 摘要"

  preview:
    trigger: "hover 持续 400ms"
    content:
      - "关键帧缩略图"
      - "时间戳（mono）"
      - "帧编号（mono）"
    position: "薄片上方，带小箭头"
    style:
      background: "#FFFFFF"
      border: "1px solid #E0DDD8"
      padding: 12px
      radius: 4px

  default_scope:
    rule: "用户未划分范围时，默认理解为整个视频"
    indicator: "在输入栏工具条右侧显示 '范围：整段视频'"

  fold:
    description: "时间轴可以收起，只留标题行，把高度让给对话区"
    control: "标题行右侧的 收起/展开 按钮（chevron 旋转）"
    animation: { property: "grid-template-rows 1fr → 0fr", duration: 0.4s, easing: "power2.inOut" }
    persistence: "localStorage（timeline.open），刷新后保持"
    auto_open:
      - "输入栏点「选帧」：展开，并让标题行以 #C8F04A 闪一下（0.9s，power2.out，延迟 0.25s）"
      - "点击回答里的时间点：展开并定位"

  seek:
    trigger: "点击回答或步骤详情里的时间点"
    effect: "最接近的薄片抬起 + #C8F04A 描边 + 立即显示预览，2.5s 后复原"
    note: "时间点与最近的帧相差 ≥1s 时，预览里显示 '≈ mm:ss'"
```

---

## 9. Streaming & Agent Trace Protocol（流式与追踪协议）

### 9.1 设计意图

参照 Claude / Codex：一条回答是**按发生顺序排列的片段**——连续的工具调用折叠成一个步骤组，回答文字写在它后面；若之后又调用工具，就再起一个步骤组。运行时步骤组展开并实时显示当前步骤，结束后收起成一行摘要。主消息流里能直接读到的只有回答文字和引用来源；每一步的参数、结果和可视化细节都要点开才看。

（2026-10-15 起取代原先的"所有工具卡片堆在回答上方 + 黑色完成信息块"。）

### 9.2 事件与片段

```yaml
streaming:
  transport: "SSE (Server-Sent Events)"
  scroll_behavior: "sticky bottom；用户上滚时暂停跟随，并出现「回到底部 / 回到最新」按钮"

  event_fields:
    t: "从提问起算的秒数，后端给每个事件加上；步骤组用它计算用时，历史回放也能显示"
    data: "tool_call.output 上的结构化结果，供可视化使用（不发给模型）"

  message_parts:
    steps: "{ kind: 'steps', calls: [...], from, to }   连续的工具调用"
    text:  "{ kind: 'text', text }                       回答文字"
    rules:
      - "tool_call.started：最后一个片段是未结束的步骤组就并入，否则新开一个步骤组"
      - "assistant.message.delta：最后一个片段是文字就追加，否则结束当前步骤组（记下 to）并新开文字片段"
      - "run.completed / run.error：结束所有步骤组；仍在运行的步骤标为 stopped（用户停止）或 error"

  event_types:
    progress.update:
      render: "作为步骤组运行中的标签（没有正在运行的步骤时显示 '{step}…'）"
    tool_call.started / input / output / completed:
      component: "StepGroup > StepRow"
      render: "一行：状态标记 · 动作 · 对象（mono）· 结果（mono，tertiary）· chevron"
    assistant.message.delta:
      component: "StreamingText"
      render: "Markdown 子集（段落、标题、多级列表、粗体、斜体、行内代码、链接）；时间点渲染为可点击的 ts-chip；最后一段文字末尾有光标 █"
    file.edit.diff:
      component: "StepDetail > DiffViewer"
    run.completed:
      component: "MessageFooter"
      render: "一行 mono_sm、tertiary：'N 步 · 用时 · 输入/输出 tokens'，右侧为复制、重新回答"
    run.error:
      render: "bubble__error 文字；用户停止显示 '已停止'"

  persistence:
    - "保存回答时，事件按顺序存下，连续的文字片段合并为一条，重新打开会话时可以按原顺序回放"
    - "旧格式（没有存文字片段）的回答：文字统一排在步骤之后"
```

### 9.3 步骤组（StepGroup）

```yaml
step_group:
  base: "React Bits ThoughtLine（MIT + Commons Clause），见 front/src/components/react-bits/SOURCE.md"
  local_changes: "项目图标替代 Hugeicons；steps 可传 React 节点；全宽；defaultOpen / onOpenChange"
  working:
    label: "当前步骤，如 '联网搜索「grapefruit statin…」…'"
    shimmer: { duration: 1.8s, linear, infinite }
    glyph: "10×10 方块，#C8F04A 填充 + 近黑内描边"
    timer: "mono_sm，实时计时"
    open: true
  settled:
    label: "执行了 N 步（· M 步失败） + 用时"
    settle: { duration: 350ms, blur: 2px, easing: "cubic-bezier(0.23, 1, 0.32, 1)" }
    collapse_on_settle: true
  steps_list:
    style: "左侧 1px border-default 竖线，行间距 2px"
    hidden: "模型推理轮次（vision.*）不列为步骤，与 Claude / Codex 一致；token 用量放在 MessageFooter"

step_row:
  layout: "grid: 16px 标记 | 动作 | 对象（省略号）| 结果 | 12px chevron"
  status_marks: { running: "脉冲圆点", done: "✓ success", error: "▲ processing", stopped: "■ tertiary" }
  expand: { duration: 0.24s, easing: "power2.out" }
  collapse: { duration: 0.18s, easing: "power2.in" }
  verbs:
    frames.select: "选取画面"
    transcript.read: "读取语音转写"
    decision.research_intent: "判断是否需要查资料"
    transcript.search: "搜索转写"
    transcript.read_range: "读取转写"
    frames.view: "细看画面"
    web.search: "联网搜索"
    web.fetch: "阅读网页"
    papers.search: "检索论文"
```

### 9.4 步骤详情可视化（StepDetail）

```yaml
step_detail:
  entrance: "首次展开时播放一次（gsap.context，reduced-motion 下直接显示终态）"
  views:
    decision.research_intent:
      component: "Meter"
      render: "6px 概率条，fill 从 0 到 p（0.6s power2.out），0.5 处 1px #F5A623 阈值线，右侧 '需要查资料 0.52'"
    web.search:
      component: "Results"
      render: "每条：标题 + host（mono）· 三段概率条（可靠 success / 存疑 processing / 无关 border-strong）· 判定章"
      motion:
        rows: { from: "opacity 0, y 6", duration: 0.24s, easing: "power2.out", stagger: 0.05s }
        bars: { from: "scaleX 0", duration: 0.6s, easing: "power2.out" }
        stamps: { from: "opacity 0, scale 1.4", duration: 0.2s, easing: "back.out(1.4)", stagger: 0.05s }
        dropped: "无关结果画删除线（scaleX 0→1）并淡到 0.45，0.3s power2.inOut"
    web.fetch:
      component: "PageScan"
      render: "标题、host、读取的字数范围；每 2000 字一段扫描块依次亮起（stagger 0.18s），安全为 success、命中为 processing；章：'安全 0.02' / '已拦截 0.97'"
    papers.search:
      component: "Papers"
      render: "标题、作者 · 年份 · 期刊（mono_sm）、右侧被引次数"
    transcript.search:
      component: "Hits"
      render: "命中句子，前置可点击的时间点"
    frames.view:
      render: "截取的时间点（可点击）；原视频不可读时注明使用了已有关键帧"
    fallback:
      render: "参数表 + stdout / stderr（mono，max-height 240px 内部滚动）+ diff"
  verdict_stamp:
    style: "1px currentColor 边框，mono_sm，radius xs；可靠 success / 存疑 processing / 无关 tertiary"
```

---

## 10. Chat Interface（对话界面）

```yaml
chat:
  layout:
    container: "WireframeContainer 内，padding 24px"
    message_gap: 16px
    max_width: 1120px   # chat_max_width
    align: center

  avatars:
    user:
      shape: "rounded_rect"
      radius: 6px
      size: 32x32
      color: "#1A1A1A"
    assistant:
      shape: "rounded_rect"
      radius: 6px
      size: 32x32
      color: "#C8F04A"
    note: "头像图片待补，暂用纯色块"

  message_bubble:
    user:
      align: right
      background: "#1A1A1A"
      color: "#FFFFFF"
      radius: "6px 6px 0 6px"
      max_width: "72%"
      padding: "10px 14px"
      options_note: "这次关掉了联网或论文时，气泡下方注明 '不联网 · 不查论文'"
    assistant:
      align: left
      background: "#FFFFFF"
      border: "1px solid #E0DDD8"
      color: "#1A1A1A"
      radius: "6px 6px 6px 0"
      max_width: "100%"   # 原 80%，2026-10-15 改为占满对话区
      padding: "12px 16px"
      content: "片段序列（Section 9.2）→ 来源卡片 → 统计与操作"

  sources:
    rule: "回答里出现的链接，与本次检索/阅读/论文结果匹配出标题；匹配不到的显示 host"
    layout: "顶部 1px 分隔线 + '来源 · N'；卡片 auto-fill minmax(220px, 1fr)"
    card: "序号方块（inverse）· 标题 · '网页/论文/链接 · host'；surface_alt 背景，radius sm"
    motion: { from: "opacity 0, y 4", duration: 0.4s, easing: "power2.out", stagger: 60ms }
    links_in_text: "Markdown 里的网址渲染为链接，显示 host + 截短的路径"

  message_actions:
    copy: "复制回答文字（成功后图标变 ✓ 1.5s）"
    regenerate: "用同一问题、同样的附件和开关再问一次；有回答在运行时不可用"

  jump_to_latest:
    trigger: "用户上滚离开底部"
    style: "胶囊按钮，surface 背景，hairline 边框，位于输入栏上方居中"
    motion: { from: "opacity 0, y 8", duration: 0.2s, easing: "power2.out" }

  composer:
    reference: "React Bits PromptBar 的交互，精简实现（不含模型、思考深度选择）"
    box: "surface 背景，hairline 边框，radius 8px，focus 时 border-focus"
    input: "自动增高，44–200px；Enter 发送，Shift+Enter 换行，输入法组字时不发送"
    toolbar:
      - "选帧：展开时间轴并闪烁标题行，用于点选关键帧作为附件"
      - "联网 / 论文：开关，开启为 inverse 填充；随问题发送给后端（web / papers），决定这次可用的工具；记在 localStorage"
      - "命令：插入 / 打开命令菜单"
      - "右侧：范围提示（mono_sm，tertiary）+ 发送 / 停止"
    slash_menu:
      trigger: "输入框内容为 '/xxx'"
      items: ["/总结", "/时间线", "/核实", "/论文", "/细看"]
      keys: "↑↓ 选择，Enter / Tab 确认，Esc 关闭；确认后填入完整提问，/细看 选中时间范围便于修改"
      motion: { from: "opacity 0, y 6, scale 0.98", duration: 0.16s, easing: "power2.out" }
    attachments: "已选关键帧以 frame-chip 显示在输入框上方（≤5 张显示缩略图，否则 '已选 N 帧'），可单个移除或清除"

  embedded_tools:
    placement: "assistant 消息内，片段序列之后"
    see: Section 11
```

---

## 11. BrowserViewport（Computer Use 视口）

```yaml
browser_viewport:
  description: "Agent 调用浏览器工具时，在对话气泡内嵌入实时视口"
  trigger: "agent 调用 browser / computer use 工具"
  placement: "assistant 消息内，片段序列（步骤组与文字）之后"

  layout:
    width: "100%"
    min_height: 240px
    max_height: 480px
    default_height: 320px
    border: "1px solid #E0DDD8"
    radius: 4px
    background: "#FFFFFF"

  chrome:
    address_bar:
      height: 32px
      font: mono_sm
      background: "#FAF8F5"
      border_bottom: "1px solid #E0DDD8"
      show_url: true
      show_lock_icon: true
    controls:
      - "刷新"
      - "展开（切换为全屏 overlay）"
      - "停止"

  viewport:
    sync_mode: "随回答的 SSE 流：每个动作之后一张截图（browser.frame，JPEG data URL），不是连续视频流"
    resize: "远程视口固定 1280×800；本地显示区按 16:10 居中（container query），光标坐标是相对截图的比例，所以不会偏"
    stream: "browser.open → browser.action（action / detail / x / y / url，失败的动作带 error）→ browser.frame，按发生顺序"
    cursor_indicator:
      enabled: true
      style: "小圆点 + 涟漪，#C8F04A"
      show_click: true

  actions_log:
    position: "视口下方"
    style: "mono_sm，折叠显示"
    entries:
      - "click (x, y)"
      - "type '...'"
      - "navigate '...'"

  performance:
    pause_when_offscreen: true
    low_quality_mode: "低端设备降低帧率至 5fps"
```

---

## 12. Motion Principles（动效原则）

```yaml
motion:
  principles:
    - "所有状态过渡必须有明确的 duration 和 easing"
    - "禁止统一使用 opacity:0 + translateY(20px) 作为所有入场动效"
    - "动效目的：反馈状态变化，而非装饰"
    - "遵循 Remotion + GSAP 分工：Remotion 负责场景级序列，GSAP 负责组件级微交互"

  tooling:
    remotion:
      use_for: "场景级序列、帧精确控制、阶段切换编排"
      example: "<Sequence>、interpolate"
    gsap:
      use_for: "组件级交互、hover、click feedback、mask transitions"
      example: "gsap.to、gsap.timeline"

  standard_easings:
    enter: "power2.out"
    exit: "power2.in"
    move: "power2.inOut"
    bounce: "back.out(1.4)"

  standard_durations:
    micro: 0.2s
    short: 0.4s
    medium: 0.8s
    long: 1.2s
    scene: 1.6s

  micro_interactions:
    button_press:
      scale: { from: 1, to: 0.97 }
      duration: 0.1s
      easing: "power2.out"
    sheet_hover:
      see: Section 8
    chat:
      step_group_shimmer: "1.8s linear infinite（运行中）；收起 350ms，见 Section 9.3"
      step_row_expand: "0.24s power2.out / 收起 0.18s power2.in，见 Section 9.3"
      step_detail_entrance: "行 stagger 0.05s、概率条 0.6s、判定章 back.out(1.4)，见 Section 9.4"
      source_cards: "0.4s power2.out，stagger 60ms，见 Section 10"
      slash_menu: "0.16s power2.out，见 Section 10"
      jump_to_latest: "0.2s power2.out，见 Section 10"
      timeline_fold: "0.4s power2.inOut，见 Section 8"
    reduced_motion: "以上入场动画全部直接显示终态；流光与计时保留但放慢"
```

---

## 13. Anti-Patterns（禁止项）

```yaml
anti_patterns:
  visual:
    - "禁止大圆角卡片瀑布（border-radius > 8px 的卡片堆叠）"
    - "禁止彩虹渐变、霓虹光晕、厚重投影"
    - "禁止随机编号和伪代码堆叠"
    - "禁止使用 emoji 作为界面图标（除非明确指定）"
    - "禁止超过 #C8F04A / #F5A623 / #E5484D 之外的高饱和色"

  motion:
    - "禁止统一使用 opacity:0 + translateY(20px) 作为所有入场动效"
    - "禁止无 easing 的线性过渡"
    - "禁止超过 0.4s 的 hover 反馈"

  threejs:
    - "禁止为雕塑的每个薄片创建独立 Mesh（必须使用 InstancedMesh）"
    - "禁止使用 flat 材质或非哑光材质"
    - "禁止超过 500 个实例"

  streaming:
    - "禁止把所有工具调用堆在回答上方：按发生顺序折叠为步骤组，与回答文字交错"
    - "禁止在主消息流中展开显示完整工具调用 JSON"
    - "禁止在 streaming 过程中滚动跳动"
    - "禁止在步骤详情（StepDetail）外显示 raw stdout/stderr"
    - "禁止把模型推理轮次列为步骤（token 用量放在回答底部统计行）"

  data:
    - "禁止硬编码颜色 hex（必须使用 Token）"
    - "禁止硬编码间距（必须使用 spacing scale）"
```

---

## 14. Agent Prompt Summary（最终指令摘要）

```markdown
你正在实现 VideoComprehensive 视频理解工作台的前端界面。

## 核心约束
- 所有颜色使用 Section 1 的语义 Token，禁止硬编码 hex
- 所有间距使用 Section 3 的 spacing scale
- 雕塑使用 InstancedMesh，参数见 Section 7
- 所有动效必须有 duration + easing，参考 Section 12
- 流式事件按 Section 9 的事件类型映射到组件
- 工具调用按发生顺序折叠为步骤组，与回答文字交错；步骤详情点开才看（Section 9）

## 阶段流程
1. 空闲态：SculptureCanvas + 视频导入入口
2. 上传中：ContourLoader 遮罩覆盖雕塑
3. 分析中：雕塑翻转深色 + 加速旋转
4. 对话态：ChatThread（步骤组与文字交错、来源卡片、Composer）+ 下方可收起的 TimelineSculpture

## 禁止
- 大圆角卡片、彩虹渐变、霓虹、厚重投影
- 统一 opacity + translateY 入场动效
- 独立 Mesh 渲染每个薄片
- 主消息流展开原始工具调用 JSON
- 工具调用全部堆在回答上方

## 若需求未在本文件定义
生成前先提问，禁止自行发挥。
```
