# 数字与口径审计

范围是已提交的 `README.md`、`backend/README.md`、`docs/**/*.md`、`essay/*.md`，基于 `34b38f0f`。本轮核对的是文档出处与已提交 JSON 的静态计数；未重跑模型评测，也未读取主工作区 `backend/data` 或未提交材料。历史文档有出处不等于本轮重新验证。

| 数字/口径 | 出处 | 原始数据/复核入口 | 本轮结论与建议表述 |
| --- | --- | --- | --- |
| 11 视频 / 47 题 | `backend/evals/cases.json` | videos/cases 的 JSON 长度 | 本轮静态计数；README 的 7 视频 / 29 题已过时，参赛材料应写 11/47。人工质量与目标覆盖仍待验收 |
| 42 条 / 165 说法 / reviewed=0 | `backend/evals/factcheck.json`；`docs/evals/factcheck-review.md` | items/claims/reviewed | 本轮静态计数；必须称“待人工复核草稿”，不能写成已确认标准答案 |
| 说法抽取 28%→73%、错误拦截 18%→48% | [PR #24](https://github.com/Teachmeplaycode/MyTargetProject/pull/24) 标题 | `backend/data/evals-factcheck/results/` 历史运行 | 只确认历史 PR 表述；未重算分母/人工标签，使用时标为历史阶段结果，不能当当前模型验收率 |
| 4018 道 / 六题型 | `docs/experiments/2026-10-17-motionbench.md`“方法” | `backend/data/bench/motionbench/` | 历史文档报告的 MotionBench 开发集规模；不等于本项目人工验收集数量 |
| C 62.5% / 重跑63.0%；E 63.3% | 同文“量化校准” | `backend/data/bench/results/n100/` | 测试600题，不同配置。C为手写校准，E为学到的量化校准；不能统一成一个数字 |
| C 61.7% / 重跑62.2%；E 65.0% | 同文“验证集检验”“量化校准” | `backend/data/bench/results/` 的 val 运行 | 验证360题、seed31、温度0；不可和600题测试集混用 |
| C 12.2k；E 12.9k 平均输入token | 同文“量化校准” | 测试集逐题usage | 仅测试配置的平均输入token，不是输入+输出总token，也不是人民币成本；缺价格和完整usage不估算费用 |
| 验证C约12.4k；D3约19.9k | 同文“验证集检验” | 验证集逐题usage | 集合/配置不同，不能拿测试C12.2k替代验证C12.4k |
| C 600题约730万；验证360题约450万输入token | 同文“下一步”“如何继续” | 对应历史结果JSON | 是整组输入用量，不能和单题均值直接比较或当作模型总费用 |
| C/E测试差异p=0.71/0.92，验证p=0.096 | 同文“量化校准” | 历史配对运行及检验 | 文档报告未达显著；勿声称E显著优于C |
| 成长曲线趋势p=0.34 | 同文“成长曲线” | 对应历史运行 | 未证明“随练习持续增长”，不能在PPT写成已验证结论 |
| 约13GB、视频3.8GB、结果18MB | 同文“如何继续” | 本地 `backend/data/bench/` 目录 | 历史磁盘快照，不是当前大小，也不是题量/token；本轮未测量 |
| “约13万” | 本轮检索的已提交md未定位到对应原句 | 需用户指出原文与原始结果 | 保留待核实；不猜成13GB误读，不擅自改数字 |
| Alcedo额外35个平台 | `backend/README.md`、[PR #19](https://github.com/Teachmeplaycode/MyTargetProject/pull/19) | alcedo版本、各平台导入记录 | 支持清单不等于本轮所有平台导入成功；网络/签名/登录限制需真实平台验收 |
| pytest/Playwright数量、约5分钟评测、约15秒E2E | README的历史说明 | 对应SHA的真实日志 | 数量与耗时随版本、硬件、网络改变。本轮文档检查没有重跑全套，不回填新的通过数 |

## 可重复的静态计数

在仓库根目录执行，不需要密钥或网络：

```bash
python3 - <<'PY'
import json
from pathlib import Path
c = json.loads(Path('backend/evals/cases.json').read_text())
f = json.loads(Path('backend/evals/factcheck.json').read_text())['items']
print('videos', len(c['videos']), 'cases', len(c['cases']))
print('items', len(f), 'claims', sum(len(i['claims']) for i in f.values()),
      'reviewed', sum(bool(i.get('reviewed')) for i in f.values()))
PY
rg -n '13万|130000|62[.]5|63[.]3|token' README.md backend/README.md docs essay -g '*.md'
```

本轮计数结果为 `videos 11 cases 47`、`items 42 claims 165 reviewed 0`。原始运行数据未纳入云端输入，准确率、成本、文件大小及“约13万”的口径仍需对应原始结果核查。请同时记录集合、配置、模型、温度、运行SHA、分母和人工标签状态，不把“静态一致”写成“验收通过”。
