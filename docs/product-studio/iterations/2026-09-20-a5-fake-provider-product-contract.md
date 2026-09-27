# Iteration：A5 Fake Provider Product Contract 闭环

- 日期：2026-09-20
- 关闭日期：2026-09-21
- 状态：Closed
- 路线图工作包：A5
- 类型：Workflow / API / UI / Validation

## 目标

用确定性 fake provider 和持久化 Product Studio Job 走通“已确认 ProductIntent → ProblemModel proposal → 人工确认 → OutcomeContract proposal → 人工确认”，让用户在浏览器中形成首个带 revision、来源、未知和证据边界的 Product Contract。

## 基线

- A1/A2 四对象、命令、revision、SQLite 与 Gate 是 `prototype tested`，尚待真实用户切片校准。
- A3 本地 HTTP command/error/restart matrix 已完成；A4 已验证 ProductIntent onboarding、纠正、冲突恢复、确认和浏览器 Gate。
- 现有 Web 不会生成 ProblemModel/OutcomeContract；对话区明确显示未接入。
- 旧 Experience 域有 JobRecord/提交时 optimistic snapshot 等可复用语义，但 Product Studio 没有独立可恢复 Job 用户能力。
- North Star §11.1/§12 要求耗时工作返回 `job_id`、模型只产生 proposal、每步保存输入 revision/输出/版本并处理 stale input。

## 范围

- Product Studio proposal Job 的最小持久化模型、Repository 与 SQLite schema；
- 确定性 fake provider，只从 confirmed upstream snapshot 生成带 `model_proposal` provenance 的 ProblemModel/OutcomeContract proposal DTO；
- enqueue、单步 claim/run、成功/失败/stale 状态和重启恢复；
- HTTP create/read/run 边界：创建立即返回 `job_id`，运行通过独立 worker-compatible command，不在创建请求中执行 provider；
- 浏览器中发起、推进、刷新 Job，并在生成后转到人工决策；
- ProblemModel 与 OutcomeContract 最小可纠正表单，确认前允许创建新 proposal revision；
- API/UI/SQLite/Playwright 端到端测试覆盖失败、stale 与重启。

## 非目标

- 不调用真实或付费模型，不研究互联网，不生成 ProductThesis；
- 不实现常驻生产 worker、SSE、暂停/预算或分布式 claim；这些在 Phase B 持久化 Job 中扩展；
- 不让 fake provider 产物成为事实或证据；事实数组默认只包含明确的用户陈述来源，解释与未知保持可见；
- 不自动确认 ProblemModel/OutcomeContract，不绕过 Domain Command；
- 不实现产品代码生成、沙箱、预览或部署。

## 验收条件

- Given confirmed ProductIntent，When 创建 problem proposal Job，Then HTTP 返回 persisted queued `job_id`，provider 尚未执行；
- When worker-compatible run command 执行，Then fake provider 产生 ProblemModel proposal，Job 保存 pinned input revision、provider/version、result revision/status；
- When upstream revision 已改变，Then Job 标记 stale，不提交 provider 输出；
- When provider 失败，Then Job 保存安全错误摘要，已确认状态不丢失，允许显式重试或新建 Job；
- When app 关闭重开，Then queued/succeeded/failed/stale Job 与结果 revision 可读取；
- 浏览器可发起/运行生成、查看并纠正 proposal、人工确认，然后以相同方式形成 OutcomeContract；
- 未确认 proposal 不会驱动下一步，fake output 不被标成 research/evidence；
- 完整 API/UI/SQLite/浏览器回归通过，Phase A 文档同步。

## 实施记录

按发生顺序：

1. **Job 领域模型**：在 `product/models.py` 增加 `ProductProposalJob` 不可变快照，字段覆盖 `job_id`、revision 链、`project_id`、`kind`、provider/版本、pinned `input_dependencies`、`result_object_id`、`raw_input`、`fingerprint`、`status`、`attempt`、`result_revision_id` 与 `error_code`/`error_summary`。Job 与四个上位对象一样是 append-only revision，不做原地可变状态机。
2. **确定性 fake provider**：`product/providers.py` 定义 `ProductContractProposalProvider` Protocol 与 `DeterministicFakeProductContractProvider`（`deterministic_fake@a5-v1`）。它只转述已确认上游内容：intent 提案把原句放进 `desired_change`/`current_situation` 并把受影响人群显式标为“需要人工纠正”；problem 提案只产生一条转述用户陈述的 fact、两条 unknown 和两条可证伪的竞争解释；outcome 提案的阈值写成“必须由人设定”，`prohibited_outcomes_reviewed=False`，`required_evidence` 固定为 `real_user_observation`。
3. **Job 服务与 worker 边界**：`product/jobs.py` 的 `ProductProposalJobService` 把 enqueue 与执行拆成两步。`create_job` 校验上游已确认、pin 依赖 revision、算 fingerprint 并持久化 `queued`，不调用 provider；重复请求命中 fingerprint 时复用同一 queued/running/succeeded Job，避免重复点击产生并行提案。`run_job` 单步 claim：先尝试 reconcile 已提交结果（覆盖提交后崩溃），再校验 pinned revision，然后 `running` → provider → 提交前二次校验 → `succeeded`，异常分流为 `stale_input`、`proposal_commit_conflict` 或 `provider_failed`。`retry_job` 只允许从 `failed`/`stale_input` 回到 `queued`，且输入必须仍然当前。
4. **持久化**：`product/sqlite.py` 增加 `product_job_revisions` 与 `product_job_current` 两张表及 project/fingerprint 索引，沿用既有 `CREATE TABLE IF NOT EXISTS` 建表路径，现有 SQLite 文件可直接升级。`InMemoryProductJobRepository` 与 SQLite adapter 共用同一乐观并发校验（首 revision、`expected_revision`、父链、逐 1 递增）。
5. **HTTP 边界**：`api/proposal_jobs.py` 提供 `POST /api/v1/projects/{id}/proposal-jobs`（202 + 已持久化 `job_id`）、`GET .../proposal-jobs`、`GET .../proposal-jobs/{job_id}`、`POST .../{job_id}/runs`、`POST .../{job_id}/retries`。创建请求不执行 provider；`runs` 就是 worker-compatible 的单步执行命令。错误沿用 A3 的统一 envelope 与 request id。
6. **Web 工作流**：`studio/` 的新建项目不再直接写 ProductIntent，而是 create job → run job；`ContractView` 增加提案工作流面板，显示最新 Job 的状态、provider@version 与 attempt，并在 intent/problem 确认后给出“生成问题模型提案 / 生成结果契约提案”。`ContractProposalEditors.tsx` 新增 ProblemModel 与 OutcomeContract 的最小纠正表单（竞争性解释、未知、成功阈值、禁止结果审查勾选），确认前可创建新 proposal revision。
7. **失败可见性**：Job 返回非 `succeeded` 时 UI 显示安全摘要；`stale_input` 显示“输入已变化，结果未提交”，不把失败静默成空白界面。
8. **测试与回归**：补 6 个领域 Job 测试、4 个 HTTP Job 测试、1 个前端表单测试和 1 条端到端浏览器用例，然后跑完整 Python/前端/构建/E2E/依赖回归。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| 领域模型 | 新增 `ProductProposalJob` revision 快照与状态集合 | `src/psyteardown/product/models.py` |
| provider | 新增 Protocol 与确定性 fake provider，输出显式标注 `model_proposal` 来源 | `src/psyteardown/product/providers.py` |
| 应用服务 | 新增 enqueue/单步 run/retry、fingerprint 复用、stale 与失败分流 | `src/psyteardown/product/jobs.py` |
| 持久化 | 新增 `product_job_revisions`/`product_job_current` 与索引 | `src/psyteardown/product/sqlite.py` |
| HTTP | 新增 create/list/get/run/retry 五个端点与 DTO | `src/psyteardown/api/proposal_jobs.py`、`src/psyteardown/api/schemas.py`、`src/psyteardown/api/app.py` |
| Web | onboarding 改走 Job；新增提案工作流面板与 ProblemModel/OutcomeContract 纠正表单 | `studio/src/views/NewProject.tsx`、`studio/src/views/ProjectStudio.tsx`、`studio/src/views/ContractView.tsx`、`studio/src/components/ContractProposalEditors.tsx` |
| 契约类型 | OpenAPI 重新导出并生成前端 transport types | `studio/openapi.json`、`studio/src/api/schema.ts` |
| 测试 | 领域 6、HTTP 4、前端 1、浏览器 1 条新用例 | `tests/product/test_jobs.py`、`tests/api/test_proposal_jobs.py`、`studio/src/components/ContractProposalEditors.test.tsx`、`studio/e2e/product-studio.spec.ts` |

## 决策与偏差

- A5 建立可恢复的最小 Job boundary，而不是把 fake provider 塞进同步 proposal endpoint；这验证 North Star 的异步形态，但不预先实现 Phase B 完整 worker runtime。
- fake provider 输出是 proposal，不是研究结果；其事实只能转述有来源的已确认用户输入，不能凭空生成外部事实。
- 当前 run command 预期由测试/本地开发调用，接口设计为可被未来单 worker 复用；是否在 A5 内增加常驻 worker 取决于实现复杂度和浏览器体验验证。

实施期间发生的偏差：

- **未增加常驻 worker**：`POST .../runs` 作为显式单步命令已足以验证异步形态，浏览器由客户端在创建后立即调用。常驻 worker、SSE 与预算留给 Phase B，因此“生成中”仍是一次前台请求的等待，不是后台进度流。
- **表名与计划不同**：实际建的是 `product_job_revisions` 与 `product_job_current`，而不是计划中的单张 `product_jobs`。原因是 Job 采用与四对象一致的 append-only revision + current pointer 模型，用一张表无法既保留历史又表达当前指针。
- **onboarding 一并改走 Job**：原范围只写了 ProblemModel/OutcomeContract，但把首句自然语言直接写成 ProductIntent 会让“原始输入 → proposal”这一步没有 provenance。因此增加 `product_intent` kind，由 Job 保存 `raw_input` 并产生带 `user_input` + `model_proposal` 双来源的 proposal。这是范围的最小扩大，不是新能力。
- **fingerprint 幂等**：为防止重复点击产生并行提案，`create_job` 对相同 (project, kind, pinned deps, provider, version, raw_input hash) 复用现有 queued/running/succeeded Job。这是实现取舍，不是已确认的长期幂等语义。
- **Phase A 未一次性关闭**：A5 的实施门槛已满足，但 A1/A2 的字段与人工确认门槛仍是 `prototype tested`，按路线图图例不能据此宣布阶段正式完成。详见「遗留项与风险」。

## 验证

2026-09-21 在 Windows 11 / Python 3.12 / Node 本地环境执行，全部为原始工具输出：

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/product tests/api -q` | 49 passed、2 warnings |
| `python -m pytest -q` | 455 passed、2 skipped、2 warnings，22.36s（A3.1 基线为 445 passed） |
| `npm test`（studio） | 5 files、10 passed |
| `npm run build`（studio） | OpenAPI 导出 → `schema.ts` 生成 → `tsc -b` → `vite build` 成功 |
| `npx playwright test`（chromium） | 2 passed，含 axe WCAG A/AA critical/serious Gate |
| `python -m pip check` | No broken requirements found |
| `npm audit` | found 0 vulnerabilities |

验收条件逐条对照：

| 验收条件 | 状态 | 证据 |
|---|---|---|
| 创建返回 persisted queued `job_id`，provider 未执行 | verified | `tests/product/test_jobs.py::test_problem_job_is_persisted_before_provider_runs_and_is_idempotent`、`tests/api/test_proposal_jobs.py::test_jobs_persist_before_run_and_recover_after_restart` |
| run 后保存 pinned input revision、provider/version、result revision/status | verified | 同上；断言 `completed.result_revision_id == problem.revision_id`、`attempt == 1` |
| upstream 变化 → `stale_input` 且不提交输出 | verified | `test_changed_input_marks_queued_job_stale_without_committing_output`、`test_stale_pinned_input_prevents_job_result_commit` |
| provider 失败保存安全摘要、已确认状态不丢失、可重试 | verified | `test_provider_failure_is_safe_and_retryable`（断言 provider 私有细节不进入 `error_summary`） |
| 重开后 queued/succeeded/failed/stale Job 与结果 revision 可读 | verified | `test_failed_sqlite_job_recovers_after_restart_and_can_be_retried`、`test_jobs_persist_before_run_and_recover_after_restart` |
| 浏览器发起/运行生成、纠正 proposal、人工确认，再以同样方式形成 OutcomeContract | verified | `studio/e2e/product-studio.spec.ts::fake provider jobs form a human-confirmed Product Contract` |
| 未确认 proposal 不驱动下一步；fake 输出不被标成 research/evidence | verified | `test_outcome_job_requires_confirmed_problem_and_keeps_human_review_gate`；provider 来源写为 `model_proposal`，`prohibited_outcomes_reviewed=False`，指标要求 `real_user_observation` |
| 完整 API/UI/SQLite/浏览器回归通过，Phase A 文档同步 | verified | 上表全部命令 + 本次台账更新 |

## 数据与迁移

- 实际新增 `product_job_revisions`（append-only 快照）与 `product_job_current`（current 指针）两张表，以及 project 与 fingerprint 索引；既有 `product_revisions`/`product_current`/事件/审计/impact 表未改。
- 建表沿用 `CREATE TABLE IF NOT EXISTS`，已有 SQLite 文件打开即升级，无需手工迁移脚本；旧文件中不存在 Job 行，读取返回空列表。
- Job 只保存结构化、可重放数据：`raw_input` 为用户自己输入的文本，`fingerprint` 为 SHA-256，`error_summary` 为固定安全文案，不写异常堆栈、文件路径或 secret。

## 遗留项与风险

1. 没有常驻 worker：Job 的推进依赖客户端在创建后显式调用 `runs`。如果浏览器在运行中关闭，Job 会停在 `queued`/`running`，需要用户再次点击生成（fingerprint 会复用同一 Job）才会继续；没有后台自动推进，也没有进度流。
2. UI 未暴露 `retries` 与取消：失败后界面只显示安全摘要，用户的恢复路径是再次点击生成并创建新 Job；`POST .../retries` 目前只有 API 与测试覆盖。
3. fake provider 的输出质量不构成产品价值证据：它只能转述已确认输入，unknown 与竞争解释是固定模板。A5 验证的是 proposal/confirm 工作流，不是模型能力。
4. `product_intent` kind 的原始输入直接落库，当前没有长度上限、脱敏或保留策略；接入真实 provider 前需要确定输入保留边界。
5. fingerprint 幂等按 pinned revision 计算，同一上游下只能有一个活跃 Job，用户暂时无法并行生成多个候选提案；是否需要多候选由 Phase B 的 ProductThesis 场景决定。
6. A1/A2 的字段与人工确认门槛仍未经真实用户切片校准（PS-O001/O002/O003），因此 Phase A 的产品决策门槛未关闭。
7. 浏览器覆盖仍限于 Chromium 桌面；Pydantic 字段遮蔽与 FastAPI TestClient/httpx2 的 warning 仍在，未在本批次处理。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（新增 PS-H008 Job 边界假设）
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档（`README.md`、`studio/README.md`、`workstreams/phase-a-foundation.md`）

## 下一最小工作包

A5 的实施门槛已满足，Phase A 的剩余门槛只剩 A1/A2 的产品决策校准。下一最小工作包是 Phase B 的前置 Gate：选定一类具体目标用户与现实问题（PS-O001），用它复核四对象最小字段与人工确认范围（PS-O002/O003），并冻结首条纵向切片的 Outcome Contract。在此之前不扩大 provider 能力、不加常驻 worker、不进入代码生成。
