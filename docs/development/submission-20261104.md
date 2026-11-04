# 2026-11-04 提交版本收敛

2026-11-02 比赛修订包的消息分组修复尚未进入 GitHub main，最新 Windows 源码与旧修订包不能直接相互替换
从当前 main 42b3556 建立独立分支，原本机 main 的未提交内容保持原样

导入已存在的网页码道修复：
- 原修复提交：594d70878d2b94aba9520879ffa3729774183d67
- 原补丁：release/competition-review-20261102/codearts_proof/2026-10-30/cloud-results/fix-question-last.patch
- 补丁 SHA-256：48cad0cec3ebc26c6b6f084e542a45bd3f17d81f676ca918771910e1854d8b60
- git am 保留原补丁作者及 AuthorDate，实际导入 CommitDate 为本轮真实日期
- 原 Git 对象不在 GitHub 仓库，移植后 SHA 不同，不宣称保留原提交对象
- 加入此前 IDE 真实生成并验证的 test_prelook_attachment_edges.py 两项边界用例

修复前在最新 main 运行修订包八项回归，实际为 4 failed / 4 passed
失败组合是截图（含定位说明）与时间段慢放复看并存，原 pop() 移错了截图或说明，破坏消息分组
现按 scope、attachments、prelook、question 的明确分组组装，问题恰好出现一次并在预看场景保持最后
没有预看的旧结构保持不变，缺失附件不生成附件说明

本轮目标是让比赛源码同时包含已有码道修复和 Windows/设置功能
测试使用模拟模型 transport，不发起真实付费调用
PPT、视频由作者在别处完成，候选包仅放明确占位说明，组别待作者按报名信息填写
