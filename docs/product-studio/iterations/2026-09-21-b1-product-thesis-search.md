# Iteration：B1 Product Thesis 搜索与人工选择

- 日期：2026-09-21
- 状态：Closed
- 路线图工作包：Phase B 第 1–2 步
- 类型：Domain / API / UI / Workflow / Validation

## 目标

基于 A6 已确认的 `ProblemModel` 与 `OutcomeContract`，通过可恢复的持久化 Job 一次生成 2–3 条在机制、实现方式和最低成本证伪方法上有实质差异的 `ProductThesis` proposal；用户可以在 Web 工作台并列比较，并具名选择任一路径或只授权其低成本探索。

本批次只开始 Phase B，不声称完成数字产品生成闭环，也不把确定性 provider 输出当作研究事实或现实结果。

## 基线

- Phase A 已关闭；A6 冻结了“自主管理工作的知识工作者保护 25–60 分钟桌面专注时段，同时保留紧急联系控制”的第一版 Outcome Contract。
- 领域/Application Service/SQLite/HTTP 已支持单条 `ProductThesis` proposal 与 disposition，但没有成组生成 Job、Web 生成入口或可比较的人类选择界面。
- A5 proposal Job 已具备 enqueue、显式单步执行、revision pin、fingerprint 幂等、stale/失败分流和 SQLite 重启恢复。
- 最近完整验证基线：Python 455 passed、2 skipped；前端 10 passed；Chromium E2E 2 passed；production build、依赖检查通过。

## 范围

- 将 thesis 搜索加入现有 proposal Job 边界，pin 已确认的 problem/outcome revisions；
- deterministic fake provider 为首条切片生成三条差异路径，并显式保留 model-proposal 来源；
- 持久化一组结果 revision，支持重复执行、重启恢复、stale input 和部分提交后的幂等协调；
- HTTP/OpenAPI 暴露 thesis 批次 Job；
- 工作台显示机制、差异、证伪测试、风险和交付负担，并允许发起生成；
- 决策区让人从任一候选中选择或授权低成本探索。

## 非目标

- 不接真实模型、网络研究或外部通知/消息系统；
- 不决定 Web 生成模板、沙箱、模型/工具预算和反馈采集边界；
- 不生成、安装、构建或运行产品代码；
- 不将软件测试升级为真实用户结果证据；
- 不引入常驻 worker、SSE、多队列或多人治理。

## 验收条件

- Given 已确认且仍为 current 的 ProblemModel/OutcomeContract，When 创建并运行 thesis Job，Then 持久化 2–3 个不同机制的 proposal，并将所有结果 revision 记录到 Job；
- When 同一上游 revision 重复请求或 worker 在提交后重试，Then 不重复创建候选，且可协调为 succeeded；
- When pinned 上游在执行前变化，Then Job 进入 `stale_input`，不提交新 thesis；
- Given 三条候选，When 用户打开工作台，Then 能比较机制、最低成本证伪、风险和成本，而不是只看到名称；
- When 用户选择任一候选或授权探索，Then 通过现有 Domain Command 创建具名 disposition revision；
- Python 领域/API 测试、前端单测、OpenAPI 类型生成、production build 与 Chromium E2E/axe 通过。

## 实施记录

- 2026-09-21：工作包开始。选择扩展 A5 的持久化 proposal Job，而不是新建同步 thesis 生成端点；本批仍使用无网络的确定性 provider，以验证状态、恢复和人工 Gate。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain | `ProductProposalJob` 支持 `product_theses` 三结果 batch；确定性 provider 提供三条切片候选 | `src/psyteardown/product/models.py`, `src/psyteardown/product/jobs.py`, `src/psyteardown/product/providers.py` |
| API | Job DTO/OpenAPI 支持 `product_theses`、`result_object_ids` 和 `result_revision_ids` | `src/psyteardown/api/schemas.py`, `studio/openapi.json` |
| UI | 工作台可触发和比较候选；决策区逐条授权探索或选择 | `studio/src/views/WorkbenchView.tsx`, `studio/src/views/DecisionsView.tsx` |
| tests | 批量差异、幂等、stale 和 HTTP 选择链路 | `tests/product/test_jobs.py`, `tests/api/test_proposal_jobs.py` |

## 决策与偏差

- `product_theses` Job 是可回退的首条切片实现假设，不是通用模型编排架构。
- PS-O004/005/006/007 仍保持 open；本批不越过对应 Gate 进入代码生成、执行或反馈采集。

## 验证

- 命令：`pytest -q`; `Push-Location studio; npm test -- --run; npm run build; Pop-Location`
- 结果：Python 459 passed、2 skipped、2 warnings；前端 11 passed；production build 成功
- Chromium：既有第二条 Product Contract E2E 已延伸覆盖 thesis batch、工作台比较和逐条探索/选择；2 条 Chromium/axe E2E 均通过
- 现实证据边界：确定性测试只能证明 proposal/revision/选择工作流，不能证明任何论点会减少真实中断或保持紧急联系。

## 数据与迁移

- 计划仅向持久化 Job JSON 增加带默认值的多结果字段，不增加 SQLite 表；既有 A5 Job 必须仍可读取。
- API schema 将新增 `product_theses` kind 和多结果 revision 列表；前端类型由 OpenAPI 重新生成。

## 遗留项与风险

- 真实 provider、预算和输入保留边界仍未决定；
- thesis 批次提交跨多个 aggregate，不是单事务；本批必须验证中断后的幂等协调，不能伪称原子写入；
- 本批不会改变现实证据等级。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（如适用）
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档（如适用）

## 下一最小工作包

在 B1 验证后，关闭 PS-O004：选择单一 Web 技术模板并定义内容最小化生成契约；在首次执行生成代码前另行关闭 PS-O005/PS-O006。
