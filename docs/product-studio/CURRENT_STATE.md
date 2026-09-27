# Product Studio 当前状态

- 快照日期：2026-09-27
- 当前阶段：Phase B 已关闭；Phase C in progress（C0/C2/C3 已完成；C1 Product-side backend/API、主持面板和主链路引导已实现，尚未招募/收集真实参与者；B4 诊断边界已记录）
- 当前工作包：C1 Active，真实参与者/负责人真实体验验证继续暂缓；C1.3 trial lifecycle、close/stop API、Panel 结束操作、关闭后 presentation/observation 拒绝和本地 30 天 retention cleanup 已落地；C1 API/UI 暂停门禁、reviewer 占位拒绝和中断 Execution Job 恢复已落地，主链路恢复 Gate 已通过；当前保持真实试用开关关闭，不设独立的非参与者演练 Gate；C3 R4 已完成 10/10，本批稳定性 Gate 已通过；R1/R2/R3 失败样本与 B4 安全诊断边界仍保留，均不等于生产级稳定性保证
- 下一步：C1 真实体验验证继续暂缓；C1.3 lifecycle/retention 回归已通过。下一步不是自动启动试用，而是由负责人明确决定是否通过 `PSYTEARDOWN_C1_TRIAL_ENABLED=1` 按 `c1-local-v1` 启动自我试用；这替代强制的非参与者演练。先把结果按 `participant_n=1, session_k>=1` 标为本地探索性自试：你可以做多次真实任务/多次 presentation，但不能把同一个人计作多个用户，也不能把它当作当前 C2 计划的 `minimum_n=3` participant gate。多次 session 可用于观察重复性、学习效应和疲劳效应；保留显式同意、30 天保留/撤回边界，任何 EvidenceReview 等级提升仍须由与 host 分离的具名 reviewer 完成。
- 最近完整验证：2026-09-27 C1.3 lifecycle/retention 完成后的确定性回归 `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py` 561 passed、3 skipped、2 warnings；`npm test -- --run` 29 passed（含 C1Panel 结束 trial）；`npm run build` 成功；Chromium E2E 3 passed（含 Product Contract、Evidence/C2 来源层、阈值、确认、C1 panel 启动 Gate、工作区恢复和 axe Gate）；OpenAPI drift 已重新生成。C0 于 2026-09-25 完成过一次真实 DeepSeek Product Contract → B7m source=model → B4 本地 subprocess/Chromium → B6 交付包链路，5 次模型调用，5,788 input / 7,824 output tokens，总耗时 100.22 秒；2026-09-26 的一次重复尝试在 B7m 静态门禁因模型漏写契约 screen ID 而失败，需由 C3 评估稳定性。 C3 于 2026-09-26 完成 R1/R2/R3 诊断，并完成 R4 有界复测：首轮 10 次中 7 次完整成功；第二轮 10 次中 8 次完整成功，2 次 B4 `command_failed` 未恢复；R3 完成 6 次后安全停止，其中 1 次 `browser_command_failed`、1 次 `run_timeout`；R4 10/10 完整通过，50 次模型调用，57,724 input / 83,183 output tokens。R2 总 52 次模型调用，58,850 input / 86,279 output tokens，总耗时 746.48 秒；R3 总 25 次调用，28,430 input / 41,806 output tokens，记录耗时 725.40 秒。R4 汇总金额保持 unavailable，不作推断。

## 一句话状态

Phase B 已关闭。仓库已经具备从模糊意图到可运行 Web 产品、自动测试/修复、反馈和导出的完整闭环，且该闭环可演示、可恢复。用户可以在浏览器里从一句不完整的话开始，经持久化 proposal Job 依次得到 ProductIntent、ProblemModel、OutcomeContract 提案，逐个纠正并具名确认，形成带 revision、来源、未知和证据边界的 Product Contract；可以在确认的 Outcome Contract 上生成并比较三条机制/实现/验证路径不同的 ProductThesis；可以选择一个 thesis 并生成 WebProductGenerationContract；可以在受限 workspace 中生成 React/TypeScript/Vite SPA 源码（确定性模板或真实模型）；可以在本地 subprocess 中构建、loopback 预览并运行 Playwright/axe 检查；失败的执行可以触发独立 Repair Job，只读取安全摘要并使用确定性白名单补丁在新的 generation lineage 中重试；成功的执行可以导出为内容寻址、字节确定的 zip 交付包（源码、构建物、验证产物、交付说明与未验证声明）；用户可以在沙箱 iframe 中预览产品，提交显式、逐次同意、可撤回的反馈，锚定到交付包/执行/契约 revision 与页面/任务/状态；一条反馈可以驱动同一契约的下一 proposed revision，经人确认后重走生成、验证与导出，并提供版本差异比较。C2 现在可从已确认 Outcome Contract 派生并确认一份带 revision 的测量计划，显示服务端派生的来源层证据上限/可收集性、guardrail、停止条件、样本和同意/撤回边界；这份计划不等于观察或现实结果。C0 已在 2026-09-25 验证一次真实 DeepSeek Product Contract → B7m source=model → B4 本地 subprocess/Chromium → B6 交付包链路；token 与耗时已记录。仍未解决的是金额预算、部署级 OS/container 隔离、视觉回归/跨浏览器验证和真实用户结果；本批另外补强了本地恢复与运行控制，并用 Chromium E2E 验证了 queued proposal 的恢复；但 R4 仍只证明固定环境下的 10 次评估通过。

## 已验证的软件基线

| 能力区域 | 当前事实 | 证据位置 | 状态 |
|---|---|---|---|
| 拆解与知识内核 | 具备心理框架、五步流水线、grounding、记忆、策略与自评模块 | `src/psyteardown/{kb,pipeline,memory,growth,strategy,review}` 与对应测试 | verified |
| 体验与证据内核 | 具备 Evidence、Observation、ExperienceHypothesis、设计候选、实验与反馈模型 | `src/psyteardown/experience/` 与 `tests/experience/` | verified |
| revision 与依赖传播 | 具备 SQLite 持久化、revision、依赖图以及 stale/invalidation 语义 | experience repositories/sqlite/service 与测试 | verified |
| 工程与质量边界 | 具备工程对象、工具请求/结果分离、质量和发布 Gate；没有真实工具结果就不会提升声明 | experience engineering/quality/tool modules 与测试 | verified |
| 自动化入口 | CLI 与 MCP 共享现有应用/编排能力；MCP 主要用于读取和草稿 | `src/psyteardown/cli.py`、`src/psyteardown/mcp_server/` | verified |
| Product Studio 上位领域 | 四对象不可变 revision、人工确认/授权门和直接 revision 影响计算；B2 增加可追溯 WebProductGenerationContract | `src/psyteardown/product/`、`tests/product/test_a6_first_slice.py`、`tests/product/test_jobs.py` | verified for first slice / B2 |
| Product 项目应用层 | 独立聚合、命令、expected revision、事件/审计/impact、双 adapter 和重启恢复；A6 已确认适合首条切片 | `src/psyteardown/product/{commands,service,repositories,sqlite}.py`、`tests/product/test_a6_first_slice.py` | verified for first slice |
| A3 HTTP 原型 | 四对象 command chain、统一错误、Gate/conflict/validation 脱敏、OpenAPI、localhost 边界和 SQLite lifespan/restart 均从 HTTP 验证 | `src/psyteardown/api/`、`tests/api/`、`pyproject.toml` | verified in local Phase A scope |
| A4/B1/B2 Web 工作空间原型 | 五区壳、Product Contract 纠正/确认、B1 thesis 比较/授权、B2 Web generation contract 生成/确认、冲突保草稿恢复、生成 API 类型、键盘与 axe 浏览器 Gate | `studio/src/`、`studio/e2e/`、`studio/openapi.json` | Product Contract + B1/B2 contract workflow verified；离线草稿仍未做 |
| A5/B1/B2 提案 Job 与 fake provider | 持久化 proposal Job（enqueue/单步 run/retry、pinned revision、fingerprint 幂等、stale/失败分流、重启恢复）；B1 三结果 thesis batch；B2 Web generation contract 单结果 Job | `src/psyteardown/product/{jobs,providers,sqlite}.py`、`src/psyteardown/api/proposal_jobs.py`、`tests/product/test_jobs.py`、`tests/api/test_proposal_jobs.py` | verified in local B2 scope |
| B3 Web 生成 workspace | 确认契约触发独立、幂等、可恢复的 Generation Job；固定模板写入项目/Job workspace，manifest 记录文件 hash/大小，默认无网络、无 Secret、不执行源码并受文件/字节/时间/尝试预算约束 | `src/psyteardown/product/{generation,models,sqlite}.py`、`src/psyteardown/api/generation_jobs.py`、`tests/product/test_generation.py`、`tests/api/test_generation_jobs.py` | verified in local B3 scope |
| B4 Web 执行 sandbox | 独立 Execution Job pin 成功 generation revision；复核 manifest/package allowlist，按 install/build/loopback preview/Playwright/axe/截图顺序执行，保存步骤与安全错误摘要 | `src/psyteardown/product/execution.py`、`src/psyteardown/api/execution_jobs.py`、`tests/product/test_execution.py`、`docs/product-studio/iterations/2026-09-22-b4-isolated-execution.md` | verified in local runner scope; no container isolation |
| B5 受限失败定位与修复 | 独立 Repair Job pin 失败的 B4 revision，只消费步骤/错误安全摘要；确定性白名单补丁写入新的 repair workspace，创建 child generation lineage 和新的 Execution Job，保存尝试、补丁、成本并保持原 revision 不变 | `src/psyteardown/product/repair.py`、`src/psyteardown/api/repair_jobs.py`、`tests/product/test_repair.py`、`studio/src/views/{ProjectStudio,WorkbenchView}.tsx`、`docs/product-studio/iterations/2026-09-22-b5-bounded-repair-loop.md` | verified in local deterministic-repair scope; no real model or deployment isolation |
| B6 交付包导出 | 不可变 `ProductDeliveryBundle` pin 成功执行 revision；复核源码 manifest、`dist/index.html`、凭据/符号链接和 256 文件/8 MiB 预算；确定性 zip 以 sha256 寻址，下载前复核；`outcome_evidence_level` 固定为 `none` | `src/psyteardown/product/delivery.py`、`src/psyteardown/api/delivery_bundles.py`、`tests/product/test_delivery.py`、`tests/api/test_delivery_bundles.py`、`docs/product-studio/iterations/2026-09-23-b6-delivery-bundle.md` | verified in local scope, including one real npm/Chromium run |
| B7 预览与显式反馈 | 从 hash 复核的 B6 archive 只读提供 `build/` 文件（CSP `sandbox allow-scripts`、`connect-src 'none'`）；`PreviewFeedback` 锚定 bundle/execution/contract revision + screen/task/state，需当前同意版本，提交者可撤回为 r2 墓碑，SQLite `secure_delete` 保证正文不留在文件中；证据等级 `user_report` | `src/psyteardown/product/feedback.py`、`src/psyteardown/api/preview_feedback.py`、`tests/product/test_feedback.py`、`tests/api/test_preview_feedback.py`、`studio/src/views/PreviewFeedbackPanel.tsx`、`docs/product-studio/iterations/2026-09-23-b7-preview-feedback-anchors.md` | verified in local scope, including one real npm/Chromium run |
| C0/B7m 真实模型链路 | Product Contract 的 DeepSeek Intent/Problem/Outcome/Thesis + B7m source=model；真实 B4/B6 链路成功；项目 `.env.local` 优先读取、JSON mode、token/耗时报告 | `src/psyteardown/product/{env,contract_model,providers,source_model}.py`、`tests/product/test_c0_real_provider_e2e.py`、C0 iteration | verified；一次真实链路；C3 R4 固定环境评估 10/10 通过（不等于生产级稳定性保证） |
| B7m 真实模型源码生成 | B3 可选 `source=model`：DeepSeek 只接收已确认 Web generation contract，只写 `src/App.tsx`/`src/styles.css`；静态门禁、契约派生浏览器测试、每 Job ≤2 次调用、transcript 仅本机；一次真实 DeepSeek→B4→B6 链路成功 | `src/psyteardown/product/source_model.py`、`tests/product/test_source_model.py`、`tests/api/test_source_model_api.py`、`docs/product-studio/iterations/2026-09-23-b7m-model-source-generation.md` | verified in local scope, one real provider run |
| B8 反馈驱动迭代 | 一条 submitted 反馈可驱动同一 Web 契约的下一 proposed revision（ID 不变、只追加引用反馈 ID/类别的验收检查、不复制正文）；撤回使迭代 Job stale；人工确认后重走 B3→B4→B6；交付包 sha256/契约集合差异；反馈处理状态由人标记 | `src/psyteardown/product/{jobs,providers,feedback,delivery}.py`、`tests/api/test_feedback_iteration.py`、`studio/src/views/{PreviewFeedbackPanel,WorkbenchView}.tsx` | verified in local scope；模板路径下产品不变 |
| C2 Outcome Contract 测量计划 | 从已确认 Outcome Contract 确定性派生带 revision 的测量计划；每条指标有 measure；固定来源层、证据上限、可收集性、阈值、缺失处理、矛盾回退；禁止结果 guardrail、停止条件、样本/同意/撤回边界均可审查；Outcome Contract 修订记录 stale impact | `src/psyteardown/product/{models,measurement,service}.py`、`tests/product/test_measurement.py`、`tests/api/test_http_contract_matrix.py`、`studio/src/views/EvidenceView.tsx`、C2 iteration | verified in local scope；没有 MeasurementObservation/EvidenceReview |
| 浏览器 Product Contract 闭环 | 从一句话到 intent/problem/outcome 三次 proposal、纠正与具名确认，全程显示 revision、状态与 Job 来源 | `studio/e2e/product-studio.spec.ts`、`studio/src/views/ContractView.tsx` | verified with fake provider；真实 provider 已在脚本链路验证 |
| 回归基线 | Python、前端单测、类型/生产构建、Chromium E2E/axe 和 OpenAPI drift 通过 | 2026-09-27：561 passed、3 skipped、2 warnings（不含可选 C0 真实 provider 重复测试；含 C3 B4 诊断 Gate）；R4 真实复测 10/10 完整通过；前端 29 passed；Chromium E2E 3 passed；`npm run build` 成功；已重新生成 OpenAPI drift 基线 | verified in covered scope |

## Product Studio 能力差距

| 工作流 | 目标 | 当前状态 | 最近下一步 |
|---|---|---|---|
| 上位产品模型 | ProductIntent、ProblemModel、OutcomeContract、ProductThesis、WebProductGenerationContract 与 OutcomeMeasurementPlan 均可版本化、纠正和追溯 | first-slice + B2 + C2 verified | 先完成本地恢复/Job 控制补强，再进行 C1 负责人自试；C3 根据稳定性复核字段 |
| 项目应用层 | 用 Domain Command 和 `expected_revision` 编排上位对象 | verified for first slice | 跨域 realization 或多方协作出现时复核聚合与存储边界 |
| FastAPI API | `/api/v1` 提供稳定命令/读取入口 | local Phase A contract matrix + proposal job endpoints verified | 接入真实 provider 时保持“创建即返回 job_id、执行走独立命令”的边界 |
| Web Product Studio | 五区工作空间共享同一项目 revision 上下文；工作台可比较 thesis、生成并确认 Web generation contract、执行/修复/导出，并在 Evidence 区处理 C2 测量计划和 C1 主持 intake | Product Contract correction、B1/B2、B3–B9、C2 Evidence plan、C1 host panel verified；真实参与者流程仍未执行 | 本地主链路恢复 Gate 已通过；继续处理剩余本地体验风险，C1 负责人自试保持暂缓 |
| 对话到结构化状态 | 模型 proposal 经人确认后成为领域 revision | proposal/confirm workflow verified with deterministic fake provider | 换成真实 provider 前先定输入保留、预算与失败重试边界 |
| 持久化长任务 | Job 可暂停、恢复、取消、限预算并处理 stale input | proposal、Generation、Execution 与 Repair Job 的 enqueue/run/retry、stale、失败、预算、取消和 SQLite/InMemory revision 恢复 verified；没有常驻 worker/SSE | 后续按真实需求增加单 worker、进度流或 SSE |
| 隔离生成与运行 | 在受限 workspace 构建、测试和运行生成的 Web 产品，并对失败执行受限修复 | B4 本地 Execution Job 覆盖独立权限、固定依赖、构建、loopback 预览与步骤恢复，并已真实跑通（修复了 Windows 环境、npm config、预览孤儿进程与构建副产物 4 类缺陷）；B5 只读安全摘要并在 child workspace 重跑验证 | 部署级 OS/container 隔离、浏览器二进制 Gate 与真实任务反馈 |
| 浏览器验证 | Playwright 覆盖启动、关键任务、错误态和基础可访问性 | 生成模板测试覆盖启动、Continue、Stop/error、critical/serious axe 与截图产物；B5 可对已知浏览器/axe 失败做确定性白名单修复 | 截图尚非视觉基线回归；仍无跨浏览器/移动/真实用户结果 |
| 预览与反馈 | 用户直接使用产品，反馈锚定页面、任务和 revision，并驱动可审查迭代 | B7 预览/显式反馈 + B8 迭代提案、版本差异与人工处理状态 verified；模板不消费验收检查，迭代后源码/构建不变 | B9：让迭代改变产品（模板消费检查或 B7m 模型路径） |
| 导出与交付 | 导出源码、构建物、验证结果、未知和交付说明 | B6 本地交付包 verified（含一次真实链路）；未签名、无部署 | 签名/发布渠道按真实交付需求再定 |
| 真实结果验证 | 现实任务、用户报告和测量保持来源与证据边界 | C2 测量计划、C1 observation/review intake、trial lifecycle/retention backend/API/host panel verified；没有真实参与者数据；C3 R4 评估 Gate 已通过 | C1 负责人本地自试；后续是否扩大样本由结果和需求决定；部署级/跨环境稳定性 |

`partial foundation` 只表示旧内核存在可复用构件，不表示 Product Studio 已经提供该用户能力。

## 当前证据边界

- 当前版本可以称为本地 Product Studio 工作空间原型，但不能称为完整 AI Product Studio；用户可以得到经人工确认、生成并在本机验证的 Web workspace，以及一份经人确认的“如何测量”计划，仍得不到自动研究、部署级隔离或现实任务结果。
- Product Contract 默认仍使用 deterministic fake；显式选择 real 时，Intent/Problem/Outcome/Thesis 使用 DeepSeek。真实模型输出仍只是待人工确认的 proposal，不是外部事实或现实结果证据。
- Transit Anchor 仍是 `geometry_ready / design-review confirmed / physical validation pending`。
- 当前 `PrototypeRun=0`、`MeasurementObservation=0`、Experience `EvidenceReview=0`；C1 Product-side intake 只有确定性/API/UI 测试记录，没有真实参与者数据，不能提升 Outcome Evidence；C2 的 MeasurementPlan 是计划元数据，不是 Observation 或 EvidenceReview。
- Blender、GLB、PNG、virtual preflight 和 scenario replay 是设计或派生材料，不是舒适、安全、可靠、可制造、合规或可发布证据。
- 自动化测试证明的是代码在覆盖范围内的行为，不证明产品给真实用户带来了目标结果。
- B5 Repair Job 只接收 B4 的步骤名、错误码和安全摘要；确定性 planner 只允许模板内可审查的文本补丁，未知失败会保留诊断并停止，不会因为本地验证通过就提升 Outcome Evidence。

## 当前约束与风险

1. Product 上位域暂时复用 `experience.models` 的 frozen/revision/event 基础类型；这是原型取舍，不是已确认的长期架构。
2. 第一条纵向切片已选定为自主管理工作的知识工作者保护桌面专注时段；A6 只校准领域边界，不证明产品价值，Phase C 仍需真实任务观察。
3. FastAPI 已约束在当前验证过的 `>=0.141,<0.142` 兼容线；前端 transport types 已从 OpenAPI 生成并有 drift test，但 Pydantic default fields 的 optional 表达仍由 UI alias 收窄。
4. 旧 ADR 在既有内核范围内才可能有效；新平台方向以 North Star 为准，新增字段、人工 Gate、聚合和存储选择须重新确认。
5. 初始 onboarding 仍由“创建项目”和“创建/运行意图提案 Job”组成，不是跨命令原子事务；现在首页会列出本地 SQLite 中的最近项目，失败或关闭浏览器后可从项目列表恢复，不再只依赖 localStorage 中的单个项目 ID。
6. 没有常驻 worker：proposal、generation 和 execution Job 仍由客户端显式推进；浏览器关闭后不会丢失 Job。工作区现在会显示未完成工作并提供继续入口，Generation Job 暴露暂停/继续/取消，Execution Job 暴露停止/重试；这些是恢复和状态控制，不是后台 worker，也不能保证正在执行的同步子进程被即时中断。
7. `product_intent` Job 仍保存用户原始输入，但已增加 4000 字符服务端/前端上限并显示计数；当前仍不做自动脱敏。C0 已决定完整输入仅发送给 provider、transcript 留在本机，后续托管/多用户版本需重新评估。
8. Playwright 当前只覆盖 Chromium 桌面的 onboarding、冲突恢复、Product Contract/C2 闭环以及 axe critical/serious Gate；尚无跨浏览器、移动或视觉回归。C0 的最新真实 provider 重复尝试在 B7m 静态门禁失败，说明一次成功不能代表模型路径稳定。
9. 全量测试仍有 Pydantic 字段遮蔽和 FastAPI TestClient/httpx2 迁移 warning；它们不影响本轮通过，但应在依赖升级前处理。
10. B5 默认最多 2 次修复尝试、2 个补丁、16 KiB 补丁内容和 2 成本单位；补丁只允许固定模板白名单路径并校验源文件 hash。真实 provider、跨框架修复、原始日志保留与部署级隔离仍需单独决策。
11. B4 优先使用 4173 作为约定预览端口；若被其他本地进程占用，执行器会为该次 Job 选择一个可用 loopback 端口，并将同一地址传给 Playwright，降低本地端口冲突。仍只支持本机已安装 Playwright 1.55.1 对应的 Chromium，执行器不会自动下载浏览器。
12. C2 测量计划当前只允许声明固定来源层；`model_interpretation` 不能作为证据，`runtime_event` 因 PS-O007 只能声明为 blocked。C1 仅接受 `research_observation`，ceiling 为 `observed`，计划确认不会创建观察记录，也不会提升 Outcome Evidence。
13. C1 真实试用默认由 `PSYTEARDOWN_C1_TRIAL_ENABLED=0` 暂停；只有明确开启后才允许创建 trial envelope。暂停是工作流门禁，不是身份、权限或多租户治理。
14. reviewer 具名校验只拒绝明显自动化主体和常见占位名；它不是现实身份认证。
15. Job 控制仍是本地客户端动作：暂停/取消/重试先改变持久化状态；若另一个同步请求已经进入子进程，不能承诺即时杀掉该进程，需依赖下一次恢复/刷新确认最终状态。
16. C1 close/stop 后源记录保留至 envelope close 后 30 天；cleanup 在本地 C1 service 初始化以及 envelope list/get 前触发，不是常驻 worker，也不声称擦除 SQLite 备份、操作系统残留或外部副本。

## 下一次状态更新的触发条件

下一次状态更新由负责人对私有仓库、访问者和 C1 开关的明确决定触发；在明确开启 `PSYTEARDOWN_C1_TRIAL_ENABLED` 前不启动真实参与者/负责人体验验证。后续 N=1 仍只能形成一条本地探索性真实观察，不满足当前 C2 计划的 minimum_n=3，也不能单独支持可泛化的产品效果声明；没有现实任务观察和独立人工 EvidenceReview 前，不提升 Outcome Evidence。
