# 码道 IDE 插件真实使用记录

本轮于 2026-10-31 在本机 VS Code 中实际使用码道插件，补齐浏览器码道材料之外的 IDE 操作记录

## 直接查看

- [Windows / 浏览器阅读入口](OPEN-FIRST.html)，完整解压后双击打开
- [13 张原始截图](截图浏览.html)，012–013 为连续重叠的最终结果和收尾视图
- [会话页面原文](会话页面原文.txt)，按无障碍树保存可访问文字，折叠卡片不等于完整展开日志
- [Windows 记事本文字副本](conversation-windows.txt)
- [插件真实活动日志节选](logs/CodeArts-Agent-runtime-excerpt.log)与[来源和原始行号](logs/log-provenance.json)
- [插件生成并采纳的两项边界测试](validation/test_prelook_attachment_edges.py)
- [四份完整 pytest 输出](validation/)

## 实际完成的工作

1. 打开项目，使用 CodeArts Agent 26.10.2（`HuaweiCloud.vscode-codebot`）审阅 `build_messages`、`attached_parts` 与真实 `run_agent` 的消息组装
2. 对照前一轮浏览器码道生成的真实修复补丁，确认当前 main 尚未合入该补丁，不把已有修复说成本轮新发现
3. 纠正首轮审阅把已有部分定位覆盖列为缺口、把缺失附件过滤误作丢失说明、把兼容旧顺序当缺陷的判断
4. 使用从当前 HEAD 导出的两份临时副本实跑补丁的六项回归，模型请求经 `httpx.MockTransport` 模拟
5. 插件新增两项真实入口边界测试，覆盖无预看时兼容旧顺序，以及全部附件路径缺失且有慢放时不虚构附件说明，并在两份副本中执行
6. 核对生成的测试后在插件内采纳，保存截图、页面原文和实际插件活动日志节选

插件会话界面显示的模型为 `DeepSeek-V4.1-Flash-1017`，测试中的模型请求均为模拟请求，两者应分开理解

## 可复核结果

| 副本 | 补丁自带六项回归 | 退出码 | 新增两项边界测试 | 退出码 |
| --- | --- | --- | --- | --- |
| baseline 原实现 | 2 passed / 4 failed | 1 | 2 passed | 0 |
| patched 应用已有补丁 | 6 passed / 0 failed | 0 | 2 passed | 0 |

四份日志保留真实失败输出与退出码，不用修复后的成功结果覆盖原实现失败日志
本轮只做这些专项验证，未重新执行全量后端测试或真实视频问答，不能将其描述为整个项目的新一轮验收

## 版本与文件边界

临时副本来自 Git HEAD `0a17ddd8def71d92b5c67505b6349061628e37a5`，仅导出已跟踪 backend，不复制 `.env`、`.venv` 或未提交改动
准备临时副本与应用已有补丁由 Codex 完成，IDE 插件负责本轮代码审阅、新增测试生成与四组实际测试执行，分工不混称
详情见 [review-baseline.json](review-baseline.json) 与 [verification.json](validation/verification.json)

插件生成的正式代码文件位于本目录 `validation/`，测试副本在 `/private/tmp/zhenxun-codearts-ide-20261031/`
本轮未修改主工作区 backend 中被审阅的源码，未进行 Git 提交或推送，之前存在的其他未提交修改保持原状
新增测试存放在证据目录，在副本 backend/tests 中执行，IDE 在证据目录直接查看时可能提示 modules 导入路径警告，以实际 pytest 输出和运行路径为准

## 证据说明

这些记录证明 2026-10-31 这一次真实 IDE 插件使用，不证明项目早期开发已经使用插件，不倒填日期
001 为安装后等待登录的准备记录，002 起为登录后的真实操作；编号是实际采集顺序，不宣称整组是逐页连续截屏，012–013 是连续收尾视图
所有 JPG 均为原始窗口捕获，没有修改聊天内容或拼造界面，尺寸和哈希见 [manifest.json](manifest.json)

运行日志通过插件“打开当前日志文件”命令定位，提交的是按标记筛选且逐行保持原文的活动节选，记录原日志 SHA256 与所选行号；未把包含账号响应等信息的整份原日志放入材料包
截图由 Codex 捕获归档，不把插件自动展示的产物列表当作插件生成截图的证据
原有《提问草稿_尚未发送.md》只是准备时的草稿，不作为已发生会话的证据

## 专项测试复跑

将本目录的测试放入与本轮对应版本的 backend/tests 后，用项目虚拟环境的 Python 执行

```bash
cd backend
.venv/bin/python -m pytest tests/test_prelook_attachment_edges.py -v
```

补丁自带的六项测试和修复内容在 `../2026-10-30/cloud-results/fix-question-last.patch`，请在独立副本中应用后再对照执行
