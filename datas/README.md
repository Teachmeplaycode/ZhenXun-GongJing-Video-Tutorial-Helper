# datas

链接解析的测试数据集，按平台分目录。目前只有 B 站（`bilibili/links.json`，60 条）。

## B 站用例覆盖

| 类别 | 数量 | 说明 |
| --- | --- | --- |
| `old` | 15 | 2009–2023 年每年一条老视频（Bad Apple!!、拜年祭、鬼畜等） |
| `recent` | 17 | 近期视频，各来自不同分区（游戏、数码、美食、音乐、知识、汽车、娱乐…） |
| `multipart` | 6 | 多 P：第 3P、69P 合集的最后一 P、138P 合集的第 100P、80 分钟长分P 等 |
| `short` / `long` | 6 / 4 | 一分钟内的短视频、一小时以上的长视频 |
| `normal` | 1 | 最早的公开视频 av2 |
| `error` | 11 | 不存在、番剧、课程、用户主页、直播间、分P越界、没有链接、BV 号不完整等 |

输入格式轮换覆盖 13 种：标准链接、网页分享链接（带 `share_source`/`vd_source`）、带标题的分享文本、App 分享文本（`b23.tv` 短链）、只有 BV 号、BV 号夹在句子里、av 号链接、只有 av 号、手机版链接、没有 `https://` 的链接、带 `spm_id_from`、带 `?t=` 时间点、活动页链接（`?bvid=`）。

## 用例格式

```json
{
  "id": "bili-multipart-share-text",
  "category": "normal | multipart | long | short | error",
  "note": "这条用例要覆盖什么",
  "input": "粘贴进输入框的原文：链接、分享文本或 BV 号",
  "expect": {
    "ok": true,
    "video_id": "BV…", "part": 3, "part_count": 4, "duration": 203,
    "title": "…", "author": "…"
  },
  "observed": { "date": "…", "frames_ok": 64, "frames_total": 64, "first_frame_sec": 3.3, "total_sec": 60.5 }
}
```

- `expect` 是校验项。`video_id`、`part`、`part_count`、`duration`（允许 ±1 秒）不一致即判失败；`title` 和 `author` 可能被 UP 主修改，不一致只给出提示。
- 解析失败类用例写 `"ok": false` 和预期的错误码 `code`（见 `backend/modules/video_source/bilibili.py`）。
- `observed` 记录最近一次完整抽帧的实测结果，仅作参考，不参与校验。

## 重新验证（需要联网）

```bash
cd backend
uv run python scripts/check_links.py                     # 只解析，逐条比对 expect
uv run python scripts/check_links.py --frames 16         # 同时每条抽 16 帧，报告覆盖率和耗时
uv run python scripts/check_links.py --only bili-long-bare-bv
uv run python scripts/check_links.py --frames 16 --record   # 抽帧结果写回 observed（已有记录的保留，加 --overwrite 覆盖）
```

全量 60 条、每条抽 16 帧约需 20 分钟。公开视频可能被删除或改标题：`video_id`、分P、时长不一致才判失败，标题或 UP 主变化只提示。

新增平台时，在 `datas/<platform>/links.json` 按同样格式添加用例即可，脚本会自动读取所有平台目录。
