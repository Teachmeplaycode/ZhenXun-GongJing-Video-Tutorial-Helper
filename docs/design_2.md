
```yaml
agent_instructions:
  scope: "本项目所有前端界面组件、动效、交互"
  rules:
    - "所有颜色必须使用 Section 1 定义的语义 Token，禁止硬编码 hex"
    - "所有间距必须使用 Section 3 定义的间距刻度"
    - "所有动效必须包含 duration + easing，参考 Section 8"
    - "雕塑必须使用 InstancedMesh，参数见 Section 7"
    - "流式事件必须按 Section 9 的事件类型映射到组件"
    - "工具调用默认折叠，主消息流只显示用户输入和最终结果"
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
    pill: 999px   # 仅用于状态标签

  border:
    hairline: 1px solid var(--border-default)
    strong: 1px solid var(--border-strong)
    focus: 2px solid var(--border-focus)

  layout:
    page_max_width: 1440px
    page_padding: 24px
    wireframe_container_padding: 24px
    content_max_width: 960px
```

---

## 4. Component Registry（组件清单）

| 组件名 | 用途 | 所在 Section |
|---|---|---|
| `WireframeContainer` | 页面主容器，细线框包围 | 5 |
| `SculptureCanvas` | Three.js 薄片雕塑画布 | 7 |
| `UploadMask` | 上传时的等高线遮罩 | 6, 7 |
| `ContourLoader` | 等高线地形绘制动画 | 6 |
| `ProgressPill` | 内联进度标签 | 9 |
| `ChatThread` | 对话主容器 | 10 |
| `MessageBubble` | 用户/AI 消息气泡 | 10 |
| `Avatar` | 圆角矩形头像 | 10 |
| `ToolCallCard` | 工具调用折叠卡片 | 9 |
| `DiffViewer` | 文件改动 diff 展示 | 9 |
| `BrowserViewport` | Computer Use 浏览器视口 | 11 |
| `TimelineSculpture` | 薄片时间轴 | 8 |
| `SheetPreview` | 薄片 hover 预览卡 | 8 |
| `CompletionBanner` | 完成信息块 | 9 |

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
    below: TimelineSculpture
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
    indicator: "在输入框上方显示 '范围：整段视频'"
```

---

## 9. Streaming & Agent Trace Protocol（流式与追踪协议）

### 9.1 设计意图

采用 **Streaming Agent Execution + Tool Call Trace / Observability** 模式：主消息流只显示用户输入和最终结果；工具调用、bash 指令、文件改动默认折叠为摘要卡片，可展开查看。

### 9.2 事件类型与组件映射

```yaml
streaming:
  transport: "SSE (Server-Sent Events)"
  scroll_behavior: "sticky bottom, 用户上滚时暂停自动滚动"

  event_types:
    assistant.message.delta:
      component: "StreamingText"
      render: "逐字追加，光标 █ 闪烁"
      style: "body 字号，正常字色"

    progress.update:
      component: "ProgressPill"
      render: "内联标签：当前步骤名 + 百分比"
      style:
        background: "#1A1A1A"
        color: "#FFFFFF"
        font: mono_sm
        radius: pill
        padding: "4px 10px"

    tool_call.started:
      component: "ToolCallCard"
      render: "工具名 + 加载指示器，默认折叠"
      summary_line: "{tool_name} · 运行中..."
      indicator: "旋转小圆点，#C8F04A"

    tool_call.input:
      component: "ToolCallCard.Args"
      render:
        bash: "以 <code> 展示命令，等宽字体"
        params: "key: value 列表，key 用 secondary 色"

    tool_call.output:
      component: "ToolCallCard.Result"
      render:
        stdout: "mono 字体，surface_alt 背景"
        stderr: "mono 字体，#E5484D 文字"
        exit_code: "状态色标识：0 绿，非 0 橙/红"
      max_height: 320px
      overflow: "内部滚动"

    tool_call.completed:
      component: "ToolCallCard"
      render: "状态切换为 ✓，卡片自动折叠为单行摘要"
      summary_line: "{tool_name} · 完成 · {result_count} 项"

    file.edit.diff:
      component: "DiffViewer"
      render: "unified diff 格式"
      style:
        added: { background: "#E8F5D8", color: "#1A1A1A" }
        removed: { background: "#FBE0E0", color: "#1A1A1A" }
        context: { background: "#FAF8F5" }
        font: mono_sm
      max_height: 400px

    run.completed:
      component: "CompletionBanner"
      render:
        background: "#1A1A1A"
        color: "#FFFFFF"
        content: "总步骤数 · 耗时 · 操作摘要"
        font: mono_sm
        padding: 16px
        radius: 4px

  ui_rules:
    - "主消息流只显示用户输入和最终结果"
    - "工具调用详情默认折叠，摘要行显示工具名 + 状态 + 结果计数"
    - "10+ 工具调用时，折叠区域显示 '42 步操作' 而非逐条列出"
    - "工具状态用 data-status 属性驱动样式（done/error/running）"
    - "流式过程中禁止滚动跳动，使用 scroll anchor"
```

### 9.3 折叠卡片展开态

```yaml
tool_call_card_expanded:
  layout:
    - summary_line: "工具名 · 状态 · 计数"
    - args_section: "命令行 / 参数"
    - result_section: "stdout / stderr / exit_code"
    - diff_section: "如涉及文件改动，追加 DiffViewer"
  animation:
    expand: { duration: 0.24s, easing: "power2.out" }
    collapse: { duration: 0.18s, easing: "power2.in" }
  border:
    running: "1px solid #C8F04A"
    done: "1px solid #E0DDD8"
    error: "1px solid #F5A623"
```

---

## 10. Chat Interface（对话界面）

```yaml
chat:
  layout:
    container: "WireframeContainer 内，padding 24px"
    message_gap: 16px
    max_width: 960px
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
    assistant:
      align: left
      background: "#FFFFFF"
      border: "1px solid #E0DDD8"
      color: "#1A1A1A"
      radius: "6px 6px 6px 0"
      max_width: "80%"
      padding: "12px 16px"

  input_area:
    position: "底部 sticky"
    style:
      background: "#FFFFFF"
      border: "1px solid #E0DDD8"
      radius: 4px
      padding: 12px
    scope_indicator:
      default: "范围：整段视频"
      with_selection: "范围：已选 {N} 帧"
      style: "mono_sm, tertiary"

  embedded_tools:
    placement: "assistant 消息气泡内，位于工具调用卡片下方"
    see: Section 11
```

---

## 11. BrowserViewport（Computer Use 视口）

```yaml
browser_viewport:
  description: "Agent 调用浏览器工具时，在对话气泡内嵌入实时视口"
  trigger: "agent 调用 browser / computer use 工具"
  placement: "assistant 消息气泡内，工具调用卡片下方"

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
    sync_mode: "WebSocket"
    resize: "ResizeObserver 监听本地容器，同步到远程 Playwright viewport"
    stream: "画面流式传输"
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
    pill_appear:
      opacity: { from: 0, to: 1 }
      y: { from: 4, to: 0 }
      duration: 0.24s
      easing: "power2.out"
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
    - "禁止在主消息流中展开显示完整工具调用 JSON"
    - "禁止在 streaming 过程中滚动跳动"
    - "禁止在工具调用卡片外显示 raw stdout/stderr"

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
- 工具调用默认折叠，主消息流只显示用户输入和最终结果

## 阶段流程
1. 空闲态：SculptureCanvas + 视频导入入口
2. 上传中：ContourLoader 遮罩覆盖雕塑
3. 分析中：雕塑翻转深色 + 加速旋转
4. 对话态：ChatThread + 下方 TimelineSculpture

## 禁止
- 大圆角卡片、彩虹渐变、霓虹、厚重投影
- 统一 opacity + translateY 入场动效
- 独立 Mesh 渲染每个薄片
- 主消息流展开原始工具调用 JSON

## 若需求未在本文件定义
生成前先提问，禁止自行发挥。
```
