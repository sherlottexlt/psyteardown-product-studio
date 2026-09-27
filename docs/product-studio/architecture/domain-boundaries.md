# Product Studio 领域边界与集成方向

- 状态：Prototype view；非正式架构决策
- 最近更新：2026-09-26（C2 measurement plan；C1 bridge remains undecided）
- 依据：[North Star 上位模型和既有内核关系](../../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md)；细化实现待首条切片验证

## 当前边界

```text
Web / API / CLI / MCP adapters
                ↓ commands / queries
psyteardown.product
  ├─ ProductProject lifecycle
  ├─ ProductIntent
  ├─ ProblemModel
  ├─ OutcomeContract
  ├─ OutcomeMeasurementPlan (C2; plan only)
  ├─ ProductThesis
  ├─ ProductApplicationService
  └─ product_* revision/event/impact store
                ↓ future explicit realization adapter
psyteardown.experience
  ├─ Discovery / Evidence / Observation / ExperienceHypothesis
  ├─ DesignBrief / Candidate / Review / Experiment
  ├─ Engineering / Quality / Release gates
  └─ experience_* revision/event/outbox store
```

`product` 回答“为什么做、要改变什么结果、有哪些产品路径”；`experience` 回答“某条路径怎样被设计、评审、工程化和验证”。目前代码采用独立表、Repository 和 Application Service；这是 A2 原型的实现事实，不是既定的跨域集成决策。

## 对象映射

| Product 上位对象 | 既有内核关系 | 当前 A2 行为 | 后续集成要求 |
|---|---|---|---|
| ProductIntent | 是整个项目的用户价值与拒绝项边界 | 不直接生成下位对象 | realization 命令必须携带 confirmed intent revision |
| ProblemModel | 可引用 Discovery、Evidence、Observation 的来源，但不等于其中任何一个 | 只保存来源指针与竞争解释 | 导入既有研究时保留原 revision/provenance，不复制成无来源事实 |
| OutcomeContract | 位于 DesignBrief 之前 | 固定指标、禁止结果、资源与停止条件 | DesignBrief adapter 只能细化，不能静默弱化 hard boundary |
| OutcomeMeasurementPlan | C2 pin 一条已确认 OutcomeContract revision，声明 measure/source layer/ceiling/guardrail/sample/consent prose | 独立 Product aggregate；不是 Observation、Consent receipt 或 EvidenceReview | C1 bridge 尚未决定；Observation 必须 typed-pin plan + B6 delivery + actual consent revision，且只能由人工 EvidenceReview 审查 |
| ProductThesis | 一条可证伪 realization path | 保存机制、预测、验证和处置状态 | 只有 selected 或在授权范围内 exploring 的 revision 可以请求 DesignBrief proposal |
| ProductProjectView | 面向 UI 的 current projection | 组合独立 current pointers 与历史 impact | 只读；不得作为写模型回存 |

## 待验证的跨域接入假设

1. Adapter 只能构造 Command DTO，不能直接调用 Repository。
2. ProductApplicationService 是上位域唯一写边界；ExperienceApplicationService/Coordinator 是下位域写边界。
3. 跨域动作未来使用显式 realization command：固定 ProductThesis、OutcomeContract、ProblemModel 和 ProductIntent revision，再生成 `DesignBrief` proposal。
4. 生成的 DesignBrief 在人工冻结前仍是 proposal；选中 ProductThesis 不等于批准 DesignBrief。
5. 下位验证结果通过带 provenance 的新命令回流，不反向修改历史 ProductThesis 或 OutcomeContract。
6. 上游修订产生 impact/event；应用服务决定何时把跨域对象标为 review required/stale，不做数据库级隐式级联。

## A2–A4 原型已实现并测试

- 项目与四对象独立 stable ID/revision chain；
- 同项目、confirmed upstream 和 expected revision Gate；
- 原子 revision/current/event/audit/impact 写入；
- InMemory 与 SQLite 双 adapter；
- SQLite 重启恢复的 ProductProjectView。
- FastAPI command/projection adapter、统一错误 envelope、localhost 边界和最小 HTTP/SQLite 往返；
- React Product Studio 通过 API 使用 ProductProjectView，不从浏览器直接写领域存储；
- 五区 UI 共享一个项目 projection，并显式展示 proposal、unknown、impact 和未实现边界。

## 尚未实现

- ProductThesis → DesignBrief realization command/adapter；
- C2 OutcomeMeasurementPlan → Experience OutcomeObservation 的 C1 adapter；participant consent receipt、withdrawal/erasure、source ceiling review gate 尚待 PS-O022/O023/O024；
- Experience/Evidence 到 ProblemModel 的正式 provenance import；
- 跨域 stale 传播 worker/outbox；
- 完整 HTTP command/gate/restart 测试矩阵、OpenAPI 生成客户端类型；
- 身份、权限和跨项目访问控制；
- 已存在 Product Contract proposal 的浏览器纠正流程。

这些缺口不能被解释为 Product Studio 已经与既有内核走通；A2 仅探索了一种接入位置。以上写入和适配方式仍需在真实用户情境中校准，不能直接视为后续项目的强制规范。
