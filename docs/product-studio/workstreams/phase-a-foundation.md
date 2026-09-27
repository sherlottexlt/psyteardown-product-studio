# Phase A 工作流：上位模型和产品壳

- 状态：Closed（A3/A4/A5/A6 已完成；真实结果验证仍属于 Phase C）
- 开始日期：2026-09-20
- 对应路线图：[`ROADMAP.md`](../ROADMAP.md#phase-a上位模型和产品壳)
- 上位规格：[`North Star §9、§11、§13、§14`](../../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md)

## 目标

建立 Product Studio 的最小可信骨架，使用户能从一条不完整意图开始，在浏览器中查看并纠正结构化理解，经明确确认形成带 revision 的 Product Contract；新能力必须复用现有研发内核，且不把聊天或模型输出当作权威状态。

## 非目标

- 本阶段不生成最终 Web 产品；
- 不执行不受控代码或接入真实部署；
- 不引入多人租户、企业 RBAC、PostgreSQL、Temporal 或插件市场；
- 不扩展硬件 realization pack；
- 不宣称任何真实用户结果。

## 工作包依赖

```text
A0 项目台账（done）
  ↓
A1 上位领域契约（首条切片已校准；不代表所有 realization pack 的最终 schema）
  ↓
A2 项目聚合与应用服务（首条切片已校准；跨域长期边界仍待后续验证）
  ↓
A3 FastAPI API（done；完整 HTTP/restart matrix） ───────┐
  ↓                  │
A4 React Studio 壳（done；Product Contract 闭环已验证）  │
  └──────────────┬───┘
                 ↓
      A5 薄纵向集成（done；fake provider + 持久化提案 Job）
                 ↓
      A6 首条切片校准（done；Phase A 出口）
```

## A1 设计检查表

A6 以“自主管理工作的知识工作者，在桌面浏览器中保护 25–60 分钟专注时段，同时保留紧急联系控制”的首条切片完成了字段与人工 Gate 校准，详见 [`iterations/2026-09-21-a6-first-slice-calibration.md`](../iterations/2026-09-21-a6-first-slice-calibration.md)。

四个对象都必须回答：

1. 它拥有而相邻对象不拥有的事实是什么；
2. 哪些字段来自用户陈述、外部证据、AI 推断或人类决定；
3. proposal 如何产生、如何被确认、纠正、替代和拒绝；
4. revision 身份、父 revision、内容 hash 和时间如何记录；
5. 哪些变化会使哪些下游对象 stale，而不是直接删除；
6. 什么条件下对象仍是 draft、可以 confirmed、必须 blocked 或需要重新建模；
7. API DTO 与领域快照怎样分离；
8. 如何在没有真实模型调用的情况下确定性测试。

建议的对象职责边界，当前仅作为设计起点而非已接受 schema：

| 对象 | 负责表达 | 不应负责 |
|---|---|---|
| ProductIntent | 用户想改变的现实、受影响者、价值、明确拒绝项和资源倾向 | 问题成因、具体解决方案或验证结论 |
| ProblemModel | 事实、假设、未知、竞争解释和利益相关方张力 | 将某个产品路径写成既定答案 |
| OutcomeContract | 目标结果、指标、禁止结果、资源边界、停止条件和最低交付成熟度 | 具体界面、技术栈或实现任务 |
| ProductThesis | 机制假设、实现模式、可证伪预测、验证策略和维护代价 | 冒充已验证结果或直接批准发布 |

## A2–A5 当前边界（已按首条切片校准）

以下写/读/存储组织方式部分来自旧内核经验，不因旧 ADR 标为 accepted 就自动成为新平台正式架构。

- 写路径：HTTP/CLI/MCP adapter → application command → domain transition → repository transaction → event/outbox。
- 读路径：可使用页面导向 projection，但 projection 不能写领域状态。
- 并发：所有会改变已存在聚合的命令携带 `expected_revision`。
- 模型：provider 只产生带 provenance 的 proposal DTO；确认命令创建不可变领域 revision。
- 存储：先提供内存适配器做领域测试，再提供 SQLite 适配器；不让 ORM 模型成为领域模型。
- 前端：所有区域共享明确的 project/revision 上下文；stale、unknown、unverified 和 conflict 必须可见。
- 集成：Phase A 使用 fake provider 和结构化文本，避免测试依赖网络、费用或采样波动。

## A3/A4/A5 当前实现事实

- FastAPI app factory、SQLite lifespan、`/api/v1` routes、稳定错误 envelope 与 localhost 开发边界可运行，完整四对象 HTTP command/gate/conflict/restart 矩阵已通过。
- `studio/` SPA 通过 API 创建项目、创建并运行提案 Job、读取 ProductProjectView，并调用既有 confirm/transition commands；浏览器不直接写 Repository 或复制领域状态转换。
- 五个工作区共享同一 query 中的项目 projection；未确认、未知、revision impact 和“尚未接入”能力具有不同呈现。
- TypeScript transport 类型由 FastAPI OpenAPI 生成，并有后端 drift test 锁定。
- Product Contract 的三个对象都可以查看、纠正并具名确认；自然语言到 proposal 由持久化 Job 加确定性 fake provider 完成，创建请求不执行 provider。
- Job 是 append-only revision：pin 上游 revision，执行前后校验，失败分流为 `stale_input`/`provider_failed`/`proposal_commit_conflict`，重启后可读取与重试；没有常驻 worker、进度流、暂停与预算。

## Phase A 验收场景

```text
Given 一个尚无 Product Contract 的新项目
When 用户提交一条不完整目标
Then 系统保存原始输入并产生 ProductIntent proposal

When 用户纠正并确认关键价值边界
Then 系统通过 Domain Command 创建新的不可变 revision
And 保留 proposal、确认者、时间和来源

When ProblemModel 或 OutcomeContract 的上游事实改变
Then 受影响 ProductThesis/DesignBrief 被标为需要复核或 stale
And 历史 revision 仍可读取

When 两个客户端基于同一旧 revision 写入
Then 后提交者得到显式冲突
And 系统不自动合并价值判断

When 用户打开 Web Studio
Then 对话、产品契约、工作台、决策和证据区域共享同一项目 revision
And 未确认 proposal 与已确认事实具有不同呈现
```

## 风险与提前验证

| 风险 | 最小验证 |
|---|---|
| 四对象边界过细，用户流程被内部模型绑架 | 先用一个端到端 Product Contract projection 驱动 schema |
| 新 revision 系统与旧内核并行 | A1/A2 先验证原型中的 ID/clock/hash/command 行为，再核对旧内核跨域接入是否必要 |
| API DTO 泄漏领域内部复杂度 | 用页面读模型和命令 DTO 契约测试隔离 |
| 前后端同时扩张导致无可运行切片 | 每个工作包保持 fake provider 下可运行，A5 只走一条 happy path 加关键失败路径 |
| 切片过早扩展成通用架构 | 先保持本记录的单人 Web 范围；新用户类型、组织协作或 realization pack 出现时重新打开 PS-O002/O003 |

## 完成定义

Phase A 在以下条件同时满足后关闭（2026-09-21）：

- A1–A5 的验收条件均有代码和测试证据；
- 浏览器中可以完成“模糊输入 → proposal → 人工纠正/确认 → Product Contract revision”；
- 关闭/重启后已确认状态仍可恢复；
- revision 冲突、provider 失败、无效 proposal 和 stale input 有显式错误路径；
- README、API schema、当前状态、路线图、决策登记与演变日志同步；
- 未引入 Phase A 非目标，也没有提高未经现实验证的声明；
- A1/A2 的最小字段与人工确认范围已用首条具体目标用户/现实问题切片校准（A6 已完成）；该校准不构成真实用户结果证据，后续真实任务试用仍受 Phase C 约束。
