# Iteration：校正 ADR 适用范围

- 日期：2026-09-20
- 状态：Closed
- 类型：Documentation / governance correction
- 触发：用户指出旧 ADR 针对的是既有项目，新 Product Studio 不应默认继承

## 结果

- 删除本轮误建、未纳入版本控制的 ADR 0429–0435 共 7 篇；不修改或删除已有的 430 篇旧 ADR。
- 旧 ADR 仅保留其原领域范围的历史作用；North Star 明确重申的方向以 North Star 为权威来源。
- A1/A2 代码和此前测试结果保留，但字段、确认门、聚合与存储方案降为 `prototype_only` 假设；PS-O002、PS-O003 重新开放。
- A3 明确暂停：`src/psyteardown/api/` 与 `pyproject.toml` 的草稿保留，尚未通过启动/HTTP 集成测试。

## 校正理由

历史 ADR 的 `accepted` 只在其原有体验/工程内核范围内成立。A1/A2 当时编写新 ADR、又将具体原型选择直接标记为 accepted，跳过了 North Star §17 要求在真实切片中逐步回答的问题。自动化测试能够验证当前实现的一致性，却不能证明该架构适合新产品方向。

## 涉及文件

- 更新 `README.md`、`CURRENT_STATE.md`、`ROADMAP.md`、`DECISION_REGISTER.md`、`EVOLUTION_LOG.md`；
- 为 A1/A2 历史 iteration 加范围勘误，给 A3 记录补充已写代码与启动失败事实；
- 将 `architecture/domain-boundaries.md` 从规范性决策改为原型边界视图；
- 删除 7 篇新增 ADR，仅在本记录中保留清理范围，不保留失效链接。

## 验证边界

- 检查结果：7 篇目标 ADR 均不存在；Product Studio 文档的本地相对链接全部可解析，且没有指向被删文件的权威链接。
- 本次校正后执行 `pytest -q`：438 passed、2 skipped、1 个既有 Pydantic warning，用时 26.75 秒；A3 草稿仍无启动/HTTP 测试覆盖。
- 不因本次文档校正宣称 A3 可用；新旧代码未在此次清理中修改或回退。

## 后续

在明确第一条代表性用户问题、复核 A1/A2 假设以及修复 API 依赖兼容性之前，不继续 A3 实施，也不按旧 ADR 编号顺延新平台决策。
