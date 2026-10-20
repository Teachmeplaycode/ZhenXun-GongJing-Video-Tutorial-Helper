# 开发与核验过程

项目：[Teachmeplaycode/MyTargetProject](https://github.com/Teachmeplaycode/MyTargetProject)。本次 C 工作线对应 [Issue #31](https://github.com/Teachmeplaycode/MyTargetProject/issues/31)，分支 `docs/competition`，只增加本目录的五份文档。

## 实际发生的工作

- 2026-10-20，主会话准备真实 `origin/main` 的干净快照，版本 `34b38f0f74a1b85dd1cba167a4063a6642eab44f`，270个文件；main归档SHA256为 `6a1fe3cf02e3336519bdc485ed9b94968536191c50a5f2e207fa006f8f58965a`。不含本地环境配置、登录态、数据目录或未提交改动。
- 原先上传到主机目录，CodeArts隔离沙箱未找到输入。经资源管理器上传到对应CodeArts沙箱后，A会话校验了归档大小和SHA；保留了输入阻塞记录，未用旧源码冒充本次输入。
- C初次请求的持久历史显示“无响应内容”，并未开始写文档。主会话在原会话续作，确认了任务读取、SHA核验、真实Git元数据读取和五个文档的写入工具记录。
- C实际使用 `huaweicloud-maas/OpenPangu-2.0-Flash`。它在 `/workspace/gongjing-20261020/c-docs` 初始化的是仅含新增文档的空Git仓库，并未建立完整main源码基线；其合成提交 `95d23dc` 只用于云端产物记录，不能推入真实项目历史。主会话取回完整新增文件补丁，并在真实main的独立工作区验证和应用。
- 首版云端补丁 `C-docs.patch` 为37004字节，SHA256 `d0eff94a425bdfe62082ed3f43be69221baeb728a16846e99d4b561ad861f4ca`；经CodeArts网页下载到本机，持久保存补丁与报告。初稿的7/29旧计数、无效factcheck参数、上传即删说明和未经测量的耗时被本地源码核对发现并纠正；原云端报告保留，不能把它的估算行数或“核验通过”全部当成事实。
- 向原C会话发送修正清单时平台返回 `Invalid params`，没有产生该轮修正工具输出。本地主会话完成文档修正；不把失败请求算成云端已执行修正。

记录位置：CodeArts WebUI的“C#31比赛复现与数字审计文档”历史；本聊天持久目录 `codearts-20261020/dispatch.json`、`monitor.json`、`artifacts/C-docs.patch`、`C-docs-report.md`、`C-local-validation.json`。工作流截图如需展示，应截取真实页面并隐去地址栏票据/账户信息；没有可用截图时保留缺项，不回填历史活动。

## 本地实际检查

环境：macOS Apple Silicon；独立文档工作区。只读借用既有backend虚拟环境解释器，未读取或复制主工作区密钥。下表为2026-10-20本轮实际输出，耗时是单次观测，不代表全新安装或真实模型评测耗时。

| 命令（backend目录） | 退出码 | 耗时（秒） | 验证范围 |
| --- | --- | --- | --- |
| `python scripts/eval.py --help` | 0 | 0.18 | 参数帮助，无网络/模型问答 |
| `python scripts/factcheck_eval.py --help` | 0 | 0.093 | 参数帮助，无网络/模型问答 |
| `python scripts/bench.py --help` | 0 | 0.086 | 参数帮助，无网络/模型问答 |

此外，主会话通过JSON解析核对了11视频/47题和42草稿/165说法/reviewed=0，检查了playback/source API及评测脚本参数。未执行全新Mac安装、完整pytest/Playwright、模型准确率、视频导入或Linux容器验收；文档改动的验证范围限于这些静态检查与命令帮助。

## A/B/C 所有权与交接

| 工作线 | Issue | 真实分支 | 指定模型 | 范围 |
| --- | --- | --- | --- | --- |
| A | [#8](https://github.com/Teachmeplaycode/MyTargetProject/issues/8) | `feat/cloud-adapters` | GLM-5.3 | ASR/OCR/deploy/intent |
| B | [#30](https://github.com/Teachmeplaycode/MyTargetProject/issues/30) | `feat/agent-budget` | DeepSeek-v4.1-Flash | budget/run/UI/eval |
| C | [#31](https://github.com/Teachmeplaycode/MyTargetProject/issues/31) | `docs/competition` | OpenPangu-2.0-Flash | 本目录文档 |

A/B需保持 `intent.classify(question, decider)` 兼容，通过带默认值的usage/elapsed_ms元数据计入预算；组合验证要等实际分支产物，不能拿单分支mock当集成验收。D软件教程验收集由用户选片、确认答案。

WorkSwarm本轮仅检查了工具帮助；向其沙箱传源码被自动审批拒绝，正在等待具体目的地授权。DeepSeek Harness仅检查了帮助和模型列表，现有列表只有GLM-5.2、OpenPangu-Flash、GLM-5.1，尚未用DeepSeek执行实际任务。用户要求Harness必须用真正DeepSeek模型；配置/实际执行完成前不写成已使用。这些状态可能随续作改变，应以持久分派记录和对应真实产物更新。

## 真实 Git / PR 证据

下面来自主会话2026-10-20导出的真实GitHub元数据，不是云端合成git log；仅代表当时快照，PR标题中的性能数字仍需原始结果核验。完整main历史另存 `real-main-history.txt`。本次不自动合并。

| PR | 分支 | 合并时间（UTC） | 标题 |
| --- | --- | --- | --- |
| [#29](https://github.com/Teachmeplaycode/MyTargetProject/pull/29) | `feat/suggest` | 2026-10-20T03:58:45Z | 为每个视频生成推荐问题，点一下就问 |
| [#28](https://github.com/Teachmeplaycode/MyTargetProject/pull/28) | `feat/intent` | 2026-10-19T23:35:19Z | 意图识别：教程、核查、反诈等问题各按各的方式回答 |
| [#27](https://github.com/Teachmeplaycode/MyTargetProject/pull/27) | `feat/skills` | 2026-10-19T23:19:31Z | 反诈、科普核查改为 agent 技能；最后一轮工具调用乱码修复 |
| [#26](https://github.com/Teachmeplaycode/MyTargetProject/pull/26) | `feat/evidence` | 2026-10-19T16:50:55Z | 帧见：结论—证据类型—时间—点击回看，回答完成前逐条校验引用 |
| [#25](https://github.com/Teachmeplaycode/MyTargetProject/pull/25) | `feat/playback` | 2026-10-19T16:19:19Z | 帧见：回答里的时间点回看原片，三种证据状态如实标注 |
| [#24](https://github.com/Teachmeplaycode/MyTargetProject/pull/24) | `data/factcheck-eval` | 2026-10-19T12:23:52Z | 科普核验：评测集与第一轮修复（说法抽取 28% → 73%，错误说法拦截 18% → 48%） |
| [#23](https://github.com/Teachmeplaycode/MyTargetProject/pull/23) | `feat/home` | 2026-10-19T05:31:03Z | Home: one import card for links, files and pictures; simpler settings; mascot |
| [#22](https://github.com/Teachmeplaycode/MyTargetProject/pull/22) | `feat/images` | 2026-10-19T00:16:46Z | Picture posts: calmer page, the post's body text, 小红书 comments |
| [#21](https://github.com/Teachmeplaycode/MyTargetProject/pull/21) | `feat/deepseek-search` | 2026-10-19T00:15:10Z | Search: DeepSeek search first, sources weighed by authority; Bocha removed |
| [#20](https://github.com/Teachmeplaycode/MyTargetProject/pull/20) | `feat/images` | 2026-10-18T17:53:53Z | 图集与图片：纯图文按图片集分析，不走视频流程，界面适配 |
| [#19](https://github.com/Teachmeplaycode/MyTargetProject/pull/19) | `feat/alcedo` | 2026-10-18T17:52:37Z | 更多来源：用 alcedo 接入抖音、YouTube、快手、小红书等 35 个平台 |
| [#18](https://github.com/Teachmeplaycode/MyTargetProject/pull/18) | `feat/sampling` | 2026-10-18T17:45:39Z | 采样设置：三档预设、按镜头补帧、画面不变不重复识别文字；长视频读取再加固 |
| [#17](https://github.com/Teachmeplaycode/MyTargetProject/pull/17) | `fix/long-video-reads` | 2026-10-18T12:34:45Z | 修复：长视频读取中途断开后静默截断；回答 2048 token 截断 |
| [#16](https://github.com/Teachmeplaycode/MyTargetProject/pull/16) | `feat/workbench` | 2026-10-18T12:54:19Z | 工作台侧栏、AI 网课笔记与画布编辑器、时间轴长按放大与输入区间 |
| [#15](https://github.com/Teachmeplaycode/MyTargetProject/pull/15) | `feat/export` | 2026-10-18T12:54:21Z | feat(export): 勾选会话问答导出 Markdown 与 PDF 打印页 |
| [#14](https://github.com/Teachmeplaycode/MyTargetProject/pull/14) | `feat/antifraud` | 2026-10-18T12:54:21Z | 反诈风险线索、机构公开证据与模型复核 |
| [#13](https://github.com/Teachmeplaycode/MyTargetProject/pull/13) | `feat/chapters` | 2026-10-18T12:54:21Z | feat: 后台生成视频章节目录与摘要 |
| [#12](https://github.com/Teachmeplaycode/MyTargetProject/pull/12) | `feat/factcheck` | 2026-10-18T12:54:21Z | feat: 新增视频科普核查报告与证据展示 |
| [#9](https://github.com/Teachmeplaycode/MyTargetProject/pull/9) | `ci/github-actions` | 2026-10-18T07:05:53Z | CI: 每个 PR 自动跑 pytest 和 Playwright |

元数据包含19个已合并PR。C文档分支的Draft PR链接由主会话创建后补充；未创建之前不编造链接。
