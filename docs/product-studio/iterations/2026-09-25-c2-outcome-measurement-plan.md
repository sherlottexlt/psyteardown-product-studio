# C2 — Outcome Contract 指标测量计划

- 工作包 ID：C2
- 开始日期：2026-09-25
- 关闭日期：2026-09-26
- 状态：Closed
- 路线图工作包：C2
- 类型：Domain / Workflow / API / UI / Validation
- 前置条件：C0 已关闭（真实 provider 链路一次成功）；用户于 2026-09-25 选择 C2 先于 C1/C3

> C2 的完成只表示测量计划可派生、可编辑、可确认并可恢复；不表示已经产生 Observation 或现实结果证据。

## 目标

把已确认 OutcomeContract 的成功指标、禁止结果与停止条件转成一份**可执行、经人确认、带 revision 的测量计划**，并在计划层面严格区分证据来源层：

1. 每个 `SuccessIndicator` 至少对应一个测量项（measure），测量项声明来源层、收集方法、值类型、阈值、缺失处理和"结果矛盾时回退到哪个上游对象"；
2. 来源层固定为 `software_check`、`runtime_event`、`user_report`、`research_observation`、`expert_review`；`model_interpretation` 不是可选来源层，永远不能作为测量证据；
3. 每个来源层有证据等级上限（ceiling），只有后续人工 `EvidenceReview` 才能真正提升证据等级；
4. 每个禁止结果对应一个 guardrail；计划引用合同的全部停止条件；
5. 计划确认有门禁：覆盖、来源层与指标 `required_evidence` 兼容、真实世界指标至少有一个当前可收集的测量项、唯一主测量、阈值不是占位符、样本边界与同意范围已写明；
6. OutcomeContract 产生新 revision 时，pin 旧 revision 的测量计划得到 `stale` 影响记录（复用现有 impact 机制）。

## 非目标

- 不招募参与者、不运行试用、不写入 `MeasurementObservation`/`EvidenceReview`（属于 C1）；
- 不做统计分析或预注册（旧内核 `ExperimentPlan` 绑定 DesignBrief/假设，PS-O010 仍 open，不在本包打通）；
- 不引入自动事件采集：PS-O007 仍禁止从预览自动采集，`runtime_event` 测量项只能声明为 blocked；
- 不调用真实模型：计划由确定性派生产生候选，人纠正并确认。

## 基线

- Python 532 passed、3 skipped（含 C0 真实链路测试；不含时 531 passed）；前端 24 passed；Chromium E2E 2 passed。
- 提交 `5d15f6d`（C0 收尾）。

## 验收条件

1. 领域模型 + 纯派生函数 + 门禁函数有单元测试（覆盖每条门禁的拒绝路径）；
2. 应用服务 derive/submit/confirm 命令走 `expected_revision`、事件、审计，InMemory/SQLite 均可恢复；
3. 合同修订后测量计划出现 `stale` 影响；
4. HTTP 端点 + OpenAPI + 前端生成类型；证据区展示计划、来源层、上限、可收集性、确认阻塞项，并可修改阈值后确认；
5. 全量 Python、前端单测、build、Chromium E2E 通过。

## 实施记录

### 已实现

- 新增 `OutcomeMeasure`、`MeasurementGuardrail` 和 `OutcomeMeasurementPlan` 不可变 revision 模型；measure/guardrail 的来源层固定为 `software_check`、`runtime_event`、`user_report`、`research_observation`、`expert_review`，并显式记录各层证据上限；`runtime_event` 两种记录都必须显示 blocked reason。
- 新增纯确定性派生与门禁：从已确认 Outcome Contract 为每条指标生成 measure，为禁止结果生成 guardrail，引用全部 stop condition；占位/空阈值及空样本/同意/撤回字段不能确认；`model_interpretation` 不属于测量来源，runtime event 在 PS-O007 下只能声明为 blocked。
- 应用服务支持 `derive`、`submit`、`confirm`，沿用 `expected_revision`、DomainEvent、AuditEvent、SQLite/InMemory repository 和 dependency impact；Outcome Contract 修订会为旧计划记录 `stale`。
- FastAPI 提供三个命令端点并更新 OpenAPI/生成 TypeScript；measure/guardrail response 由服务端计算 `evidence_ceiling` 与 `collectable`，避免前端另维护一份上限映射；Evidence 区显示阻塞项、样本/同意/撤回/护栏，并支持修改阈值后确认。

### 验证

- Python 确定性回归：`pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py` → **538 passed, 3 skipped, 2 warnings**。C0 的可选真实 provider 测试不属于 C2 验收；2026-09-26 重复尝试在 B7m 静态门禁因模型漏写契约 screen ID 失败，保持 C3 稳定性遗留项。
- C2/HTTP：测量计划 InMemory/SQLite 重启恢复、stale impact、HTTP derive/submit/confirm 和 GET projection 均有测试。
- 前端：`npm test -- --run` → **26 passed**；`npm run build` 成功并重新生成 OpenAPI drift 基线。
- 浏览器：`npm run test:e2e` → **2 passed**，包含 C2 Evidence 区的来源层/阈值/确认和 critical/serious axe Gate。

### 结论与遗留项

- C2 验证的是“如何测量”的结构化计划，不是已经发生的测量，也不是现实结果证据；当前仍为 `MeasurementObservation=0`、`EvidenceReview=0`。
- C1 负责真实任务试用与观察记录；C3 负责多次真实 provider 链路稳定性，二者可并行但都不能越过来源和人工审查边界。
- 下一最小工作包：C1 真实任务试用，或 C3 多次真实链路稳定性评估。
