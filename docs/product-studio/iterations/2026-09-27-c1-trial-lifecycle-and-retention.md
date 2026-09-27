# Iteration：C1.3 trial lifecycle and retention enforcement

- 日期：2026-09-27
- 工作包：C1.3
- 状态：Closed
- 基线：`56bc4fc feat: harden Product Studio local workflow`
- 范围：C1 envelope close/stop、Panel 结束 trial、关闭后的写入拒绝、本地 30 天 retention cleanup、SQLite/restart/withdrawal/retention 回归

## 目标

在不启动真实参与者、不改变 C2 `minimum_n=3`、不提升 Outcome Evidence 的前提下，把一次本地 C1 trial 的结束语义和源记录生命周期做成可执行边界：主持人可以明确结束或停止 trial；结束后不能继续 enrollment、presentation 或 observation；关闭时间起 30 天后本地 C1 源记录被清理，同时保留不含参与者内容的 envelope 状态与必要的 retention audit。

## 非目标

- 不启动真实参与者或负责人真实体验验证；
- 不改变 `PSYTEARDOWN_C1_TRIAL_ENABLED=0` 默认暂停；
- 不把同一 participant 的多次 session 计作多个用户；
- 不改变 C2 `minimum_n=3`、`research_observation` evidence ceiling 或 EvidenceReview 规则；
- 不提供 hosted worker、跨备份擦除、身份/权限系统或部署级治理。

## 实现

### Envelope 生命周期

- `C1TrialEnvelope` 增加 `closed_at`、`retention_expires_at` 和 `close_reason`；active envelope 不允许携带关闭时间，closed/stopped envelope 的到期时间必须严格为关闭时间后 30 天。
- Product service 新增 `close_envelope` 与 `stop_envelope`，要求具名 host、非空原因，并通过 repository 原子更新当前 envelope。
- 新增 API：
  - `POST /api/v1/projects/{project_id}/c1/envelopes/{envelope_id}/close`
  - `POST /api/v1/projects/{project_id}/c1/envelopes/{envelope_id}/stop`
- enrollment、presentation、observation 继续使用 active envelope gate；因此关闭/停止后服务端拒绝后续 presentation/observation，而不是只依赖 UI 隐藏控件。

### Panel

- C1 Panel 在 active trial 中展示“结束 trial”和“停止 trial”操作，并要求结束原因。
- 非 active trial 显示关闭/停止时间、retention 到期时间和写入已停止的说明。
- 前端 transport client 与 OpenAPI schema 已同步。

### Retention

- 固定本地策略常量 `C1_RETENTION_DAYS = 30` / `C1_RETENTION_PERIOD`。
- `InMemoryC1Repository` 与 `SQLiteC1Repository` 均实现 `cleanup_c1_retention(now=...)`，删除已到期 envelope 下的 receipt、participant、presentation、observation 和 review 源记录；保留 envelope 生命周期状态与 content-free retention audit。
- Product C1 service 在初始化以及 envelope list/get 前运行清理。这是本地启动/访问触发的确定性 cleanup，不是常驻 worker，也不声称会擦除操作系统、SQLite 备份或外部副本。
- withdrawal 的即时擦除与 tombstone 语义保持不变；retention cleanup 不删除 content-free withdrawal tombstone。

## 验证

- Python：`tests/api/test_c1.py` 覆盖 close/stop 两条 API、关闭后 presentation/observation 409、SQLite restart、withdrawal source erasure，以及推进 30 天后的 retention cleanup；C1 API 7 passed。
- Frontend：C1Panel 覆盖 active trial 必须填写结束原因并调用 close API；前端全量 29 passed。
- 回归：确定性 Python 全量 `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py` 为 561 passed、3 skipped、2 warnings；`npm run build` 成功；Chromium E2E 3 passed。
- 未创建参与者现实结果；本批只增加生命周期/存储行为测试，不提升 Outcome Evidence。

## 遗留项

- C1 仍是本地 host-led 原型；retention cleanup 没有独立后台调度器。
- 关闭后的 review 仍可用于整理已经产生的 observation；关闭只阻止新的 enrollment/presentation/observation，符合本批明确范围。
- 是否开启 `PSYTEARDOWN_C1_TRIAL_ENABLED=1` 以及是否开始负责人 N=1 自试，仍由负责人另行明确决定。
