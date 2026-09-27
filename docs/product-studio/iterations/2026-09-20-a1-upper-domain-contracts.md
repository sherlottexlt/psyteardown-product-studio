# Iteration：A1 上位领域契约与状态转换

- 日期：2026-09-20
- 状态：Closed
- 路线图工作包：A1
- 类型：Domain

> 范围校正（2026-09-20）：下文是当时的实现记录，不代表字段、确认门或旧 ADR 已成为新平台权威决策。误建的四篇新 ADR 已删除；当前代码和测试标记为 `prototype tested`。参见[校正记录](2026-09-20-adr-scope-correction.md)。

## 目标

建立 ProductIntent、ProblemModel、OutcomeContract 和 ProductThesis 的最小不可变领域契约、人工确认/处置状态转换与上游 revision 影响计算，为后续项目应用服务和 API 提供稳定边界。

## 基线

- Product Studio 开发台账 A0 已完成；完整测试为 406 passed、2 skipped、1 warning。
- 现有 experience 内核采用 Pydantic frozen snapshot、`RevisionMeta`、稳定 ID、内容 hash、命令新建 revision 和乐观并发。
- 旧内核 ADR 0095、0096、0202、0203 和 0206 提供既有实现参考，其适用范围不自动延伸到 Product Studio。
- North Star 已定义四对象职责，但字段、状态机和确认门尚未编码。

## 范围

- 四对象的原型假设；当时写出的四篇新 ADR 已在范围校正中撤回；
- 新建独立 `psyteardown.product` 上位产品域包；
- 四个不可变 revision snapshot 及其细粒度值对象；
- proposal → human-confirmed 与 thesis disposition 的纯状态转换；
- amendment 生成新 proposal、保留 stable ID/parent revision、清除旧确认；
- 基于显式 dependency 的直接 revision 影响计算；
- 领域验证和失败路径单元测试。

## 非目标

- 不实现 Repository、SQLite schema、Application Service、API 或 UI；
- 不接入真实 LLM/provider；
- 不选择首条 vertical slice 的具体用户问题；
- 不自动级联改写下游对象，只计算需要后续命令处理的影响。

## 验收条件

- 未确认 proposal 与 confirmed snapshot 在 schema 和状态上可区分；
- 未具名确认不能创建 confirmed ProductIntent、ProblemModel 或 OutcomeContract；
- confirmed ProblemModel 不允许缺少来源事实或竞争解释；
- confirmed OutcomeContract 的目标结果必须绑定有效指标，并显式审查禁止结果；
- ProductThesis 的 selected 状态必须有人工决定或显式授权；
- 修订保持对象 stable ID，revision 单调增加并引用 parent revision；
- 上游 revision 变化只产生显式 impact，不修改或删除历史对象；
- 新旧完整测试通过。

## 实施记录

1. 复核既有 FrozenModel、RevisionMeta、DependencyRef、Repository 和 ADR 0095/0096/0201–0206，确定沿用不可变快照与纯转换语义。
2. 当时曾为四对象编写新 ADR，后来发现确认过早，已在范围校正中撤回；对象边界仍是待验证假设。
3. 新建 `psyteardown.product`，把上位产品域与既有 `experience` 业务对象分包；本批次只复用共享基础类型。
4. 为事实来源、竞争解释、结果指标、资源/停止边界、机制假设、预测、验证策略和 thesis disposition 建立细粒度不可变对象。
5. 实现 confirm、revise、thesis transition 与直接 revision impact 纯函数；所有时间和 revision ID 由调用者注入。
6. 以 18 个测试覆盖冻结语义、来源要求、确认门、竞争解释、指标引用、授权、父 revision、终止状态和无副作用影响计算。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| prototype hypothesis | 四个上位对象的职责和状态假设 | `docs/product-studio/DECISION_REGISTER.md` 的 PS-H001/PS-H002（待复核） |
| domain models | 四个 revision snapshot 及值对象 | `src/psyteardown/product/models.py` |
| transitions | confirm/revise/disposition/impact 纯函数 | `src/psyteardown/product/transitions.py` |
| public API | Product domain exports | `src/psyteardown/product/__init__.py` |
| tests | 领域不变量和转换失败路径 | `tests/product/`，18 passed |

## 决策与偏差

- 四对象目前使用一套实现假设，并非已经接受的领域决策；原先误建的新 ADR 已撤回。
- 通用 `FrozenModel`、`RevisionMeta`、`DependencyRef` 和 `DomainStateError` 暂时复用 experience 模块中的既有定义，避免在本批次同时做共享内核迁移；是否提取到独立 shared kernel 留给 A2 评估。
- `ProductIntent`、`ProblemModel`、`OutcomeContract` 采用简单的 proposed/confirmed 语义；confirmed 后的任何内容修订重新回到 proposed，避免部分字段确认带来的隐式复杂度。
- 上游影响函数只计算直接依赖，不递归传播、不修改对象；A2 由应用服务在事务和事件边界内决定持久化/传播。

## 验证

- 定向命令：`pytest -q tests/product`
- 定向结果：18 passed、1 个既有 warning，用时 0.09 秒。
- 全量命令：`pytest -q`
- 全量结果：424 passed、2 skipped、1 个既有 warning，用时 19.52 秒。
- warning：`ExperienceHypothesis.construct` 遮蔽父类属性；A1 未改动该类。
- 这些测试证明领域 schema 和纯转换满足当前不变量，不证明持久化、API、浏览器体验或真实用户结果。

## 数据与迁移

本批次没有持久化 schema；N/A。

## 遗留项与风险

- 应用命令的原子存储、expected revision 和事件记录属于 A2。
- provider/import boundary DTO 属于 A2/A3，不能直接让 LLM 构造 confirmed snapshot。
- Product domain 当前从 experience models 导入共享基础类型；A2 需评估最小、兼容的 shared-kernel 提取。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`

## 下一最小工作包

A2：项目聚合与应用服务。
