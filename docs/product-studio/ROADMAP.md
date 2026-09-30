# Product Studio 路线图

- 基线日期：2026-09-30
- 路线图状态：Phase A 已关闭；Phase B 已关闭（B1–B9 含 B7m 已实现并验证，退出复核完成）；Phase C in progress（C0/C2/C3 已完成；C1 backend/API/UI 已实现，未招募真实参与者）
- 排序原则：先完成一个可验证的数字产品纵向闭环，再扩展用户类型、基础设施或 realization pack

## 状态图例

| 状态 | 含义 |
|---|---|
| `done` | 验收条件已有可复核证据 |
| `in progress` | 当前正在实施 |
| `ready` | 前置条件满足，可直接开始 |
| `prototype tested` | 实现及测试存在，但字段/架构的产品决策未确认，不能当作阶段正式完成 |
| `paused` | 已明确暂停，不继续投入，保留已写的草稿和待解决问题 |
| `planned` | 已进入路线图，但前置条件尚未满足 |
| `decision required` | 缺少会实质改变实现的产品或架构决策 |

完成度按工作包和退出门槛判断，不使用缺少事实基础的百分比。

## 总体阶段

| 阶段 | 目标结果 | 状态 | 退出门槛摘要 |
|---|---|---|---|
| Phase A | 上位模型和 Product Studio 壳 | done（A6 首条切片校准完成） | 可从 Web/API 创建项目、形成并纠正确认 Product Contract，旧内核经应用服务复用；四对象字段与人工确认范围已在首条数字产品切片中冻结 |
| Phase B | 数字产品生成闭环 | done（Exit Review 完成） | 从模糊意图到可运行 Web 产品、自动测试/修复、反馈和导出全链路可演示且可恢复 |
| Phase C | 真实结果验证 | in progress（C0/C2/C3 已完成；C1 软件侧试用前准备已验证，尚未启动负责人自试/招募参与者） | 目标结果有可操作测量，现实观察与 AI/仿真解释严格分层，并能回退产品论点 |
| Phase D | 个人交付与企业治理 | planned | 身份、权限、租户、预算、审计与外部系统集成由真实需求驱动并经过验证 |
| Phase E | Realization Packs | planned | 在数字产品路径验证后，以共享内核增加移动、硬件、服务等独立实现包 |

## Phase A：上位模型和产品壳

### A0 — 建立项目记忆系统

- 状态：`done`
- 产物：本目录的状态、路线图、决策索引、演变日志、工作流计划和记录模板
- 验证：仓库测试基线 406 passed、2 skipped；未修改生产代码

### A1 — 上位领域契约与状态转换（首条切片基线）

- 状态：`done`（首条切片校准）；不声称是所有 realization pack 的最终 schema
- 范围：`ProductIntent`、`ProblemModel`、`OutcomeContract`、`ProductThesis`
- 关键产物：
  - 每个对象的职责、最小字段、不变量和 revision 语义；
  - proposal、human confirmation、amendment、supersession 和 invalidation 状态转换；
  - 与 DesignBrief、Discovery、Evidence 和现有 revision/dependency graph 的映射；
  - 原型假设记录与领域单元测试；只有经确认需要时才创建正式决策文档。
- 退出门槛：四类对象能通过命令创建/修订；无确认 proposal 不能静默成为权威状态；上游变化的影响可确定性计算；已用 A6 首条切片检验字段与确认门槛。

### A2 — 项目聚合与应用服务（首条切片基线）

- 状态：`done`（首条切片校准）；跨域长期集成边界仍待后续场景验证
- 前置：A1
- 范围：Product Project/Program 的最小聚合边界、命令处理、读模型、Repository 接口和内存/SQLite 适配。
- 退出门槛：同一项目下可追踪四个上位对象；写入支持 `expected_revision`；命令为原子事务边界；旧内核通过明确适配器复用；A6 已确认独立 current pointer 与只读 projection 适合首条切片。

### A3 — FastAPI `/api/v1` 壳

- 状态：`done`；完整四对象命令、错误/Gate/conflict、OpenAPI、SQLite lifespan/restart HTTP 矩阵通过
- 前置：A1/A2 首条切片基线（A6 已校准；跨域长期边界仍待后续验证）
- 范围：项目资源、命令端点、错误契约、OpenAPI、健康检查和 fake provider 下的集成测试。
- 退出门槛：API 不承载领域写逻辑；并发 revision 冲突可见；耗时动作只返回 Job 引用；客户端类型可由 schema 校验或生成。

### A4 — React/TypeScript/Vite Product Studio 壳

- 状态：`done`；五区壳、三个上位对象的纠正交互、浏览器 E2E 与可访问性 Gate 均已通过
- 前置：A3 当前最小 schema
- 范围：项目主页以及对话、产品契约、工作台、决策、证据五区导航；共享项目 revision 上下文；加载、空、错误和 stale 状态。
- 已有证据：浏览器工作空间具备五区导航；可创建、纠正并确认 ProductIntent、ProblemModel 与 OutcomeContract，409 conflict 刷新权威 revision 且保留草稿；OpenAPI 生成客户端类型；加载、空、错误和未实现能力显式；前端 10 tests、Chromium E2E/axe 2 tests 和 production build 通过。
- 未纳入本包：ProductThesis 交互、离线草稿持久化、Job 重试/取消控件，以及跨浏览器与视觉回归。

### A5 — Phase A 薄纵向集成

- 状态：`done`
- 前置：A1–A4
- 范围：用 fake provider 从一条模糊输入生成结构化 proposal，经人工确认形成 Product Contract，并显示 revision 与未知项。
- 已有证据：持久化 proposal Job（创建即返回 `job_id` 且不执行 provider、单步 run、pinned revision、fingerprint 幂等、stale/失败分流、重启恢复）与确定性 fake provider；浏览器可完成“一句话 → intent/problem/outcome 三次提案 → 纠正 → 具名确认”；Python 455 passed/2 skipped、前端 10 passed、Chromium E2E 2 passed、构建与依赖检查通过。
- 边界：provider 无网络、无研究能力，其输出不是事实或证据；没有常驻 worker、进度流、暂停/取消与预算。
- 详细记录：[`iterations/2026-09-20-a5-fake-provider-product-contract.md`](iterations/2026-09-20-a5-fake-provider-product-contract.md)

### A6 — Phase A 出口：首条切片校准（Phase B 前置 Gate）

- 状态：`done`
- 前置：A5
- 范围：选定一类具体目标用户与现实问题（PS-O001），用该切片复核四对象最小字段、人工确认范围与聚合边界（PS-O002/O003），并冻结首条纵向切片的 Outcome Contract。
- 退出门槛：A1/A2 已升级为按首条数字产品切片确认的基线，并记录字段、确认门槛、聚合边界和冻结 Outcome Contract；Phase A 关闭。

## Phase B：数字产品闭环

按依赖顺序推进：

1. 基于 A6 已冻结的首条纵向切片 Outcome Contract，生成 2–3 个具有真实机制/实现差异的 Product Thesis；
2. 由人选择或授权低成本证伪路径；
3. 建立受支持的单一 Web 技术模板和内容最小化生成契约；
4. 建立持久化、幂等、可恢复且受预算约束的生成 Job；
5. 在隔离 workspace 中安装依赖、构建并运行产品；
6. 用 Playwright 执行关键任务、错误状态、基础可访问性和视觉回归；
7. 自动定位并修复失败，保留每次尝试和成本；
8. 提供嵌入式预览、revision 差异和页面/任务级反馈锚点；
9. 导出源码、构建物、测试证据、未验证声明和交付说明。

### B1 — Product Thesis 搜索与人工选择

- 状态：`done`（本批次）
- 前置：A6 冻结的 PS-O001/Outcome Contract
- 实现：`product_theses` revision-pinned proposal Job；确定性 fake provider 生成三条机制、实现方式、关键未知、最低成本证伪和维护负担不同的 Web 路径；重复请求按 fingerprint 复用，执行前检测 stale input，部分提交后可协调同一结果；HTTP/OpenAPI 暴露 batch Job。
- Web：工作台可生成并列候选并显示验证层级/维护负担；决策区针对每条候选提供“授权低成本探索”和“选择此论点”，选择仍通过现有具名 Domain Command。
- 证据：`tests/product/test_jobs.py`、`tests/api/test_proposal_jobs.py`、`studio/src/views/WorkbenchView.tsx`、`studio/src/views/DecisionsView.tsx`；Python 459 passed、2 skipped，前端 11 passed，production build 成功。
- 边界：候选来自无网络、无研究能力的确定性 provider，不是外部事实、用户结果或已选择赢家；尚未生成或运行 Web 产品。

### B2 — 单一 Web 模板与内容最小化生成契约

- 状态：`done`（本批次）
- 前置：B1 候选比较；需关闭 PS-O004
- 范围：允许的 Web 技术模板、内容/页面/任务/状态最小字段、生成输入输出和 revision 绑定；不进入真实代码执行，直到 PS-O005/PS-O006 关闭。
- 决策：首条切片唯一模板为 `react_typescript_vite_spa`（React + TypeScript + Vite SPA）；运行时仅 React/ReactDOM、本地 fixture、无网络；契约固定页面、关键任务、ready/loading/empty/error/success 状态、语义内容槽位和确定性验收检查；proposal/confirm 依赖 confirmed OutcomeContract 与 exploring/selected ProductThesis。
- 证据：`src/psyteardown/product/models.py`、`src/psyteardown/product/providers.py`、`src/psyteardown/product/jobs.py`、`tests/product/test_jobs.py`、`tests/api/test_proposal_jobs.py`、`src/psyteardown/api/projects.py`、`studio/src/views/WorkbenchView.tsx`；Python 461 passed、2 skipped，前端 11 passed，production build 成功，Chromium E2E 2 passed。
- 边界：契约描述的是后续生成输入，不是源码、依赖安装、运行实例、沙箱授权或真实结果；PS-O005/PS-O006 仍保持 open。

### B3 — 受预算约束的 Web 生成 Job workspace

- 状态：`done`（B3 本地切片）；执行权限与运行验证由独立 B4 Job 处理
- 前置：B2；PS-O005/PS-O006 已按首条切片关闭
- 实现：确认后的 Web generation contract 可创建独立 Generation Job；Job 以项目/Job workspace、fingerprint、输入 revision、checkpoint、manifest 和预算消耗持久化；确定性模板只写固定最小源码、fixture、测试和 manifest，不安装依赖、不执行源码、不访问网络或 Secret。
- 边界：默认一次尝试、64 文件、1 MiB、60 秒、1 成本单位；暂停/恢复/取消、stale、预算耗尽、幂等和 SQLite 重启恢复均有测试。workspace 产物不是可运行产品，也不提升现实证据等级。
- 证据：`src/psyteardown/product/generation.py`、`src/psyteardown/api/generation_jobs.py`、`tests/product/test_generation.py`、`tests/api/test_generation_jobs.py`；Python 469 passed、2 skipped，前端测试/构建通过。

### B4 — 受隔离执行的构建、运行与浏览器验证

- 状态：`done`（本地执行切片；部署级隔离仍未完成）
- 前置：B3
- 范围：单独定义依赖安装、构建、运行、Playwright/axe/视觉检查和失败修复的执行 sandbox；不得把 B3 的源码生成过程误当作执行权限。
- 实现：独立 `ProductExecutionJob` pin 成功的 B3 generation revision，复核 manifest/package allowlist，按 install/build/loopback preview/Playwright 顺序执行；每步、预算、错误摘要和重启状态持久化，API 与工作台提供显式执行入口。
- 证据：`src/psyteardown/product/execution.py`、`src/psyteardown/api/execution_jobs.py`、`tests/product/test_execution.py`；生成模板补齐固定依赖、preview、Playwright/axe/截图检查。
- 边界：当前为本机无 shell 的 allowlisted subprocess，不是容器/远程多租户隔离；浏览器二进制、跨浏览器/移动/视觉基线和真实用户结果仍未验证。

### B5 — 受限失败定位与修复闭环

- 状态：`done`（本地 deterministic repair 切片；真实模型/跨框架修复仍未完成）
- 前置：B4
- 范围：将失败的 B4 Execution Job 交给独立、持久化且受预算约束的 Repair Job；只读取步骤名、错误码和安全摘要，输出可审查的白名单文本补丁，并在新的 workspace 中重新生成与验证。
- 实现：Repair Job pin 失败执行 revision，支持 fingerprint 幂等、`stale_input`、显式 run/retry/cancel、SQLite/InMemory revision 恢复和每次尝试/补丁/成本记录；补丁只允许模板已知的 `src/App.tsx`/`src/styles.css` 路径、精确 hash 和预算范围。成功修复创建带父 generation lineage 的新 generation revision 与独立 Execution Job，原 B3/B4 revision 不变；未知失败安全返回 `unsupported_failure`，不猜测修改源码。
- 证据：`src/psyteardown/product/repair.py`、`src/psyteardown/api/repair_jobs.py`、`tests/product/test_repair.py`、`studio/src/views/ProjectStudio.tsx`、`studio/src/views/WorkbenchView.tsx`、[`iterations/2026-09-22-b5-bounded-repair-loop.md`](iterations/2026-09-22-b5-bounded-repair-loop.md)；Python `pytest -q` 477 passed、2 skipped、2 warnings，前端 11 passed，Chromium E2E 2 passed，production build 成功。
- 边界：planner 仍是确定性本地规则，不读取原始命令输出、不接入真实模型/远程代码代理、不修改测试/依赖/脚本来“刷绿”；容器/远程多租户隔离、视觉回归基线、跨浏览器/移动验证和真实用户结果仍未验证。

### B6 — 可追溯导出交付包

- 状态：`done`（本地交付包；未签名、未部署）
- 前置：B4（成功执行），可选 B5 修复 lineage
- 实现：不可变单 revision `ProductDeliveryBundle` pin 当前成功的 Execution Job revision；复核 generation revision、源码 manifest、`dist/index.html`、凭据类文件与符号链接；输出字节确定、以 sha256 寻址的 zip（`source/`、`build/`、`verification/`、`DELIVERY.md`、`bundle-manifest.json`）；同一执行幂等；InMemory/SQLite insert-only；`/delivery-bundles` 创建/列表/读取/下载（下载前复核 hash）；工作台导出与下载入口。
- 真实验证：首次在本机以真实 npm + Chromium 跑通 B3→B4→B6，并修复了由此暴露的 B4 缺陷（Windows 环境变量、npm config、预览孤儿进程可导致验证旧 workspace、构建副产物被误判为篡改）。
- 证据：`src/psyteardown/product/delivery.py`、`src/psyteardown/product/execution.py`、`tests/product/test_delivery.py`、`tests/api/test_delivery_bundles.py`、[`iterations/2026-09-23-b6-delivery-bundle.md`](iterations/2026-09-23-b6-delivery-bundle.md)；`pytest -q` 490 passed、3 skipped；前端 15 passed；Chromium E2E 2 passed；build 成功。
- 边界：包内 `outcome_evidence_level=none`；不含 lockfile/node_modules；未签名、未部署；不替代预览反馈与真实任务结果。

### B7 — 预览与显式反馈锚点

- 状态：`done`（本地预览与显式反馈；不含迭代）
- 前置：B6；PS-O007 已决定（仅显式反馈）
- 实现：工作台沙箱 iframe 从 hash 复核的 B6 archive 读取 `build/` 文件（仅服务时把 `index.html` 根绝对资源改写为相对路径，包字节不变）；`PreviewFeedback` 锚定 bundle/execution/contract revision 与 screen/task/state，逐次显式同意（`b7-explicit-v1`），提交者可撤回为 r2 墓碑并擦除正文；`/preview-feedback-policy`、`/delivery-bundles/{id}/preview/…`、`/delivery-bundles/{id}/feedback`、`/preview-feedback`、`/preview-feedback/{id}/withdrawal`。
- 证据：`src/psyteardown/product/feedback.py`、`src/psyteardown/api/preview_feedback.py`、`tests/product/test_feedback.py`、`tests/api/test_preview_feedback.py`、`studio/src/views/PreviewFeedbackPanel.tsx`、[`iterations/2026-09-23-b7-preview-feedback-anchors.md`](iterations/2026-09-23-b7-preview-feedback-anchors.md)；`pytest -q` 504 passed、3 skipped；前端 20 passed；Chromium E2E 2 passed；build 成功；真实链路浏览器验证通过。
- 边界：反馈为 `user_report`，不代表任务完成或真实结果；单机单用户 actor；无自动事件、无任务自报、无版本差异。

### B7m — 真实模型源码生成（插入包）

- 状态：`done`（首条切片；单次真实链路）
- 前置：B7；PS-O011/PS-O012 已按首条切片决定
- 实现：`ProductSourceModel` 端口 + DeepSeek 适配；B3 Generation Job 可选 `source=model`，模型只写 `src/App.tsx`/`src/styles.css`，经静态门禁后写入 workspace；浏览器测试从契约派生；每 Job 最多 2 次调用，transcript 仅存本机；B6 交付说明标注模型源码未经人工审阅。
- 证据：`src/psyteardown/product/source_model.py`、`tests/product/test_source_model.py`、`tests/api/test_source_model_api.py`、[`iterations/2026-09-23-b7m-model-source-generation.md`](iterations/2026-09-23-b7m-model-source-generation.md)；`pytest -q` 523 passed、3 skipped；前端 22 passed；E2E 2 passed；真实 DeepSeek→B4→B6 一次成功。
- 边界：一次真实链路不代表模型稳定性、代码安全完备性或用户结果；无模型修复、无金额预算。

### B8 — 反馈驱动的迭代与版本差异

- 状态：`done`（首条切片；模板路径下产品不变）
- 前置：B7；PS-O013/O014/O015 已按首条切片决定
- 实现：`web_generation_contract` proposal Job 可带 `feedback_id`，pin baseline 契约 + 反馈，产出同一契约的下一 proposed revision（保留全部 ID，追加一条引用反馈 ID/类别的验收检查，不复制正文）；人确认后重走 B3→B4→B6；`/delivery-bundles/{id}/diff` 比较文件 sha256 与契约集合变化；反馈处理状态由人显式标记；工作台提供迭代入口、修订说明与差异面板。
- 证据：`tests/api/test_feedback_iteration.py`、`tests/product/{test_feedback,test_jobs}.py`、`studio/src/views/{PreviewFeedbackPanel,WorkbenchView}.test.tsx`、[`iterations/2026-09-24-b8-feedback-driven-iteration.md`](iterations/2026-09-24-b8-feedback-driven-iteration.md)；`pytest -q` 527 passed、3 skipped；前端 24 passed；E2E 2 passed；build 成功。
- 边界：确定性模板不读取验收检查，修订后源码/构建字节相同（diff 如实显示）；无逐行/视觉差异；无本批专项真实链路。

### B9 — 让反馈迭代真正改变产品

- 状态：`done`（首条切片；架构分析）
- 前置：B8
- 范围：模板消费契约验收检查，或在已确认修订契约上走 B7m 模型源码生成（模型仍只收已确认契约）；之后做 Phase B 出口复核。
- 决策：PS-O016 决定模板固定不消费验收检查，只有模型路径（`source="model"`）才在契约变化时产生不同源码；模板作为稳定回退基线，模型承担"根据需求变化调整产品"。
- 证据：架构分析确认 B7m `contract_payload` (source_model.py:164) 已包含 `acceptance_checks`；B8 修订契约添加验收检查；B3 `source="model"` 传递完整契约给模型；组合逻辑证明模型路径可以产生不同结果。
- 边界：首条切片依靠架构分析和现有测试组合，未做模型迭代的端到端自动化测试；模型是否消费验收检查、如何解释它们、稳定性如何，需多次真实运行观察。

Phase B 后续仍必须解决的决策：部署级 OS/container 隔离、视觉回归与跨浏览器 Gate、以及真实 provider 的输入保留/模型与工具费用；首个现实问题已由 A6 的 PS-O001 冻结。B3/B4/B5 的本地 workspace、执行和 deterministic repair 只证明受覆盖的软件行为，不替这些执行与现实验证决策提供批准。

### Phase B 退出后的产品化跟进 — V0.2 Decision Brief

- 状态：`prototype tested`；当前不是 MVP，而是从最小可验证原型向最小产品切片演变。
- 触发：V0.1 只能在当前页面临时记录选项，刷新后丢失，也没有可带走的成果；技术闭环已通过，但核心产品价值仍未验证。
- 范围：在不引入推荐、评分、账号、云同步或外部数据接入的前提下，增加决定设定、背景/回看时间、个人倾向、下一步核实问题，以及显式 JSON 导出/导入重开。
- 当前主链路：`setup → compare → brief → export/import`；当前项目的 r10 Web contract 已确认，下一步生成 workspace/B4/B6；已有 r2/r5 B6 不自动覆盖。
- 退出门槛：用户可独立完成一次近期决定，并留下可重新打开的 Decision Brief；至少再用第二个真实决定验证是否有复用意愿。该门槛不是长期决策质量或市场效果证据。
- 下一步：若复用信号成立，再把 `decision-brief.v1` 演变为 SQLite-backed `DecisionBrief` aggregate；在此之前不增加复杂基础设施或扩大 C1。
- 详细记录：[`iterations/2026-09-30-v02-decision-brief.md`](iterations/2026-09-30-v02-decision-brief.md)

## Phase C：真实结果验证

### C0 — 真实 provider 接入与端到端链路

- 状态：`done`
- 实现：DeepSeek Product Contract（Intent/Problem/Outcome/Thesis）适配、项目 `.env.local` 加载、JSON mode、schema 门禁与安全失败摘要；B7m 真实源码生成继续只接收已确认 Web generation contract。
- 真实证据：2026-09-25 完成一次真实 `Product Contract → Web generation contract → DeepSeek source=model → B4 install/build/preview/Playwright/axe → B6 delivery bundle` 链路。
- 成本证据：成功链路为 5 次模型调用，5,788 input tokens，7,824 output tokens；金额不计量，符合 PS-O018；总耗时 100.22 秒，其中 B4 69.04 秒。2026-09-26 重复尝试在 B7m 静态门禁发现模型漏写契约 screen ID 后失败；稳定性仍交给 C3。
- 遗留边界：Web generation contract 仍为 deterministic fake；无金额预算、自动重试、部署级隔离、视觉回归和真实用户结果证据。
- 证据：[`iterations/2026-09-24-c0-real-provider-integration.md`](iterations/2026-09-24-c0-real-provider-integration.md)、`tests/product/test_c0_real_provider_e2e.py`、本地 `c0-metrics.json`。

### C1 — 小规模真实任务观察接入

- 状态：`in progress`（Product-side backend/API 与主持面板已实现；未招募、未收集真实参与者）
- 已有前置：C2 测量计划和 B6 可运行交付版本；Experience 内核有 `OutcomeObservation`/`EvidenceReview` 基础模型，但未接入 Product C2 的 plan/delivery/consent revision。
- 决策已冻结：本地同意/最小数据/撤回和保留（PS-O022）；Product-side typed intake 与专用存储边界（PS-O023，PS-O010 对长期跨域仍 open）；具名 reviewer 与 source-layer ceiling（PS-O024）。
- 当前动作：D1/D2/D3 已按本地首批边界冻结；API/backend/host panel、主链路、恢复控制、暂停与生命周期门禁已实现。2026-09-29 追加 Product Usability Gate：C1 envelope 还要求 host 确认已亲自完成核心任务，不能只有 B4/B6 软件通过。首条 fake Web contract、deterministic template 与源码模型提示已改为要求具体的选项对比板、真实输入/内容和用户自己的判断；旧交付包不自动升级，必须重新生成。真实参与者/负责人自试仍未启动，默认开关保持关闭；N=1 仍按 `participant_n=1, session_k>=1` 记录，不满足 C2 `minimum_n=3`，也不支持泛化效果声明。保持 `c1-local-v1` 同意/撤回边界；无独立 reviewer 时观察可保留为未 review，任何 evidence-level promotion 均要求与 host 分离的具名 reviewer。
- 已冻结/已实现范围：人工主持、随机 participant ID、显式逐次同意、Product-side 手动 C1 observation intake；每条记录 pin C2 MeasurementPlan revision + measure + B6 bundle/execution revision + consent receipt；无自动运行事件采集；具名人工 EvidenceReview 受 source ceiling 门控；撤回按批准政策擦除/排除相关数据。
- 退出门槛：至少一轮符合已确认 C2 样本计划的可复核任务试用完成；每条观察可追上述 pin；未同意/撤回/缺失/技术失败均有拒绝或非成功路径测试；参与者使用的同意文案和数据处理方式已清楚展示；EvidenceReview 由具名且与 host 分离的人工完成。负责人 N=1 自试可以作为启动性真实观察，但不单独满足 minimum_n=3 的退出门槛。

### C1.3 — trial lifecycle and retention enforcement

- 状态：`done`
- 范围：C1 envelope close/stop API、Panel 结束 trial、关闭后禁止新的 enrollment/presentation/observation、SQLite/restart/withdrawal/retention 回归。
- 实现：active envelope 可通过 `/close` 或 `/stop` 结束并记录 `closed_at`、`close_reason` 和 `retention_expires_at`；服务端继续以 active gate 拒绝关闭后的 presentation/observation；Panel 要求结束原因并显示 30 天 retention 到期信息。
- retention：本地 C1 service 初始化以及 envelope list/get 前执行 cleanup；到期后删除 receipt、participant、presentation、observation 和 review 源记录，保留 envelope 生命周期状态与 content-free audit。无常驻 worker，不声明外部备份擦除。
- 边界：本批不启动真实参与者，不改变 C2 `minimum_n=3`，不提升 Outcome Evidence；关闭后允许整理已存在 observation 的人工 review，withdrawal tombstone 继续按 content-free 语义保留。
- 验证：C1 API 7 passed（含 close/stop、关闭后写入拒绝、SQLite restart 与 30 天 cleanup）；前端 29 passed；完整回归结果见 C1.3 iteration。
- 详细记录：[`iterations/2026-09-27-c1-trial-lifecycle-and-retention.md`](iterations/2026-09-27-c1-trial-lifecycle-and-retention.md)

### C1.2 — C1 暂停门禁、独立审查与中断 Job 恢复

- 状态：`done`
- 范围：在真实体验验证继续暂缓时，把暂停落实到 API/UI；修正 reviewer 占位身份；为中断的 `running` Execution Job 增加显式 orphan recovery。
- 实现：`PSYTEARDOWN_C1_TRIAL_ENABLED` 默认关闭；C1 policy 返回 trial state；服务端阻止暂停期间创建 envelope；reviewer 不再预填占位名；Execution recovery 要求调用方确认 orphaned 后才回到 queued。
- 边界：开关不是身份/权限系统；具名 reviewer 不是身份认证；recovery 不能证明旧 subprocess 已退出，部署级隔离仍未完成。
- 详细记录：[`iterations/2026-09-27-c1-trial-pause-and-orphan-recovery.md`](iterations/2026-09-27-c1-trial-pause-and-orphan-recovery.md)

### C1.1 — 真实体验验证前的本地体验约束补强

- 状态：`done`
- 范围：不改变 C1 证据边界，只处理会让本地使用中断或失去上下文的约束。
- 实现：项目列表/恢复 API 与首页最近工作区；未完成 proposal/generation/execution Job 的继续入口；generation 暂停/继续/取消与 execution 停止/重试控件；product intent 原始输入 4000 字符上限；B4 预览端口冲突时回退到可用 loopback 端口。
- 证据：[`iterations/2026-09-27-product-studio-recovery-and-local-guardrails.md`](iterations/2026-09-27-product-studio-recovery-and-local-guardrails.md)。这些能力不创建参与者数据、不提升 Outcome Evidence。

### C2 — Outcome Contract 指标测量计划

- 状态：`done`
- 实现：从已确认 Outcome Contract 确定性派生带 revision 的测量计划；每条 SuccessIndicator 至少一个 measure；固定来源层、服务端派生的证据上限/可收集性、收集方法、值类型、阈值、缺失处理和矛盾回退；每个禁止结果生成 guardrail，计划引用全部停止条件。
- 人工 Gate：真实世界指标必须有可收集的非软件测量；只能有一个主测量；阈值不能保留占位符；样本、同意和撤回范围必须明确；`runtime_event` 目前只能以 blocked measure 声明，`model_interpretation` 永远不是测量来源。
- 验证：InMemory/SQLite derive→human revision→confirm→restart、Outcome Contract 修订后的 stale impact、HTTP/OpenAPI、前端证据区编辑/确认、确定性 Python 回归 538 passed/3 skipped、前端 26 passed、Chromium E2E 2 passed、生产 build 成功。
- 遗留边界：C2 只定义如何测量，不招募参与者、不写入 MeasurementObservation/EvidenceReview，也不产生现实结果证据。
- 证据：[`iterations/2026-09-25-c2-outcome-measurement-plan.md`](iterations/2026-09-25-c2-outcome-measurement-plan.md)、`tests/product/test_measurement.py`、`tests/api/test_http_contract_matrix.py`、`studio/src/views/EvidenceView.test.tsx`。

### C3 — 多次真实链路稳定性评估

- 状态：`done`（R4 10/10 完整通过本批评估 Gate；不等于生产级稳定性保证）
- 证据：[`C3 评估记录`](iterations/2026-09-26-c3-real-provider-stability.md)、`output/product-studio/c3-stability/c3-stability-report.json`、`output/product-studio/c3-stability-r2/c3-stability-report.json`、`output/product-studio/c3-stability-r3/c3-stability-report.json`、`output/product-studio/c3-stability-r4/c3-stability-report.json`；R1 为 36 次模型调用、42,194 input / 60,844 output tokens、577.78 秒；R2 加入每阶段最多一次显式有界重试，为 52 次调用、58,850 input / 86,279 output tokens、746.48 秒；R3 增加 B4 阶段诊断，完成 25 次调用、28,430 input / 41,806 output tokens、725.40 秒后安全停止。
- 发现：R1 7/10，R2 8/10；R2 的 2 次 B4 `command_failed` 在 R3 被进一步区分为 1 次 `browser_command_failed` 和 1 次 `run_timeout`（R3 仅完成 6/10，不能作为通过率）。100 次调用上限未触发；金额保持 unavailable，不作推断。
- 后续诊断：本地确定性 Gate 已覆盖 `browser_assertion_failed`、`browser_accessibility_failed`、`browser_launch_failed`、`browser_timeout`，并断言 B4 `browser_timeout` 与 C3 外层 `run_timeout` 分离；R4 10 次真实完整链路全部通过，50 次模型调用，57,724 input / 83,183 output tokens，金额保持 unavailable。
- 非目标：不把稳定性或软件成功率当作真实用户结果；不在没有费用数据和需求前引入金额级预算。

Phase C 的共同边界：

- 区分运行事件、用户报告、研究观察、模型解释和正式 Evidence Review；
- 当结果不支持当前方向时，允许回退到 Product Thesis、Outcome Contract 或 ProblemModel；
- 不让软件测试、模拟用户或专家意见冒充真实用户结果。

## Phase D：个人交付与企业治理

- 基于真实使用决定本地个人版、托管版和企业部署的优先级；
- 加入身份、组织、权限、租户隔离、预算、数据政策和审计；
- 接入 Git、工单、数据仓库和部署平台；
- 支持多人评论、通知、冲突处理和具名审批；
- 达到并发与耐久性门槛后再评估 PostgreSQL、对象存储和 Temporal。

## Phase E：Realization Packs

- 数字产品主线验证后，再增加移动应用、硬件/工业设计、服务运营、内容/教育等 pack；
- 每个 pack 复用 Product Intent、Outcome Contract、Evidence 和 revision 内核；
- 每个 pack 单独定义生成器、工具、验证方法和发布 Gate；
- Transit Anchor 作为硬件 pack 的验证案例，不再承担整个平台的产品北极星。

## 暂不进入主线

在 Phase B 闭环通过前，不把以下内容加入当前关键路径：Kubernetes、Kafka、多队列、复杂插件市场、独立 Electron 客户端、任意框架代码生成、大量自治 Agent、无人批准部署，以及与 Python 内核重复的服务端业务逻辑。
