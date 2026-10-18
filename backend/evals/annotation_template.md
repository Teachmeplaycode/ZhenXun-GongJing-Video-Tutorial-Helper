# 评测集人工标注模板（Issue #7）

本模板用于把候选视频和题目补入 `cases.json`。**视频需人工挑选**（版权和内容把关），
每道题的**标准答案需人工确认**；agent 可以根据转写帮忙出题、写 rubric，但不能替人确认。

## 1. 视频类别（6 类，每类目标 ≥ 5 个视频）

| key          | 中文名     | 内容方向（供挑视频参考，不限定具体视频）             |
|--------------|-----------|---------------------------------------------------|
| lecture      | 课程讲座   | 大学公开课、MOOC 片段、知识讲解                    |
| tutorial     | 软件教程   | 软件/工具操作演示、开发实战                        |
| news_review  | 新闻测评   | 新闻事件、产品评测、资讯盘点                        |
| sports       | 运动       | 体育赛事、户外运动、健身                            |
| vlog         | 生活 vlog  | 日常记录、美食、旅行、宠物                          |
| ad_shopping  | 广告带货   | 直播带货、广告片、商品种草                          |

## 2. 题型（5 种）

| key            | 中文名       | 典型问法                          | checks 提示                     |
|----------------|-------------|----------------------------------|--------------------------------|
| locate         | 定位        | "哪里讲了…""在什么时候说到"        | `timestamps: true`             |
| visual_detail  | 画面细节    | "画面里出现了什么""字幕写了什么"    | 常配 `frames.view` 或画面字幕   |
| action_count   | 动作与计数  | "失败了几次""做了什么动作""带了多少"| 常配 `timestamps: true`         |
| summary        | 总结        | "讲了什么""整体内容是什么"         |                                |
| verify         | 核实        | "这个说法对吗""帮我查一下有没有依据"| 常配 `tools_any: web/papers`    |

## 3. 新增一个视频（填到 `cases.json` 的 `videos`）

```json
"<key>": {
  "url": "<人工挑选的视频链接，确认版权可用>",
  "note": "<时长、内容一句话描述、是否有口播/弹幕/字幕>",
  "category": "<上面 6 类之一>"
}
```

## 4. 新增一道题（填到 `cases.json` 的 `cases`）

```json
{
  "id": "<video-key>-<short-name>",
  "video": "<video-key>",
  "qtype": "<上面 5 种之一>",
  "question": "<问题>",
  "checks": {
    "contains_any": [["<必须出现的关键词之一>"]],
    "timestamps": true,
    "tools_any": ["web.search"],
    "tools_none": ["browser.use"]
  },
  "rubric": "<标准答案要点：人工确认后写在这里>"
}
```

`checks` 各字段都可选；`rubric` 是给 `--judge` 评分用的标准，**必须人工确认**。

题目还可带执行控制：`web`、`papers` 必须为 JSON 布尔值，省略时均为 `true`；
`frames` 为从 0 开始的非负整数数组，省略或空数组表示整段视频，非空时只选择这些帧。
题目层支持 `id`、`video`、`qtype`、`question`、`rubric`、`checks` 及这三个执行控制；
拼错或不受运行器支持的题目字段会在启动后端之前报错，避免以错误的联网权限或范围执行。

## 5. 确认流程

1. 人工挑选视频，确认版权和内容，填 `videos` 条目（含 `category`）。
2. 跑 `uv run python scripts/eval.py --prepare` 解析视频（帧 + 转写 + 画面文字）。
3. agent 根据转写出题、写 `rubric` 草稿；**人工逐题确认标准答案**。
4. 把确认后的题目从 `candidates.json`（候选区）移入 `cases.json`（已确认区）。
5. 跑 `uv run python scripts/eval_gap.py` 看缺口，重复直到达标。
6. 跑 `uv run python scripts/eval.py --judge` 出回归基线。

## 6. 候选区 vs 已确认区

- `cases.json`：**已确认**的用例，参与评测。
- `candidates.json`：**候选**，待人工确认，不参与评测。两者必须分开，不能混。
