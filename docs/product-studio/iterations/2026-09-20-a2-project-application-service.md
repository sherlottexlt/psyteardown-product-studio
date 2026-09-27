# Iteration：A2 项目聚合与应用服务

- 日期：2026-09-20
- 状态：Closed
- 路线图工作包：A2
- 类型：Domain / Persistence

> 范围校正（2026-09-20）：本记录只证明 A2 原型的代码和测试行为，不批准独立聚合、`product_*` 存储或旧内核 ADR 对新平台的适用性。原先误建的两篇新 ADR 已删除；参见[校正记录](2026-09-20-adr-scope-correction.md)。

## 目标

让四个上位对象通过同一个 Product Application Service 被创建、修订、确认和处置，并在 InMemory 与 SQLite 中以原子命令保存 revision、current pointer、事件、审计和依赖影响；重启后可恢复同一项目的完整只读视图。

## 基线

- A1 已实现四对象不可变 snapshot、纯状态转换和直接 impact 计算；完整测试 424 passed、2 skipped。
- 现有 experience 内核已有可借鉴的 InMemory/SQLite revision repository，但表名、模型注册和应用服务属于下位 bounded context。
- 旧内核 ADR 0097、0201–0205 记录了可参考的事件/审计、双 adapter、ID/时钟和事务方案，但不是新域的自动实施约束。

## 范围

- 最小 ProductProject 生命周期对象与项目只读组合视图；
- 明确的 proposal/confirm/disposition Command DTO；
- 注入式 Clock 与 ID factory 的 ProductApplicationService；
- 对上游 revision、项目归属、confirmed gate 和 `expected_revision` 的应用层校验；
- 行为一致的 InMemoryProductRepository 与 SQLiteProductRepository；
- 原子保存 revision、current、Domain Event、Audit Event 和 RevisionImpact；
- 重启恢复、并发冲突、事务回滚、事件边界与项目 projection 测试。

## 非目标

- 不实现 FastAPI、React、LLM/provider 或持久化 Job；
- 不自动生成 DesignBrief 或调用 experience Coordinator；
- 不递归自动重写 stale 下游对象；
- 不实现多人身份、RBAC 或租户隔离。

## 验收条件

- 新项目与四类对象都只能通过 Application Service/Command 改变状态；
- 修改已有聚合必须给出正确 `expected_revision`，冲突不会产生 revision 或事件；
- ProblemModel 只能引用同项目 confirmed ProductIntent，后续对象同理固定 confirmed upstream revisions；
- 一个命令的 revision、current、events、audit 和 impacts 在 SQLite 中全成或全败；
- InMemory 与 SQLite 对相同命令序列给出等价项目视图；
- SQLite 关闭重开后 revision chain、current pointers、events 和 impacts 均可恢复；
- 完整测试通过，项目台账同步。

## 实施记录

1. 原型选择 ProductProject 只拥有身份和生命周期，四对象保持独立聚合和并发 revision；原先误建的正式 ADR 已撤回。
2. 新增边界 Command DTO；provider/API 后续只能提交 proposal，不能直接构造 confirmed snapshot。
3. ProductApplicationService 注入 UTC Clock 与 ID factory，验证项目归属、active 状态、confirmed upstream、chain coherence 和 expected revision。
4. 实现 InMemoryProductRepository，所有冲突/重复检查在内存变更前完成。
5. 新增独立 `product_*` SQLite schema，使用 `BEGIN IMMEDIATE` 在事务内重查 current revision；revision、pointer、events、audit 和 impacts 全成或全败。
6. 用同一 parametrized 测试覆盖两种 adapter，并增加暂停/恢复、错误 gate、冲突无副作用、事务回滚、注入式 ID/时钟和 SQLite 重启恢复。
7. 新增领域边界文档，明确未来 ProductThesis → DesignBrief 必须经过显式 realization adapter。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| project model | ProductProject lifecycle 与 ProductProjectView | `src/psyteardown/product/models.py` |
| command boundary | create/status/proposal/confirm/disposition DTO | `src/psyteardown/product/commands.py` |
| application | 项目与上游 Gate、命令协调、事件/impact 构建 | `src/psyteardown/product/service.py` |
| in-memory persistence | atomic revision/current/event/audit/impact adapter | `src/psyteardown/product/repositories.py` |
| SQLite persistence | 独立 `product_*` schema、事务与恢复 | `src/psyteardown/product/sqlite.py` |
| architecture | 上位域与既有 experience/engineering 内核映射 | `docs/product-studio/architecture/domain-boundaries.md` |
| tests | 双 adapter、冲突、回滚、重启和项目 projection | `tests/product/test_service.py`，14 个新增测试 |

## 决策与偏差

- 暂定假设 PS-H003：ProductProject 是协调边界，而不是全项目大聚合；待首条用户切片验证。
- 暂定假设 PS-H004：使用独立 `product_*` 表，命令内同时保存影响事实；待跨域集成验证。
- ProductProjectView 组合 current pointers 和历史 impact，只读且不回存。
- A2 不加入 outbox：当前命令尚未触发异步副作用；将来 Job 的事务边界须结合新平台需求单独决定，旧 ADR 0205 仅供参考。
- 跨域 realization 只记录接口方向，不在 A2 自动生成或冻结 DesignBrief。

## 验证

- 定向命令：`pytest -q tests/product`
- 定向结果：32 passed、1 个既有 warning，用时 1.31 秒。
- 全量命令：`pytest -q`
- 全量结果：438 passed、2 skipped、1 个既有 warning，用时 22.29 秒。
- warning：`ExperienceHypothesis.construct` 遮蔽父类属性；A2 未改动该类。
- 测试证明领域/应用/本地持久化契约，不证明 HTTP、浏览器体验、真实 provider 或用户结果。

## 数据与迁移

- 只新增 `product_*` 表，不修改已有 `experience_*` 或旧 pipeline 表。
- 当前没有已发布 Product 数据，因此不需要历史数据迁移。

## 遗留项与风险

- API boundary DTO 和 OpenAPI 错误映射属于 A3。
- ProductThesis 到 DesignBrief 的正式 realization adapter 在 A2 只保留显式边界，不自动映射。
- 通用 frozen/revision/event 基础类型仍从 experience 模块复用；更多 bounded context 出现时再做兼容迁移。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`

## 下一最小工作包

A3：FastAPI `/api/v1` 壳。
