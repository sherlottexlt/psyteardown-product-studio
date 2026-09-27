# Product Studio 决策登记册

- 建立日期：2026-09-20
- 校正日期：2026-09-20（新旧 ADR 适用范围校正）
- 用途：区分 North Star 已明确的方向、代码原型采用的假设，以及尚需用户场景验证的待决问题

## 权威边界

`docs/adr/` 的旧条目属于它们原本针对的拆解、体验和工程内核；`accepted` 不代表自动适用于新平台。North Star §16 保留旧计划作为可信研发内核基线，§11 只明确重申了部分 API/UI 技术方向。原型代码和测试证明实现行为，不等于产品决策获得批准。2026-09-20 误建的 7 篇新 ADR 已删除，改在本文件记录待验证假设。

## North Star 已明确的方向

| ID | 状态 | 方向 | 来源 | 影响 |
|---|---|---|---|---|
| PS-D001 | accepted | 产品北极星是 AI Product Studio | [North Star §0–2](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 优先走通真实用户结果闭环 |
| PS-D002 | accepted | 主要用户形态是对话驱动、成果物中心的 Web 工作空间；CLI/MCP 是辅助入口 | [North Star §4、§10](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 不以 CLI 流程取代用户主体验 |
| PS-D003 | accepted | 首条完整纵向切片是数字/Web 产品 | [North Star §13](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 硬件和企业能力不并行扩张 |
| PS-D004 | accepted | 旧体验、证据、revision 与工程 Gate 作为可信研发内核保留 | [North Star §0、§9、§16](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 旧内核继续有效，但其原有 ADR 不自动约束新对象 |
| PS-D005 | accepted | 当前阶段采用 React/TypeScript/Vite 与 FastAPI `/api/v1`；领域写逻辑留在 Python | [North Star §11.1](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 技术方向已定，具体 HTTP DTO/错误格式仍需验证 |
| PS-D006 | accepted | 模型输出默认是 proposal，状态由命令与 revision 转换 | [North Star §12.1](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 聊天记录不能充当唯一项目状态 |
| PS-D007 | accepted | 本地第一阶段继续 SQLite、内容寻址资产、持久化单 Worker | [North Star §11.1](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 未决定上位域是否使用独立 `product_*` 表 |
| PS-D009 | accepted | 交付成熟度和证据边界必须显式，不允许伪完成 | [North Star §8](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md) | 软件测试、仿真不能证明真实用户结果 |

## 原型假设，不是已接受决策

| ID | 状态 | 当前代码采用的假设 | 证据 | 复核点 |
|---|---|---|---|---|
| PS-H001 | calibrated_for_first_slice | 四对象使用当前不可变字段与 proposed/confirmed 状态机 | [A1 记录](iterations/2026-09-20-a1-upper-domain-contracts.md)、[A6 校准](iterations/2026-09-21-a6-first-slice-calibration.md)、`src/psyteardown/product/models.py` | 新用户类型或 realization pack 出现时复核 |
| PS-H002 | calibrated_for_first_slice | ProblemModel 确认需至少两个竞争解释，OutcomeContract 确认需指标/停止条件等 | [A1 记录](iterations/2026-09-20-a1-upper-domain-contracts.md)、[A6 校准](iterations/2026-09-21-a6-first-slice-calibration.md) | 真实任务试用后复核用户负担与信息增益 |
| PS-H003 | calibrated_for_first_slice | ProductProject 与四对象使用独立 revision 聚合 | [A2 记录](iterations/2026-09-20-a2-project-application-service.md)、[A6 校准](iterations/2026-09-21-a6-first-slice-calibration.md) | 跨域 realization 或多方协作出现时复核 |
| PS-H004 | calibrated_for_first_slice | 上位域使用独立 `product_*` SQLite 表 | [A2 记录](iterations/2026-09-20-a2-project-application-service.md)、[A6 校准](iterations/2026-09-21-a6-first-slice-calibration.md) | 实测并发、跨域事务或迁移需求出现时复核 |
| PS-H005 | prototype_only | A1/A2 测试使用手工结构化输入和确定性数据，未接真实模型 | [A1/A2 测试](../../tests/product/test_service.py) | 只能验证代码路径，不能替代模型行为或真实用户闭环 |
| PS-H006 | prototype_tested | A3 使用薄 FastAPI command/projection adapter、统一 HTTP 错误格式和 SQLite lifespan | [A3/A3.1 记录](iterations/2026-09-20-a3-1-http-contract-matrix.md)、`tests/api/` | Phase A HTTP matrix 已完成；A5 新 provider/job 边界仍需独立验证 |
| PS-H007 | prototype_tested | A4 使用独立 `studio/` SPA、TanStack Query、OpenAPI 生成 transport types 和五区 projection；冲突刷新权威 revision 但保留草稿、不自动 merge | [A4/A4.1 记录](iterations/2026-09-20-a4-1-contract-correction-and-browser-gates.md)、`studio/src/` | A5 已确定 ProblemModel/OutcomeContract 的最小纠正交互；是否需要持久化离线草稿仍未决 |
| PS-H008 | prototype_tested | A5 的 proposal 工作以持久化 revision Job 表达：创建只 enqueue 并 pin 上游 revision，执行是独立单步命令；相同 (project, kind, pinned deps, provider, version, raw_input) 复用同一活跃 Job；失败分流为 `stale_input`/`provider_failed`/`proposal_commit_conflict`，Job 存 `product_job_revisions` + `product_job_current` | [A5 记录](iterations/2026-09-20-a5-fake-provider-product-contract.md)、`src/psyteardown/product/jobs.py`、`tests/product/test_jobs.py` | 接入真实 provider 与常驻 worker 时复核：claim 语义、fingerprint 幂等是否阻碍多候选提案、原始输入保留边界与预算/取消 |
| PS-H009 | prototype_tested | B1 将 thesis 搜索建模为一个 `product_theses` batch Job，创建时固定 3 个结果 ID，结果仍逐个写入 `ProductThesis` aggregate；同一 fingerprint 复用，worker 重试通过稳定 job reason 协调已提交结果 | [B1 记录](iterations/2026-09-21-b1-product-thesis-search.md)、`src/psyteardown/product/jobs.py`、`tests/product/test_jobs.py` | 首次跨 aggregate 真实生成或需要部分失败恢复时复核；不视为通用工作流/原子事务架构 |
| PS-H010 | prototype_tested | B2 用 `react_typescript_vite_spa`（React + TypeScript + Vite SPA）作为首条数字产品唯一模板；运行时只允许 React/ReactDOM、本地 fixture、无网络；生成输入以页面/任务/状态/内容槽位/确定性检查表达，不是源码或执行授权 | [B2 记录](iterations/2026-09-21-b2-web-template-generation-contract.md)、`src/psyteardown/product/models.py`、`src/psyteardown/product/providers.py`、`tests/product/test_jobs.py` | B3 首次真实生成后复核页面/状态字段、锁文件和依赖范围；不替 PS-O005/PS-O006 提供批准 |
| PS-H011 | prototype_tested | B5 将失败执行建模为独立 `ProductRepairJob`：只消费 B4 的安全步骤/错误摘要；确定性 planner 仅产生固定模板白名单路径上的精确 hash 校验补丁；补丁写入新的 child generation lineage 并由新的 Execution Job 验证，原 B3/B4 revision 不可变；每次尝试、补丁、输入 revision、成本和安全错误摘要持久化 | [B5 记录](iterations/2026-09-22-b5-bounded-repair-loop.md)、`src/psyteardown/product/repair.py`、`tests/product/test_repair.py` | 接入真实 provider、扩展失败类别或跨框架修复时复核：原始日志/输入保留、人工审批、自动应用权限、费用预算与部署级隔离；本假设不等于允许任意代码代理 |

| PS-H012 | prototype_tested | B6 将导出建模为同步、不可变的单 revision `ProductDeliveryBundle`（而非 Job）：只接受当前成功的 Execution Job revision；按 (project, execution revision, format) 幂等；zip 字节确定并以 sha256 寻址，下载前复核；不含 lockfile/node_modules；`outcome_evidence_level` 固定为 `none` | [B6 记录](iterations/2026-09-23-b6-delivery-bundle.md)、`src/psyteardown/product/delivery.py`、`tests/product/test_delivery.py` | 包体超出本地同步打包预算、需要签名/发布渠道或多人交付审批时复核 |

| PS-H013 | prototype_tested | B7 预览只读 B6 archive 中逐文件 hash 复核的 `build/` 条目，放在 CSP `sandbox allow-scripts`（无 same-origin、`connect-src 'none'`）的 iframe 中；`PreviewFeedback` 每条只存一行、最多两个 revision（submitted → withdrawn 墓碑），撤回覆盖而非追加历史，SQLite 开启 `secure_delete`，以兑现“撤回即擦除”；锚点按 bundle pin 的契约 revision 校验 | [B7 记录](iterations/2026-09-23-b7-preview-feedback-anchors.md)、`src/psyteardown/product/feedback.py`、`tests/product/test_feedback.py` | 需要反馈编辑、多人审阅、远程分享预览或保留期限策略时复核 |

| PS-H015 | prototype_tested | B8 反馈迭代复用 proposal Job：反馈按身份 pin（处理状态变化不致 stale，撤回致 `stale_input`）；反馈 revision 链为 r1 submitted → 处理状态 revision → 撤回墓碑（当前 +1）；fake 修订保留全部 baseline ID 只追加一条验收检查 | [B8 记录](iterations/2026-09-24-b8-feedback-driven-iteration.md)、`src/psyteardown/product/{jobs,feedback,delivery}.py`、`tests/api/test_feedback_iteration.py` | 模板开始消费验收检查或模型参与迭代时复核 |

| PS-H014 | prototype_tested | B7m 让模型只写 `src/App.tsx` 与 `src/styles.css`，其余模板固定；模型输出须严格为一个 TSX + 一个 CSS fenced block，经静态门禁（import 白名单、禁止网络/存储/父窗口/动态代码/外链、尺寸上限、契约 ID 必须出现）；浏览器测试从契约确定性派生（`data-screen-*`/`data-task-id`/`data-slot-id`/唯一 `role="status"`），不由模型编写 | [B7m 记录](iterations/2026-09-23-b7m-model-source-generation.md)、`src/psyteardown/product/source_model.py`、`tests/product/test_source_model.py` | 多模型比较、稳定性评测、允许模型写更多文件或接入模型修复时复核 |

| PS-H016 | prototype_tested | B9 架构分析确认：B8 修订契约可选 `source="model"`，B3 `_model_files` 通过 `contract_payload` 将包含新验收检查的契约发送给模型；首条切片依靠现有测试组合而非新的端到端测试 | [B9 记录](iterations/2026-09-24-b9-iteration-changes-product.md)、`src/psyteardown/product/source_model.py` line 164、`src/psyteardown/product/generation.py` line 595 | 模型是否消费验收检查、如何解释它们、稳定性如何，需多次真实运行观察 |

这些行只说明已经写出什么，不能作为后续工作的强制约束；应先做一条代表性用户流程，再决定保留、修改或移除。

## 当前产品问题与决策状态

| ID | 状态 | 问题 | 决策时点 |
|---|---|---|---|
| PS-O001 | decided | 自主管理工作的知识工作者，在桌面浏览器中保护 25–60 分钟专注时段，同时保留紧急联系控制 | [A6 首条切片校准](iterations/2026-09-21-a6-first-slice-calibration.md)；Phase B 生成 Product Thesis；扩展到其他用户/场景时重新打开 |
| PS-O002 | decided_for_first_slice | 四对象最小字段、状态和聚合边界按上述单人 Web 切片冻结；不宣称为最终通用 schema | [A6 首条切片校准](iterations/2026-09-21-a6-first-slice-calibration.md)、`tests/product/test_a6_first_slice.py`；真实任务试用、多方协作或新 realization pack 出现时复核 |
| PS-O003 | decided_for_first_slice | Intent 价值边界、ProblemModel 事实/竞争解释、OutcomeContract 结果/风险/资源/停止条件必须由人确认；proposal 和来源只能提供候选 | [A6 首条切片校准](iterations/2026-09-21-a6-first-slice-calibration.md)、`tests/product/test_a6_first_slice.py`；真实任务试用后复核确认负担；Thesis 选择仍需人决定或显式授权 |
| PS-O011 | decided_for_first_slice（仅 B3 源码生成） | 真实模型只接收人已确认的 Web generation contract（标题/页面/任务/状态/槽位/验收检查），不发送原始输入、Intent、ProblemModel、OutcomeContract 或 Thesis；每次调用请求/响应全文只保存在 workspace 外的本机 transcript 目录，Job 记录 sha256，transcript 不进入交付包 | 用户于 2026-09-23 选择；[B7m 记录](iterations/2026-09-23-b7m-model-source-generation.md)。Product Contract 链路换真实 provider、保留期限或多租户前重新打开 |
| PS-O004 | decided | 首条切片唯一允许生成 `react_typescript_vite_spa`；本地 fixture、无网络、固定输出布局与语义内容槽位 | [B2 记录](iterations/2026-09-21-b2-web-template-generation-contract.md)；B3 首次真实生成后复核 |
| PS-O005 | decided_for_first_slice | B3 生成阶段使用项目/Job 独立 workspace；拒绝路径穿越、符号链接、凭据文件；无网络、无 Secret、不执行生成源码。依赖安装、构建、运行另由 B4 sandbox 决策。 | [B3 记录](iterations/2026-09-21-b3-generation-job-workspace.md)；B4 执行 sandbox 前复核 |
| PS-O006 | decided_for_first_slice | B3 默认一次尝试、最多 64 文件、1 MiB、60 秒、1 成本单位；重试/暂停/恢复/取消持久化且不得越过上限，超限进入 `budget_exhausted`。模型/工具真实费用预算仍待 provider 接入。 | [B3 记录](iterations/2026-09-21-b3-generation-job-workspace.md)；真实 provider 接入前复核 |
| PS-O007 | decided_for_first_slice | 仅记录用户主动提交的反馈：锚点（bundle/execution/contract revision + screen/可选 task/state）、类别、文本、提交者、时间；不采集点击/导航/输入/录屏/截图/停留；每次提交显式同意 `b7-explicit-v1`；提交者可撤回，撤回擦除正文与类别；证据等级 `user_report` | 用户于 2026-09-23 选择；[B7 记录](iterations/2026-09-23-b7-preview-feedback-anchors.md)；多用户、远程试用或 Phase C 任务测量前复核 |
| PS-O013 | decided_for_first_slice | 人一次选择一条 submitted 反馈，触发一条 `web_generation_contract` proposal Job（可选 `feedback_id`）；不做聚合、批量或独立”改进意图”对象 | [B8 记录](iterations/2026-09-24-b8-feedback-driven-iteration.md)；多用户或多条反馈合并时复核 |
| PS-O014 | decided_for_first_slice | 迭代 Job pin 当前已确认契约为 baseline 并修订同一 contract 聚合；provider 只收反馈 ID/anchor/类别，**不收也不写入反馈正文**；结果仍需人确认 | [B8 记录](iterations/2026-09-24-b8-feedback-driven-iteration.md)；接入模型迭代前复核是否需要发送正文及其撤回语义 |
| PS-O015 | decided_for_first_slice | 版本差异只比较记录的文件 sha256 与契约集合 ID 级变化；反馈处理状态 `pending/incorporated/deferred` 只由人显式标记，撤回时清空 | [B8 记录](iterations/2026-09-24-b8-feedback-driven-iteration.md)；需要逐行/视觉差异时复核 |
| PS-O016 | decided_for_first_slice | 确定性模板保持固定行为不消费验收检查，只有模型路径（`source=”model”`）才在契约变化时产生不同源码；模板作为稳定回退基线，模型承担”根据需求变化调整产品” | [B9 记录](iterations/2026-09-24-b9-iteration-changes-product.md)；模板需要可配置行为或模型稳定性足够替代模板时复核 |
| PS-O008 | open | 哪些实测需求触发 SQLite/单 Worker 迁移？ | 后续架构评审前 |
| PS-O009 | open | 平台名称继续使用 psyteardown 吗？ | 对外试用前 |
| PS-O010 | open | 新对象与旧体验/工程内核如何共享来源、revision 和存储事务？ | 跨域实现前 |
| PS-O012 | decided_for_first_slice（仅 B3 源码生成） | 模型 Job 必须由人显式触发；输出先过静态门禁才写入 workspace，再经 B4 真实验证才能导出；每 Job 最多 2 次调用，重试只回传上一轮门禁拒绝原因；B5 修复仍为确定性白名单、不调用模型；费用只记调用次数/token，不做金额核算 | 用户于 2026-09-23 选择；[B7m 记录](iterations/2026-09-23-b7m-model-source-generation.md)。模型修复、跨框架修复或金额预算前重新打开 |
| PS-O017 | decided_for_c0 | Product Contract provider（Intent/ProblemModel/OutcomeContract）输入保留策略：与 B7m 一致，完整发送已确认上游对象 + 用户输入，transcript 仅存本机，不入交付包；不提供自动删除，由用户管理项目目录 | [C0 记录](iterations/2026-09-24-c0-real-provider-integration.md)；Phase D 多用户/托管版本时重新打开 |
| PS-O018 | decided_for_c0 | Product Contract provider 预算与费用计量：每对象最多 2 次调用（与 B7m 一致）；项目级无累计限制；费用只记调用次数/token，不做金额核算 | [C0 记录](iterations/2026-09-24-c0-real-provider-integration.md)；Phase D 多用户/托管版本或金额预算需求出现时重新打开 |
| PS-O019 | decided_for_c0 | Product Contract provider 失败重试策略：不自动重试，失败立即返回 `provider_failed`，由用户显式重试（通过 Job retry API） | [C0 记录](iterations/2026-09-24-c0-real-provider-integration.md)；真实使用反馈或高频限流/网络错误出现时复核 |
| PS-O020 | decided_for_c2 | 测量计划的来源层固定为 `software_check`、`runtime_event`、`user_report`、`research_observation`、`expert_review`；`model_interpretation` 永远不是测量证据。每层声明证据等级上限；在 PS-O007 仍有效时，`runtime_event` measures 与 guardrails 均只能以 blocked 状态声明。C2 计划是“如何测量”的计划元数据，不会提升 Outcome Evidence | [C2 记录](iterations/2026-09-25-c2-outcome-measurement-plan.md)；C1 真实任务试用或自动事件采集授权前复核 |
| PS-O021 | decided_for_c2 | 首条切片的测量计划由确定性派生生成候选；每条 SuccessIndicator 必须被覆盖，每个禁止结果必须有 guardrail，所有 stop condition 必须被引用；确认要求至少一个当前可收集的真实世界测量、唯一主测量、非空且非占位的具体阈值，以及明确样本/同意/撤回范围。结果矛盾时可回退到 `product_thesis`、`outcome_contract` 或 `problem_model` | [C2 记录](iterations/2026-09-25-c2-outcome-measurement-plan.md)；C1 试用协议或多指标/多条件研究前复核 |
| PS-O022 | decided_for_first_c1_slice | 本地主持小试用采用 `c1-local-v1`；只记录随机 participant ID、结构化 measure 值、任务状态和人工时间；访问者为本地主持与具名 reviewer；最多保留 30 天；不保留 C1 匿名聚合；撤回删除 C1 source rows/audit rows 并保留无内容 tombstone。SQLite 开启 `secure_delete`，尝试 WAL truncate；外部备份不作物理擦除承诺 | [C1 实施记录](iterations/2026-09-26-c1-outcome-observation-intake.md) D1；远程/企业招募前重新审阅 |
| PS-O023 | decided_for_first_c1_slice | C1 首批采用 Product-side typed intake aggregate 与专用 SQLite 表，不写既有 Experience Observation/Review；C1 application service 是唯一写边界，先校验 confirmed C2 plan + current Web contract + verified B6 pins，再原子写入；跨域投影另行决策，PS-O010 仍 open | [C1 实施记录](iterations/2026-09-26-c1-outcome-observation-intake.md) D2；Experience 投影或跨域事务前重新审阅 |
| PS-O024 | decided_for_first_c1_slice | reviewer 必须具名人工且与 host 分离；C1 仅接受 `research_observation`，ceiling 为 `observed`；只有 accepted/modified review 可提升至 `exploratory`/`observed`，非成功路径不得提升；首批不自动修改 Thesis/Contract | [C1 实施记录](iterations/2026-09-26-c1-outcome-observation-intake.md) D3；多指标研究或自动投影前重新审阅 |

## 记录维护规则

1. 新平台方向优先引用 North Star；旧 ADR 仅在其原范围内引用，并明确是否被 North Star 重申。
2. 可回退的实现先写 iteration 的假设与验证；不因实现先行就把设计标记为 `accepted`。
3. 对影响数据迁移、安全或跨域约束的长期选择，等具体用户场景或原型证据足够时再决定是否编写新 ADR。
4. 不再沿用旧 ADR 递增编号作为新平台实施任务清单；旧文件不批量删除，本次只移除误建的新文件。
