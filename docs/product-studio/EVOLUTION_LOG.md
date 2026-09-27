# Product Studio 演变日志

本文件记录项目级里程碑，按时间顺序只在末尾追加。早期条目中的新 ADR 与“固定架构”说法已由末尾的 2026-09-20 校正条目撤销；当前真实状态以 `CURRENT_STATE.md` 为准。

## 2026-09-20 — 建立 Product Studio 开发台账

- 触发：确认 [`AI Product Studio 北极星`](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) 是上位产品方向，需要在大型实施过程中保存连续项目记忆。
- 新增：目录入口、当前状态、阶段路线图、决策登记册、Phase A 工作流和 iteration 模板。
- 基线：现有 Python 可信研发内核、CLI/MCP、SQLite revision、体验/工程/质量能力保留；FastAPI、React Product Studio 和上位四对象尚未实现。
- 验证：运行 `pytest -q`，结果为 406 passed、2 skipped、1 warning，用时 20.16 秒。
- 边界：本次只建立开发治理与事实基线，没有修改生产代码，也没有提升任何产品或现实证据等级。
- 下一步：执行 A1，为 ProductIntent、ProblemModel、OutcomeContract 和 ProductThesis 确定最小领域契约与状态转换。
- 详细记录：[`iterations/2026-09-20-project-ledger-bootstrap.md`](iterations/2026-09-20-project-ledger-bootstrap.md)

## 2026-09-20 — A1 上位领域契约落地

- 新增：独立 `psyteardown.product` 上位产品域，包含 ProductIntent、ProblemModel、OutcomeContract、ProductThesis 的不可变 revision snapshot、细粒度值对象和纯状态转换。
- 决策：ADR 0429–0432 固定四对象职责；意图/问题/结果契约必须具名确认，ProductThesis 选择必须有人决定或引用显式授权。
- 护栏：确认后的内容再次修改会回到 proposal；上游 revision 变化只产生 `review_required`/`stale` 影响事实，不改写或删除历史对象。
- 验证：新增 18 个测试；完整 `pytest -q` 为 424 passed、2 skipped、1 warning，用时 19.52 秒。
- 边界：尚无 Product Project Repository、Application Service、SQLite schema、API 或 UI；新增能力是领域层，不代表用户已经能使用 Product Studio。
- 下一步：A2 项目聚合与应用服务，加入 Domain Command、乐观并发、事件/审计和 InMemory/SQLite 持久化。
- 详细记录：[`iterations/2026-09-20-a1-upper-domain-contracts.md`](iterations/2026-09-20-a1-upper-domain-contracts.md)

## 2026-09-20 — A2 项目应用服务与原子持久化

- 新增：最小 ProductProject 生命周期、显式 proposal/confirm/disposition commands、ProductApplicationService 和只读 ProductProjectView。
- 持久化：InMemory 与独立 `product_*` SQLite adapter 共享同一命令路径；事务内检查 `expected_revision` 和父链并保存 current、Domain Event、Audit Event 与 RevisionImpact。
- Gate：ProblemModel、OutcomeContract、ProductThesis 只能引用同项目的 confirmed upstream revision；暂停项目阻止子对象写入。
- 恢复：SQLite 关闭重开后可以恢复 revision chain、current pointers、事件、审计、impact 和完整项目视图。
- 架构：ADR 0433–0434 与 [`architecture/domain-boundaries.md`](architecture/domain-boundaries.md) 固定项目/子聚合及 Product/Experience 边界。
- 验证：Product 测试 32 passed；完整 `pytest -q` 为 438 passed、2 skipped、1 warning，用时 22.29 秒。
- 边界：尚无 HTTP API、Web UI、realization adapter、provider 或异步 Job；A2 不代表用户可通过 Product Studio 完成流程。
- 下一步：A3 FastAPI `/api/v1` 壳和稳定错误/DTO 契约。
- 详细记录：[`iterations/2026-09-20-a2-project-application-service.md`](iterations/2026-09-20-a2-project-application-service.md)

## 2026-09-20 — 校正 ADR 适用范围并暂停 A3

- 发现：前两批 iteration 把旧 Experience 域的 ADR 当作新 Product Studio 的默认约束，又过早给 7 篇新 ADR 标记 `accepted`；A1/A2 的测试仅能证明当前代码行为，不能批准长期架构。
- 处置：删除本轮未提交的 ADR 0429–0435；保留已有 430 篇旧 ADR 作为原适用范围内的历史，不做批量删除。
- 记录：`DECISION_REGISTER.md` 将 North Star 已明确的方向、原型假设与重新开放的问题分开；A1/A2 保留代码和测试，但标为 `prototype tested`。
- 暂停：A3 草稿代码保留，未完成 HTTP 测试；本机 FastAPI 0.115.6 / Starlette 1.3.1 组合启动失败，不能称为可用 API。
- 后续：选定首条代表性用户情境、校准四对象最小字段与人工确认范围，并解决依赖兼容后再决定是否继续 A3。
- 详细记录：[`iterations/2026-09-20-adr-scope-correction.md`](iterations/2026-09-20-adr-scope-correction.md)

## 2026-09-20 — 恢复 A3 并建立可运行 HTTP 边界

- 恢复：保留薄 FastAPI adapter 方向，不改变 A1/A2 仍为待产品验证原型的事实。
- 修复：确认原启动错误来自 FastAPI 0.115.6 与环境中 Starlette 1.3.1 的不兼容；将项目约束更新为已验证的 FastAPI `>=0.141,<0.142`，`pip check` 无破损依赖。
- 验证：新增临时 SQLite API 冒烟测试，覆盖项目创建、初始 ProductIntent、项目 projection、结构化 404/request ID；真实 Uvicorn 和 Vite proxy 联调返回 health 200、project create 201、project read 200。
- 边界：完整四对象 HTTP command/gate/conflict/restart 测试矩阵仍未补齐，因此 A3 保持 `in progress`，不把最小冒烟升级为稳定公开 API。
- 详细记录：[`iterations/2026-09-20-a3-fastapi-shell.md`](iterations/2026-09-20-a3-fastapi-shell.md)

## 2026-09-20 — A4 第一批 Product Studio Web 壳

- 新增：`studio/` React/TypeScript/Vite SPA，提供项目 onboarding 与对话、产品契约、工作台、决策、证据五区工作空间。
- 集成：前端只通过 `/api/v1` 读取 projection 和提交命令；项目创建后保存初始 ProductIntent，可执行已有人工确认和 ProductThesis transition。
- 诚实边界：对话生成、已存在契约纠正、后台 Job、隔离构建和产品预览均显示为未接入，不使用演示数据冒充完成。
- 验证：前端 6 个测试、TypeScript/Vite production build、npm audit、完整 Python 440 passed/2 skipped，以及真实 Vite→FastAPI HTTP 代理联调通过。
- 治理纠正：本批次开始时遗漏了 iteration 记录，收尾时按工作流补建并同步全部台账；后续必须在编码前建立记录。
- 详细记录：[`iterations/2026-09-20-a4-product-studio-web-shell.md`](iterations/2026-09-20-a4-product-studio-web-shell.md)

## 2026-09-20 — A4.1 ProductIntent 纠正、生成类型与浏览器 Gate

- 新增：用户可从 Product Contract 纠正完整 ProductIntent 字段，创建同 stable ID 的新 proposal revision；已确认内容被纠正后回到 proposed。
- 冲突：409 revision conflict 会刷新最新服务端 projection，同时保留本地草稿并要求用户复核重试，不自动合并价值字段。
- 契约：FastAPI OpenAPI 以确定性 JSON 导出，TypeScript transport types 在 build 前生成，并由后端 drift test 锁定。
- 浏览器：Playwright/Chromium 覆盖 onboarding、键盘打开/取消与焦点恢复、并发冲突、重试和确认；axe 在入口、编辑态和确认态执行 WCAG A/AA critical/serious Gate。
- 修复：首次 axe 运行发现暗色主题次要文本对比度不足；调整设计 token 和特定标签后通过。Vitest 与 Playwright 的发现范围也已显式隔离。
- 验证：Python 441 passed/2 skipped；前端 9 passed；Chromium E2E 1 passed；production build、npm audit、pip check 均通过。
- 边界：只验证 ProductIntent slice；没有模型生成、ProblemModel/OutcomeContract 编辑、离线草稿或真实用户结果证据。
- 详细记录：[`iterations/2026-09-20-a4-1-contract-correction-and-browser-gates.md`](iterations/2026-09-20-a4-1-contract-correction-and-browser-gates.md)

## 2026-09-20 — A3.1 完成 HTTP 契约与恢复矩阵

- 完整链路：从 HTTP 创建项目并依次 proposal/confirm ProductIntent、ProblemModel、OutcomeContract，最后 proposal/select ProductThesis。
- 错误边界：未确认 upstream 返回 409 domain gate；stale transition 返回 409 revision conflict 且 current projection 不变；422 validation issues 不回显敏感 rejected input。
- 恢复：关闭第一个 app lifespan 后，同一 SQLite 文件由新 app 恢复四对象 confirmation/disposition。
- Schema：OpenAPI 包含全部项目与四对象 command request、error 和 project view schemas；继续与生成前端类型保持 drift Gate。
- 验证：A3.1 targeted 4 passed；完整 Python 445 passed/2 skipped；前端 9 passed；Chromium E2E 1 passed；构建与依赖检查通过。
- 边界：A3 在本地 Phase A 范围内关闭；这不批准远程部署安全，也不把 A1/A2 产品字段升级为正式架构。
- 详细记录：[`iterations/2026-09-20-a3-1-http-contract-matrix.md`](iterations/2026-09-20-a3-1-http-contract-matrix.md)

## 2026-09-21 — A5 fake provider 与持久化提案 Job 走通 Product Contract 闭环

- 闭环：浏览器中从一句不完整的话开始，依次得到 ProductIntent、ProblemModel、OutcomeContract 提案，逐个纠正并具名确认，形成带 revision、来源、未知和证据边界的 Product Contract。
- Job 边界：新增 `ProductProposalJob` revision 对象。创建只 enqueue 并 pin 上游 revision，立即返回 `job_id` 而不执行 provider；执行是独立的单步 worker-compatible 命令，提交前后都校验 pinned revision。
- 失败语义：上游变化标 `stale_input` 且不提交输出；provider 异常保存固定安全摘要与 `provider_failed`，已确认状态不受影响；提交后崩溃可在下次 run 时 reconcile；相同输入的重复请求复用同一活跃 Job。
- 持久化：新增 `product_job_revisions` 与 `product_job_current`，沿用 `CREATE TABLE IF NOT EXISTS`；关闭重开后 queued/succeeded/failed/stale Job 与结果 revision 均可恢复。
- 诚实边界：provider 无网络、无研究能力，只转述已确认用户输入；其事实不是外部事实，未知与竞争解释是固定模板，OutcomeContract 的阈值与禁止结果审查必须由人完成。
- 验证：Python 455 passed、2 skipped；前端 10 passed；`npm run build` 成功；Chromium E2E 2 passed（含 axe）；`pip check` 与 `npm audit` 通过。
- 阶段判断：A4/A5 标为 `done`，但 A1/A2 仍是 `prototype tested`，因此 Phase A 不在本批次关闭；新增 A6 作为 Phase A 出口与 Phase B 前置 Gate。
- 详细记录：[`iterations/2026-09-20-a5-fake-provider-product-contract.md`](iterations/2026-09-20-a5-fake-provider-product-contract.md)

## 2026-09-21 — A6 首条数字产品切片校准并关闭 Phase A

- 决定：首条切片锁定为“自主管理工作的知识工作者，在桌面浏览器中保护 25–60 分钟专注时段，同时保留紧急联系控制”。范围排除员工监控、生产力评分、原生移动/硬件和跨团队治理。
- 校准：用该切片复核四对象最小字段、来源/推断/人类决定边界、proposal/confirm 门槛、独立 revision 聚合、`expected_revision` 和 impact 语义；A1/A2 升级为首条切片基线，不宣称是所有 realization pack 的最终架构。
- 人工 Gate：Intent 的价值/隐私/可撤销边界、ProblemModel 的来源事实与至少两个竞争解释、OutcomeContract 的指标/禁止结果/资源/停止条件/现实证据要求必须由人确认；ProductThesis 选择仍需人决定或显式授权。
- 冻结：首条 `OutcomeContract` 目标为可运行 Web 原型；成功阈值仍是待预注册真实任务观察的契约，不是已达成结果。
- 验证：新增 `tests/product/test_a6_first_slice.py`，确定性跑通 Intent → ProblemModel → OutcomeContract 的提案/确认闭环；测试和校准记录不构成真实用户结果证据。
- 阶段判断：A6 完成，Phase A 关闭；Phase B 下一步是围绕冻结 Outcome Contract 生成并比较 2–3 个 Product Thesis。
- 详细记录：[`iterations/2026-09-21-a6-first-slice-calibration.md`](iterations/2026-09-21-a6-first-slice-calibration.md)

## 2026-09-21 — B1 Product Thesis 搜索与人工选择完成

- 新增：在已确认的 ProblemModel/OutcomeContract 上创建 `product_theses` revision-pinned Job；确定性 fake provider 生成三条机制和实现路径有真实差异的 proposal，并保存每条结果 revision。
- 恢复与边界：相同 pinned input 按 fingerprint 幂等；执行前上游变化进入 `stale_input`；部分结果已提交时重试可按稳定 Job reason 协调，不重复生成候选。候选仍是 model proposal，不是研究事实或现实用户结果。
- Web：Product Studio 工作台可以触发批量搜索、比较机制/未知/最低成本证伪/验证层级/维护负担；决策区逐条提供低成本探索授权和人类选择，选择仍走既有 Domain Command。
- 验证：新增 B1 Python/API 测试；Python `pytest -q` 459 passed、2 skipped、2 warnings；前端 `npm test` 11 passed；`npm run build` 成功。未增加真实模型、代码执行、沙箱或现实证据。
- 下一步：关闭 PS-O004，确定单一 Web 技术模板和内容最小化生成契约；在生成代码前另行关闭 PS-O005/PS-O006。
- 详细记录：[`iterations/2026-09-21-b1-product-thesis-search.md`](iterations/2026-09-21-b1-product-thesis-search.md)

## 2026-09-21 — B2 单一 Web 模板与生成契约完成

- 决策：关闭 PS-O004。首条数字产品唯一模板为 `react_typescript_vite_spa`（React + TypeScript + Vite SPA）；不引入 SSR、Next.js、任意框架代码生成或多模板矩阵。
- 契约：新增 `WebProductGenerationContract`，固定页面、关键任务、ready/loading/empty/error/success 等状态、语义内容槽位、本地 fixture/无网络数据边界、输出布局、模板版本和确定性验收检查；依赖 confirmed OutcomeContract 与 exploring/selected ProductThesis revision。
- 工作流：新增 Web generation contract proposal/confirm API 与持久化 Job；工作台可生成并确认契约，并明确显示这不是源码、运行实例或真实结果。
- 验证：Python `pytest -q` 461 passed、2 skipped、2 warnings；前端 `npm test` 11 passed；`npm run build` 成功；Chromium E2E 2 passed。未执行代码生成、依赖安装、沙箱或外部网络。
- 下一步：关闭 PS-O005/PS-O006，定义 workspace 隔离、网络/Secret 边界、预算与失败恢复后再进入 B3。
- 详细记录：[`iterations/2026-09-21-b2-web-template-generation-contract.md`](iterations/2026-09-21-b2-web-template-generation-contract.md)

## 2026-09-21 — B3 受预算约束的 Web 生成 workspace 完成

- 决策：关闭首条切片 PS-O005/PS-O006。生成阶段使用项目/Job 独立 workspace；无网络、无 Secret、不执行生成源码；默认一次尝试、64 文件、1 MiB、60 秒、1 成本单位，超限进入 `budget_exhausted`。
- 新增：`ProductGenerationJob`、预算/沙箱/manifest 值对象、SQLite/InMemory revision 存储和 `/generation-jobs` API；确认后的 Web generation contract 可幂等物化为固定 `react_typescript_vite_spa` 最小源码、fixture、测试和文件 hash manifest。
- 恢复：Job 保存 checkpoint、输入 revision、workspace 相对路径、消耗文件/字节/时间/成本；支持 stale、暂停/恢复/取消、重试预算和 SQLite 重启恢复；路径穿越、符号链接和凭据文件会被拒绝。
- 边界：本批只验证契约到源码 workspace 的确定性软件行为；没有 npm 安装、构建、运行、Playwright、模型费用或真实用户结果证据。
- 验证：Python `pytest -q` 468 passed、2 skipped、2 warnings；新增 `tests/product/test_generation.py` 与 `tests/api/test_generation_jobs.py`；前端 11 tests、production build 通过。
- 下一步：B4 为生成 workspace 建立独立依赖安装、构建、运行和浏览器验证 sandbox，并保持执行权限与生成权限分离。
- 详细记录：[`iterations/2026-09-21-b3-generation-job-workspace.md`](iterations/2026-09-21-b3-generation-job-workspace.md)

## 2026-09-22 — B4 本地执行 sandbox 完成

- 新增：独立 `ProductExecutionJob`、执行预算/沙箱/步骤值对象、SQLite/InMemory 持久化与 `/execution-jobs` API；执行必须 pin 成功的 B3 generation revision，不会由源码生成 Job 隐式触发。
- 执行：在 workspace 完整性、manifest/hash 和固定 package allowlist 复核后，按 install → build → loopback preview → Playwright/axe/截图顺序运行；只使用无 shell 参数数组、最小环境和安全错误摘要。
- UI：工作台增加“构建并验证 workspace”显式入口，展示执行状态与 B4 边界；生成模板补齐固定类型依赖、preview script、Playwright config、error/stop/axe/screenshot 检查。
- 边界：当前是本机 allowlisted subprocess，不是容器/远程多租户隔离；截图是可审查产物而非批准的视觉基线；浏览器环境与真实用户结果仍待验证。
- 验证：`pytest -q` 471 passed、2 skipped、2 warnings；前端 11 tests；`npm run build` 成功；OpenAPI/schema drift 通过。
- 详细记录：[`iterations/2026-09-22-b4-isolated-execution.md`](iterations/2026-09-22-b4-isolated-execution.md)

## 2026-09-22 — B5 受限失败定位与修复闭环完成

- 新增：独立 `ProductRepairJob`、Repair Budget/Attempt/Patch 模型、SQLite/InMemory revision 持久化与 `/repair-jobs` API；Repair Job pin 失败的 B4 Execution Job revision，只接收步骤名、错误码和安全摘要，不保存原始命令输出或 Secret。
- 修复边界：确定性 planner 仅对模板已知的浏览器/axe 或错误状态问题提出白名单 `search/replace` 补丁；路径、源文件 hash、补丁数量/字节和成本均受限，未知失败返回 `unsupported_failure`，不猜测性修改源码，也不修改测试、依赖或脚本。
- Provenance：每次尝试、诊断、补丁、输入 revision、输出 generation/execution Job 和成本均持久化；成功修复写入新的 child generation workspace 和独立 Execution Job，原 B3/B4 workspace 与 revision 保持不可变；`stale_input`、重试、取消和 SQLite 重启恢复均保留状态。
- UI：工作台提供“定位并尝试受限修复”入口，显示 Repair Job 状态、尝试次数与 B5 的确定性修复边界。
- 验证：`pytest -q` 477 passed、2 skipped、2 warnings；前端 `npm test` 11 passed；`npm run build` 成功；Chromium E2E 2 passed；OpenAPI/schema drift 重新生成并通过；B5 targeted `tests/product/test_repair.py` 4 passed。
- 边界：本批关闭本机 deterministic repair 切片；真实模型/远程代码代理、跨框架修复、部署级 OS/container 隔离、视觉回归基线、跨浏览器/移动验证、预览反馈同意和真实用户结果仍待后续。
- 详细记录：[`iterations/2026-09-22-b5-bounded-repair-loop.md`](iterations/2026-09-22-b5-bounded-repair-loop.md)

## 2026-09-23 — B6 可追溯导出交付包完成；B4 首次真实跑通

- 新增：不可变 `ProductDeliveryBundle`、insert-only SQLite 表、`/delivery-bundles` 创建/列表/读取/下载 API 与工作台导出入口；只接受当前成功的 Execution Job revision，生成字节确定、sha256 寻址的 zip（源码、构建物、验证产物、`DELIVERY.md`、`bundle-manifest.json`）。
- 发现：B4 此前所有测试都使用 fake runner，真实执行在本机从未跑通。真实验证暴露并修复了 Windows `SYSTEMROOT` 丢失导致 Node 崩溃、npm user/global config 同路径冲突、预览孤儿进程占用 4173 并可能让下一次执行验证旧 workspace、`tsconfig.tsbuildinfo`/`node_modules/.bin` 被误判为篡改等缺陷，均补了回归测试。
- 验证：`pytest -q` 490 passed、3 skipped、2 warnings；前端 15 passed；Chromium E2E 2 passed；`npm run build` 成功；真实 B3→B4→B6 链路成功（19 文件、78,510 bytes），解压后按 `DELIVERY.md` 构建成功。
- 边界：交付包不提升证据等级（`outcome_evidence_level=none`），未签名、未部署；预览反馈、部署级隔离、视觉基线与跨浏览器仍待后续。
- 下一步：B7 预览与反馈锚点，先关闭 PS-O007。
- 详细记录：[`iterations/2026-09-23-b6-delivery-bundle.md`](iterations/2026-09-23-b6-delivery-bundle.md)

## 2026-09-23 — B7 预览与显式反馈锚点完成；PS-O007 关闭

- 决策：PS-O007 由用户选择“仅显式反馈”——只记录用户主动写下的反馈与锚点，无任何自动采集；逐次同意；提交者可撤回且正文被擦除；证据等级 `user_report`。
- 新增：`PreviewFeedback`（单行、submitted → withdrawn 墓碑）、InMemory/SQLite 存储（`secure_delete`）、预览/反馈/撤回/政策 API，工作台沙箱 iframe 预览 + 反馈表单 + 已提交列表。
- 预览：直接读取 hash 复核的 B6 archive `build/` 条目；CSP `sandbox allow-scripts`、`connect-src 'none'`；为适配 Vite 默认根绝对资源路径，仅在服务时改写 `index.html`，交付包字节不变。
- 验证：`pytest -q` 504 passed、3 skipped、2 warnings；前端 20 passed；Chromium E2E 2 passed；build 成功；真实 B3→B4（43s）→B6→B7 链路：iframe 中生成产品可交互，`fetch` 与父页面访问被阻断，提交需同意、撤回后正文清除，axe 无 serious/critical。
- 边界：不代表任务完成或真实结果；无多用户身份、无基于反馈的迭代、无版本差异。
- 下一步：B8 反馈驱动的迭代与版本差异。
- 详细记录：[`iterations/2026-09-23-b7-preview-feedback-anchors.md`](iterations/2026-09-23-b7-preview-feedback-anchors.md)

## 2026-09-24 — B7m 真实模型源码生成完成；PS-O011/PS-O012 按首条切片关闭

- 决策（用户于 2026-09-23 选择）：DeepSeek 作为首个真实 provider；只发送已确认 Web generation contract；transcript 仅存本机、不入交付包；模型 Job 显式触发、最多 2 次调用、B5 仍为确定性修复。
- 新增：`ProductSourceModel` 端口与 DeepSeek 适配、`materialization_kind=model`、`ModelCallRecord`、源码静态门禁、契约派生 Playwright/axe 测试、source policy/transcript/retry API、工作台模型入口与调用记录、B6 模型 provenance。
- 验证：`pytest -q` 523 passed、3 skipped、2 warnings；前端 22 passed；Chromium E2E 2 passed；build 成功；真实 DeepSeek（1 次调用接受）→B4 全步骤成功→B6 bundle 创建。
- 纠错：B7m 记录的收尾勾选早于实际同步；本条与 CURRENT_STATE/ROADMAP/DECISION_REGISTER 于 2026-09-24 补齐。
- 边界：一次真实链路只证明 provider、门禁、执行与导出在该输入上可运行；不证明模型稳定性、费用可接受或用户结果。
- 详细记录：[`iterations/2026-09-23-b7m-model-source-generation.md`](iterations/2026-09-23-b7m-model-source-generation.md)

## 2026-09-24 — B8 反馈驱动的迭代与版本差异完成；PS-O013/O014/O015 关闭

- 决策（首条切片，记入 DECISION_REGISTER 为暂定方案）：一次一条反馈 → 一条契约提案；pin 当前已确认契约为 baseline；provider 只收反馈 ID/anchor/类别，不收、不写入正文；差异只到文件 sha256 与契约集合 ID；处理状态只由人标记。
- 新增：proposal Job `feedback_id`、`PreviewFeedbackReader`、fake 修订、`PreviewFeedback.disposition` 与可变长 revision 链、`/preview-feedback/{id}/disposition`、`/delivery-bundles/{id}/diff`、工作台迭代入口与差异面板。
- 纠错：首轮实现使所有 proposal job 响应 422（响应 schema 缺字段）并引用不存在的服务；已重写。隐私问题（正文进入不可变契约会破坏撤回即擦除）在实现前拦下。
- 发现：确定性模板不读取验收检查，修订契约生成字节相同的源码与构建；diff 如实显示，测试锁定。
- 验证：`pytest -q` 527 passed、3 skipped、2 warnings；前端 24 passed；Chromium E2E 2 passed；build 成功；无本批专项真实链路。
- 下一步：B9 让反馈迭代真正改变产品，随后 Phase B 出口复核。
- 详细记录：[`iterations/2026-09-24-b8-feedback-driven-iteration.md`](iterations/2026-09-24-b8-feedback-driven-iteration.md)

## 2026-09-24 — B9 迭代改变产品（架构分析）完成；PS-O016 决定模板固定、模型可变

- 决策（首条切片，PS-O016）：确定性模板保持固定行为不消费验收检查，只有模型路径（`source="model"`）才在契约变化时产生不同源码；模板作为稳定回退基线，模型承担"根据需求变化调整产品"职责。
- 架构分析：B7m `contract_payload` (source_model.py:164) 已包含 `acceptance_checks`；B8 修订契约添加验收检查；B3 `source="model"` 传递完整契约给模型（generation.py:595）；组合逻辑证明模型路径可以产生不同结果。
- 测试策略：首条切片依靠架构分析和现有测试组合（B8 模板路径不变 + B7m 模型路径可生成），不添加新的端到端测试（避免 Pydantic 模型构造复杂度）。
- 验证：代码检查确认 `contract_payload` 包含 `acceptance_checks`；B8 test 验证修订契约添加检查；B3 code 验证模型路径传递完整契约；基线测试保持通过（527 passed、3 skipped）。
- 边界：架构分析证明模型**可以**接收修订契约，不证明模型**会**根据验收检查调整代码；模型是否消费验收检查、如何解释它们、稳定性如何，需多次真实运行观察。
- 下一步：Phase B 出口复核，处理部署级 OS/container 隔离、视觉回归/跨浏览器 Gate、真实 provider 输入保留/费用与修复权限。
- 详细记录：[`iterations/2026-09-24-b9-iteration-changes-product.md`](iterations/2026-09-24-b9-iteration-changes-product.md)

## 2026-09-24 — Phase B 出口复核完成并关闭 Phase B

- 触发：B1–B9（含 B7m）已实现并验证；需复核 Phase B 退出门槛是否满足，并决定哪些差距必须在 Phase C 前关闭。
- 退出门槛检查：Phase B 目标为"从模糊意图到可运行 Web 产品、自动测试/修复、反馈和导出全链路可演示且可恢复"——经逐项验证，已满足核心退出条件。
- 已验证能力：Product Contract 工作流（四对象 proposal/correction/confirmation）、Thesis 比较与选择、Web 产品生成（React/TypeScript/Vite）、本地执行与验证（subprocess + Playwright/axe）、受限失败修复（白名单补丁 + generation lineage）、预览与显式反馈（沙箱 iframe + 逐次同意 + 可撤回）、反馈驱动迭代（修订契约 + 版本差异）、可追溯导出（内容寻址交付包）、全链路可恢复（Job 与 revision 重启恢复）。
- 已知差距（可推迟）：真实 provider 接入（Product Contract 与 Thesis 仍用 fake provider）、部署级 OS/container 隔离（当前为本地 subprocess）、视觉回归与跨浏览器 Gate（Chromium only，截图无基线）、真实模型修复（deterministic planner）、交付包签名与部署。
- 决策：Phase B 可以关闭。真实 provider、部署级隔离、视觉回归等差距已明确记录，不影响"可演示且可恢复"这一核心退出条件；继续在 Phase B 实现这些能力会延迟进入 Phase C（真实结果验证），而现实任务观察才是评估产品价值的关键。
- Phase C 前置条件：至少一次从真实 provider 生成的 Product Contract 到真实模型生成的 Web 产品的端到端链路。
- 阶段判断：Phase B 关闭；Phase C 状态改为 `ready`，需先执行 C0（真实 provider 接入）。
- 下一步：创建 `iterations/2026-09-24-c0-real-provider-integration.md`，决定输入保留/预算/费用策略，实现至少一个真实 provider 适配，跑通端到端真实链路。
- 详细记录：[`iterations/2026-09-24-phase-b-exit-review.md`](iterations/2026-09-24-phase-b-exit-review.md)

## 2026-09-25 — C0 真实 provider 与完整纵向链路完成

- 修复了项目 `.env.local` 未被 Python 自动加载、旧 Windows 用户级 DeepSeek key 覆盖项目配置的问题；Product Studio 现在支持本地配置优先读取。
- DeepSeek Product Contract 适配补齐 JSON mode、当前领域 schema 对齐和安全 schema 错误摘要；fake provider 仍保持默认。
- 真实运行成功：ProductIntent → ProblemModel → OutcomeContract → 3 个 ProductThesis → Web generation contract → DeepSeek B7m source → B4 真实 subprocess/Chromium → B6 内容寻址交付包。
- 阶段 6 记录：5 次模型调用，5,788 input tokens，7,824 output tokens，总耗时 100.22 秒；本次失败 0 次。下一步进入 C1 真实任务试用或 C3 多次稳定性评估。
- 详细记录：[`iterations/2026-09-24-c0-real-provider-integration.md`](iterations/2026-09-24-c0-real-provider-integration.md)

## 2026-09-26 — C2 Outcome Contract 指标测量计划完成

- 触发：C0 已证明真实 provider 到 B6 的一次链路可运行；进入 C1 前需要先把 Outcome Contract 的成功指标、禁止结果和停止条件变成可执行的测量计划。
- 新增：`OutcomeMeasurementPlan`、`OutcomeMeasure`、`MeasurementGuardrail` revision 模型；确定性派生函数、来源层/证据上限映射、结构校验和确认阻塞项；InMemory/SQLite derive→submit→confirm→restart。
- 新增 API/UI：`/outcome-measurement-plan/derive`、`/proposals`、`/{measurement_plan_id}/confirmations`，OpenAPI/TypeScript 同步；Evidence 区展示服务端派生的来源层证据上限/可收集性、阈值、缺失处理、矛盾回退、guardrail、样本、同意/撤回和停止条件，并支持修改阈值后确认。
- 决策：PS-O020/PS-O021。`model_interpretation` 不属于测量来源；`runtime_event` measures 与 guardrails 在 PS-O007 下只能 blocked；计划确认不是观察记录，也不提升现实结果证据。
- 验证：确定性 Python 回归 538 passed、3 skipped、2 warnings；前端 26 passed；生产 build 成功；Chromium E2E 2 passed，包含 C2 页面和 critical/serious axe Gate；OpenAPI drift 已重新生成。一次可选的 C0 真实 provider 重复尝试在 B7m 静态门禁因模型漏写契约 screen ID 失败，未把它计入 C2 验收。
- 边界：C2 没有招募参与者，也没有写入 `MeasurementObservation`/`EvidenceReview`；当前下一最小工作包为 C1 真实任务试用或 C3 多次真实链路稳定性评估。
- 详细记录：[`iterations/2026-09-25-c2-outcome-measurement-plan.md`](iterations/2026-09-25-c2-outcome-measurement-plan.md)

## 2026-09-26 — C1 真实任务观察预案完成；实施等待 D1/D2/D3 决策

- 核对：C2 `OutcomeMeasurementPlan` 目前只是 Product 计划；Experience `OutcomeObservation` 尚没有类型化的 C2 plan/B6 delivery/consent pin，也没有经 Product API 暴露的 intake。`ParticipantRecord` 仅有可选 `consent_scope_revision_id`，不是 consent receipt；withdrawal/物理擦除语义不足。
- 预案：明确人工主持、随机 participant ID、逐次同意、手动 observation、计划/measure/delivery/consent provenance、具名人工 Review 和 source ceiling 的最小 C1 流程。禁止自动事件采集、模型代审或把 C2 plan 当结果。
- 待决：PS-O022 同意/数据最小化/撤回与保留；PS-O023 Product↔Experience object/store/transaction/recovery 边界（PS-O010 仍 open）；PS-O024 EvidenceReview 人工角色与 ceiling mapping。
- 决策前边界：没有新增 C1 schema/API/UI/数据、没有招募参与者；Roadmap 的 C1 改为 `decision required`，C3 可独立先行。
- 详细预案：[`iterations/2026-09-26-c1-outcome-observation-intake.md`](iterations/2026-09-26-c1-outcome-observation-intake.md)。

## 2026-09-26 — C3 多次真实链路稳定性评估完成

- 将 C0 单次真实 provider 链路扩展为显式 opt-in、顺序执行、最多 10 次的稳定性 runner；每次完成 Product Contract → deterministic Web contract → B7m source=model → B4 → B6 后清理原始 workspace/transcript，汇总只保留白名单字段。
- 新增 `src/psyteardown/product/stability.py`：只保留阶段状态、错误码、provider/model、调用数、token、耗时和 B6 archive 摘要，禁止项目 ID、prompt、response、原始错误进入汇总报告；100 次模型调用为本批硬上限，金额保持 unavailable。
- 2026-09-26 完成 10 次评估：7 次完整通过 B6，3 次失败（`model_output_rejected`、`command_failed`、`provider_schema_invalid` 各 1 次）；总 36 次模型调用，42,194 input / 60,844 output tokens，总耗时 577.78 秒。C3 评估完成，但稳定性不是 10/10，需处理失败类别后再决定是否复测。

## 2026-09-26 — C3 有界重试复测完成

- 在不改变正常产品默认行为的前提下，C3 runner 增加每阶段最多一次显式有界重试、每 run 300 秒 killable timeout、逐次脱敏 checkpoint，并修正 ProductThesis prompt 的 realization mode allowlist。
- 第二轮 10 次真实链路评估中 8 次完整通过 B6；2 次 B4 `command_failed` 未恢复，2 次 `provider_schema_invalid` 经有限重试恢复；总 52 次模型调用，58,850 input / 86,279 output tokens，总耗时 746.48 秒。
- 结论：C3 的评估任务完成，但稳定性尚不能声称通过；下一最小工作包是获取 B4 command failure 的阶段级安全诊断并修复/复测，C1 仍需独立的产品决策。

## 2026-09-26 — C3 B4 阶段诊断复测未完成

- B4 runner 增加浏览器命令失败的安全阶段码 `browser_command_failed`，并保证 combined preview/browser runner 在 browser 失败时保留 `run` 成功、`browser` 失败的步骤状态；新增确定性测试。
- R3 真实诊断样本执行 6/10 后安全停止：4 次完整成功，1 次 `browser_command_failed`，1 次 `run_timeout`；25 次模型调用，28,430 input / 41,806 output tokens，记录耗时 725.40 秒。
- 结论：诊断粒度提高，但 C3 仍未稳定通过；不将不完整 R3 样本计作通过率，后续需对 browser failure 和 timeout 做独立修复/复测。

## 2026-09-26 — B4 浏览器失败安全分类补齐

- B4 不保留浏览器原始输出，但现在会把其安全地归类为 `browser_assertion_failed`、`browser_accessibility_failed`、`browser_launch_failed` 或 `browser_timeout`；无法分类时保留 `browser_command_failed`。
- 新增本地测试覆盖分类白名单和“不保留原始输出”边界；尚未用该分类启动第四轮真实 provider 评估。

## 2026-09-26 — C3 B4 诊断本地 Gate 完成

- 修正：B4 浏览器命令现在将非零退出、启动失败和超时映射为安全分类；`browser_timeout` 严格使用剩余执行预算，不再被额外的最小 1 秒延长。
- 边界：本地测试明确区分 B4 `browser_timeout` 与 C3 进程级 watchdog 的 `run_timeout`；缺失浏览器命令归类为 `browser_launch_failed`，原始浏览器输出不进入持久化错误摘要。
- 验证：`pytest -q tests/product/test_execution.py tests/product/test_stability.py` → 21 passed、1 warning；完整确定性回归 `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py` → 551 passed、3 skipped、2 warnings。
- 结论：本地诊断 Gate 通过，但不产生新的真实 provider 成功率；没有启动第四轮付费评估，C3 仍保持 `in progress`。

## 2026-09-26 — C3 R4 有界复测通过

- 复测：在 B4 安全诊断本地 Gate 通过后，按原有 100 次调用硬上限执行 `python scripts/run_c3_real_provider_stability.py --output-root output/product-studio/c3-stability-r4`。
- 结果：10/10 次真实 `Product Contract → deterministic Web contract → B7m source=model → B4 → B6` 完整通过；50 次模型调用，57,724 input / 83,183 output tokens；金额保持 unavailable，不作推断。
- 修复：10 次链路完成后 Windows raw 清理遇到并发消失文件，C3 runner 清理器改为对受保护 raw 根内的 `FileNotFoundError` 幂等，其他错误仍失败关闭。
- 结论：C3 本批评估 Gate 通过并关闭；R1/R2/R3 失败样本、B4 诊断分类和“非生产级保证”边界继续保留。


## 2026-09-26 — C1 本地观察接入 backend slice

- 按 D1/D2/D3 冻结首批本地边界：`c1-local-v1` 显式 consent、随机 participant ID、结构化手工 measure、无自动遥测/模型输入、具名且与 host 分离的 reviewer；`research_observation` ceiling 为 `observed`。
- 新增 Product-side `C1TrialEnvelope`、consent receipt、participant/presentation、manual `C1OutcomeObservation`、`C1EvidenceReview` 和 withdrawal tombstone；专用 InMemory/SQLite adapter 支持原子写入、重启恢复和 source-row hard-delete。
- 新增 `/api/v1/c1-policy` 与 C1 envelope/participant/presentation/observation/withdrawal/review HTTP 命令和查询，更新 OpenAPI/生成类型；不写既有 Experience observation store，不把 B7 `user_report` 自动转换成 C1。
- 验证：C1 API 2 passed；Product/API 回归 147 passed、1 skipped；尚未招募或收集真实参与者，不能声明现实结果证据。

## 2026-09-26 — C1 主持面板补齐与工作包台账校正

- C1：在已有 Product-side intake/API 之上接入 Evidence 区主持面板，按同意、随机 participant ID、task presentation、结构化 observation、人工 review/withdrawal 的顺序操作；非成功路径保留 `value=null` 和人工 completion cause，review UI 每次只提交一个 observation/measure。
- 验证：新增 `studio/src/views/C1Panel.test.tsx`，覆盖无当前交付时的启动 Gate、非成功路径值边界和单条人工 review；C1 API 2 passed、C1 UI 2 passed、前端全量 28 passed、production build 成功。
- 证据边界：仍未招募或收集真实参与者，未产生现实结果证据；同意文案、访问者名单和外部备份说明仍待负责人具名审阅。
- 台账校正：发现近期记录把生命周期状态和阶段性验证结果混写，新增 [`工作包记录格式与状态语义校正`](iterations/2026-09-26-work-package-record-normalization.md)，并在 README/CURRENT_STATE/ROADMAP 统一当前解释；不静默改写已关闭历史记录。
- 下一步：C1 人工演练与负责人发布 Gate。

## 2026-09-26 — C1 改为负责人本地自试，不设独立演练 Gate

- 范围校正：对本地主持、单用户首轮，不再要求负责人先做一轮非参与者人工演练；负责人直接作为首位真实参与者完成自试，同时覆盖真实任务观察和主持流程。
- 证据边界：N=1 是真实的本地探索性观察，但当前 C2 计划的 `minimum_n=3` 尚未满足，不能据此声称目标人群效果或泛化结论。
- 保留边界：`c1-local-v1`、最小数据、撤回/保留和不采集遥测的规则不变；EvidenceReview 等级提升仍要求与 host 分离的具名 reviewer。没有分离 reviewer 时，观察可以保留但必须保持未 review。
- 下一步：负责人完成一次本机自试；之后由独立 reviewer 审阅，或将该记录明确保留为未 review observation。
- 详细记录：[`C1 负责人自试与非参与者演练 Gate 范围校正`](iterations/2026-09-26-c1-self-pilot-scope-correction.md)

## 2026-09-26 — 明确重复自试 session 不等于多个用户

- 负责人可以在本地做多次真实任务或多次 task presentation；这些是多个真实 session/observation，但 participant 仍为同一个人，应按 `participant_n=1, session_k>=1` 记录。
- 重复 session 可用于观察流程可用性、重复性、学习效应和疲劳效应；不能满足当前 C2 计划的 participant `minimum_n=3`，也不能支持多个用户或目标人群的泛化效果声明。
- 若以后要把“session”而不是“participant”作为样本单位，必须通过 C2 MeasurementPlan 的人工 revision/confirm 明确修改 sample plan，不能在 C1 记录中默默改变 N 的含义。


## 2026-09-27 — C1 主链路收敛与真实模型生成韧性补强

- 暂缓下一轮真实自试，先修复“流程跑通但不知道得到了什么”的产品问题。
- Product Studio 新增主链路引导、真实 provider 显式选择、proposal 失败/过期后一键重试，以及 Web 契约的 `primary_flow_task_ids`。
- 首条 bounded flow 收敛为：具体任务 → 10 分钟专注 session → 非紧急打断决策 → 回到任务并完成 → 看见延后事项。
- B7m 静态 Gate 与契约派生浏览器测试增加 primary flow step 检查；确定性全量回归保持 553 passed、3 skipped。
- 这些是软件边界改进，不是新的现实结果证据。


## 2026-09-27 — C1 真实体验验证前的本地体验约束补强

- 按当前优先级暂缓 C1 真实参与者/负责人真实体验验证，先处理本地使用中断风险。
- 新增项目列表/最近工作区恢复；浏览器关闭后，工作区显示未完成 proposal/generation/execution Job 并提供继续入口。
- 暴露 generation 暂停/继续/取消、execution 停止/重试控制；明确这些是客户端状态控制，不等同于常驻 worker 或即时进程终止。
- 为 `product_intent` 原始输入增加 4000 字符服务端/前端上限和计数；B4 预览端口在 4173 占用时回退到可用 loopback 端口并同步传给 Playwright。
- 验证：前端 28 passed、production build 成功；确定性 Python/API 回归 556 passed、3 skipped；本批不产生 C1 参与者数据或现实结果证据。


## 2026-09-27 — 本地主链路恢复 Gate 通过

- 在真实体验验证继续暂缓的前提下，完成一次确定性本地复核：新建项目默认走 deterministic fake，不要求本机配置 DeepSeek；真实 provider 仍可在 Product Contract 区显式选择。
- Chromium E2E 新增并通过工作区恢复场景：预置 queued proposal，回到首页从最近工作区进入，点击“继续这项工作”后恢复并完成 proposal。
- 修复主链路引导新增状态的 axe serious color-contrast 问题；当前 Chromium E2E 共 3/3 通过。
- 这仍是软件恢复/可用性证据，不是 C1 参与者观察或现实结果证据。


## 2026-09-27 — C1 暂停门禁、独立审查与中断 Job 恢复

- C1 真实体验验证继续暂缓，并由 API/UI 双边界执行：`PSYTEARDOWN_C1_TRIAL_ENABLED` 默认关闭，暂停期间不能创建 trial envelope。
- reviewer 不再使用 `named-reviewer` 默认占位；服务端拒绝常见占位名，并继续要求 reviewer 与 host 分离。
- `running` Execution Job 增加显式 orphan recovery；恢复要求调用方确认旧进程已中断风险，再回到 queued。
- 本批仍不产生 C1 参与者数据或现实结果证据。
