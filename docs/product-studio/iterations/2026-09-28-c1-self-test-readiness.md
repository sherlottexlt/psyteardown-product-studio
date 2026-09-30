# C1 负责人本地自试前就绪复核

- 日期：2026-09-28
- 工作包：C1（软件就绪复核；不含真实体验验证）
- 状态：Closed
- 关联：[`C1 主链路收敛与模型生成韧性补强`](2026-09-27-c1-mainline-and-model-resilience.md)、[`C1 观察接入`](2026-09-26-c1-outcome-observation-intake.md)

## 目标与边界

复核所有可由工程实现和自动化验证的负责人本地自试前置项。此批不代替负责人作出启动决定，不访问/改写用户现有 Product Studio 项目数据，不启用试用开关，不调用真实 provider，也不进行真实自试；自动化测试仅使用隔离测试存储/fixture，不构成现实参与者记录或观察。

## 就绪结论

**软件侧前置已验证；未发现需要先于负责人真实自试完成的剩余代码任务。** 当前 C1 仍是 Active，因为真实观察与后续人工 review 尚未发生。

已检查的边界：

- 默认 trial 状态为 paused；服务端在开关关闭时拒绝创建 envelope，前端显示暂停状态。
- 启动 envelope 需要 confirmed C2 plan、current Web contract、成功且 provenance 匹配的 B6 delivery/execution pin。
- C1 Panel 展示 `c1-local-v1` policy statement、访问策略和 retention 说明；enrollment 另要求主持人确认已向参与者展示说明并取得授权。
- 观察只收结构化 measure/task 状态/人工时间；撤回、close/stop、30 天本地 retention cleanup 和非成功路径门禁已有代码及确定性回归。
- 不要求独立非参与者演练；N=1 可有多个 session，但仍是一个 participant，不满足 C2 `minimum_n=3`。reviewer 不必先于观察采集完成指定；没有与 host 分离的具名 reviewer 时不得提升 EvidenceReview 等级，观察保持未 review。

## 验证

- `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py`：561 passed、3 skipped、2 warnings（既有 Pydantic 字段遮蔽与 Starlette/httpx deprecation）。
- `npm test -- --run`：29 passed。
- `npm run build`：成功；OpenAPI 和生成 transport types 无待提交 drift。
- `npm run test:e2e`：Chromium 3 passed；覆盖 Product Contract/C2 flow、缺少 B6 时 C1 面板禁用、工作区恢复与 axe。E2E 不等于真实 C1 任务观察。

## 负责人启动前仍需亲自确认

这些是运行/治理决定，不是可由代码代理代做的工程任务：

1. 选择实际要测的项目，并确认其 C2 plan 已确认且仍是当前 revision，Web contract 当前，B6 delivery 成功且 execution/contract provenance 与该项目一致。
2. 在 C1 Panel 阅读将实际展示的 `c1-local-v1` 同意说明、访问者范围、30 天保留/撤回边界及外部备份不承诺物理擦除的说明；确认其适合本次仅涉及自己的自试。
3. 只有明确决定启动后，才在运行 API 的进程环境设置 `PSYTEARDOWN_C1_TRIAL_ENABLED=1` 并启动本地 trial。该复核没有设置此变量，也没有启动服务性试用。
4. 记录仍按 `participant_n=1, session_k>=1` 理解；不得将重复 session 当作多个用户或泛化效果。

独立具名 reviewer 是后续 EvidenceReview 等级提升的必要条件，不是本地 N=1 观察采集的启动 Gate。
