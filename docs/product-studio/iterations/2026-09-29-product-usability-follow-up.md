# Iteration：Product Usability follow-up（稳定重提案与双选项旅程）

- 日期：2026-09-29
- 状态：已关闭
- 范围：B2 Web generation contract、B3 deterministic renderer、B4 contract-derived browser test、C1 前置门槛

## 触发

上一轮已经把首条 Web 原型改成选项对比板，但实际项目重新生成时暴露出两个工程问题：已有 singleton Web contract 会被错误地分配新 ID，导致 proposal Job 失败；渲染器虽然显示两个选项，但三类记录仍是全局共享字段，无法真正比较两个选项。

## 修正

- Web proposal Job 在已有契约上复用稳定 aggregate ID 和 expected revision，提交为下一个 `proposed` revision；增加目标 revision 指纹与运行前冲突检查，避免重复点击或旧 Job 静默覆盖。
- 工作台对已有 Web contract 显示“重新生成 Web 契约提案”，但不替用户确认；当前项目 `project-6356cb573d984a909f813ff3b7f81ea1` 已生成 `web-contract-391dfa4a03174521a289d42c2b16d0b9.r4`，状态仍为 `proposed`。
- deterministic renderer 改为每个选项独立保存名称、决策标准、已知信息和顾虑；记录判断页展示两列摘要、用户自己的倾向和下一步核实问题；不评分、不排序、不推荐。
- 修正 generated template 的 accessibility 对比度与 required content-slot 标记；保留“刷新会清空”的本地边界提示，不把示例 fixture 当成真实数据。

## 验证

- Python 目标回归：`51 passed, 1 warning`（product source-model/jobs/generation/execution）。
- 前端：`36 passed`；`npm run build` 成功。
- r4 独立生成 workspace：`npm run build` 成功；contract-derived Playwright/axe `1 passed`；双选项独立输入、记录倾向和 axe journey `1 passed`。
- 旧 B6 ZIP 未修改；没有自动确认 r4、没有生成新的 B6、没有启动 C1，也没有创建现实参与者数据。

## 下一步

负责人需要在 Product Studio 审阅 r4 proposed Web contract：确认页面、主流程和字段确实符合自己的真实任务后，点击“确认 Web 生成契约”；再生成并下载新的 B6 ZIP。只有负责人亲自走完新交互包的核心任务后，才考虑 Product Usability Gate 和 C1；`PSYTEARDOWN_C1_TRIAL_ENABLED` 继续保持 `0`。
