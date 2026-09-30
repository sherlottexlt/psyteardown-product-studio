# Product Studio 使用反馈与待共同解决问题

- 建立日期：2026-09-28
- 状态：Active
- 用途：记录实际使用中暴露的困惑、阻碍和需求，供负责人之后与助手共同复核、排序和解决
- 边界：这是待确认的问题清单，不是已批准的产品方案、承诺或路线图；描述当前行为时尽量链接代码/文档，不能把推测写成事实。

## 记录规则

- 新问题可以持续追加，不要求本清单现在就完整。
- 用户的原话/情境、已复核的当前行为、尚待讨论的方向分开记录；不得把建议自动当作用户决策。
- `Open` 表示尚未共同讨论和定范围；之后可改为 `Triaged`、`Planned`、`Resolved` 或 `Won't do`，并链接对应决定、实现和验证证据。
- 同一问题的状态变化保留简短日期记录；解决问题不等于它背后的产品决策已获批准。
- 这份清单聚焦 Product Studio 本身的使用体验与工作流，不把生成产品的领域需求混入平台缺陷。

## 2026-09-28 首轮使用反馈

### PS-U001 — 中文项目的 fake 提案出现英文内容，语言一致性不明

- 状态：`Resolved`（2026-09-28：新生成的 fake Intent / Problem / Outcome / Thesis / Web contract 会跟随中文输入；既有 revision 不自动翻译）
- 观察到的情境：以中文描述新项目后，“受到影响的人”出现英文占位内容，之后 fake 生成的问题模型等也有英文固定文本；用户因此怀疑后续内容为何都为英文。
- 已复核的当前行为：新建项目默认使用 `deterministic_fake`，但现在可在首页明确选择 `fake` 或 `real`。fake provider 会根据中文输入生成中文的 affected people、Problem、Outcome、Thesis 和 Web contract 固定文案。切换 provider 不会自动翻译已经存在的 revision。
- 证据：`studio/src/views/NewProject.tsx`；`src/psyteardown/product/providers.py`；`studio/src/views/ContractView.tsx`；`src/psyteardown/product/contract_model.py`。
- 当前处理：本轮先让 fake provider 的新提案跟随输入语言；语言仍不是独立的项目级设置，已有提案仍需由用户明确重生成/修订，不做隐式翻译。
- 注意：切换真实 provider 会按当前 C0 策略把完整原始输入及已确认上游对象发送到 provider；需与本地 fake 的隐私差异一并呈现，不能只为解决语言问题而隐式外发。

### PS-U002 — 第一次提案前无法选择 provider，fake/real 的适用阶段容易误解

- 状态：`Resolved`（2026-09-28）
- 观察到的情境：用户在看到英文初始提案后才发现提案 provider 可切换，并询问是否正是这里导致问题。
- 已复核的当前行为：首页创建项目时默认使用 `deterministic_fake`，现在可在第一次提案前选择 `deterministic_fake` 或 `real`，并把选择传给初始 ProductIntent Job。项目工作区仍可切换后续 Product Contract 提案 provider；Web generation contract 当前仍由 deterministic fake 派生；源码模型是另一个单独操作。
- 证据：`studio/src/views/NewProject.tsx`、`studio/src/views/ProjectStudio.tsx`、`studio/src/views/ContractView.tsx`。
- 结果：新建时已选择并说明 provider；当前 revision 的重生成/修订语义仍按现有 revision 规则处理，不会自动覆盖已存在内容。

### PS-U003 — “协作方式”选项含义与当前实际效果不清楚

- 状态：`Resolved`（2026-09-28：补充当前无行为差异的明确提示）
- 观察到的情境：用户创建项目时询问应选哪种协作方式，现有选项为“托管模式 / 共同设计 / 治理模式”。
- 已复核的当前行为：`managed`、`co_design`、`governance` 被保存在项目上并在工作区展示；当前代码没有发现它们改变提案、权限、流程或治理行为。对个人探索项目，当前可选默认“托管模式”，但名称可能让人误以为是云托管。
- 证据：`src/psyteardown/product/models.py` 的 `ProductProject.collaboration_mode`；`studio/src/views/NewProject.tsx`；`studio/src/views/ProjectStudio.tsx`。
- 当前处理：新建页已明确提示这些选项目前只记录协作偏好，不改变权限、提案流程或数据治理；个人探索默认建议“托管模式”。三种模式的真实行为差异仍未实现，后续若公开承诺再单独定范围。

### PS-U004 — 没有从界面删除项目的方式，归档不等于删除

- 状态：`Planned`（2026-09-28：先补可逆归档/恢复，永久删除仍未实现）
- 观察到的情境：用户想删除以错误/不理想方式开始的旧项目。
- 已复核的当前行为：Product Studio 现在可在首页对 active/paused 项目执行可逆“归档”，归档项目可恢复；归档保留项目及其历史，不是数据删除。仍没有永久删除 API。项目相关数据还可能分布于 SQLite revisions/jobs、workspace、模型 transcript 和导出文件，不能仅删除项目行就声称彻底删除。
- 证据：`src/psyteardown/api/projects.py` 的状态变更路由；`studio/src/views/NewProject.tsx` 的归档/恢复入口；`src/psyteardown/product/transitions.py` 允许 archived → active；`src/psyteardown/product/sqlite.py` 与 `src/psyteardown/api/app.py` 的本地存储路径。
- 待共同讨论：用户需要的是隐藏/归档、可撤销删除，还是带预览和明确边界的永久清理？如何处理 transcript、workspace、delivery exports、WAL/备份及已撤回/保留政策？在完整删除语义确定前，不建议直接手工删 SQLite 行或项目目录。

### PS-U005 — “开始项目”与“开始真实自试”被混为一个“开始”

- 状态：`Resolved`（2026-09-28：入口文案已分层）
- 观察到的情境：讨论选择对比板时，用户问“那我可以开始真实本地自试了吧”，之后澄清实际想问的是能否开始在 Product Studio 里做项目，并继续询问如何进入。
- 已复核的当前行为：建立项目/构建和预览原型，与启用 C1、创建 trial envelope、记录真实任务观察，是不同阶段；C1 默认关闭。先前说明没有及时区分这两种“开始”。
- 证据：`studio/src/views/NewProject.tsx`；`docs/product-studio/OPERATING_GUIDE.md` §2；`docs/product-studio/iterations/2026-09-28-c1-self-test-readiness.md`。
- 当前处理：新建页已明确“开始的是原型工作，不是正式自试”，并说明建立项目、预览原型、C1 真实任务观察是三个阶段；工作区主线继续显示进入 C1 的计划和交付门槛。

### PS-U006 — 首条专注切片与使用者本人不匹配，难以快速体验实际价值

- 状态：`Resolved`（2026-09-28：fake 候选不再硬编码为专注切片；价值验证仍未完成）
- 观察到的情境：用户没有专注/广告打断方面的困扰，且认为专注效果需要较长时间才能体验；因此希望探索能由普通 Web/SPA 快速演示的其他问题。
- 已复核的当前行为：专注场景仍是首条经过校准的历史切片，但不再是 fake ProductThesis / Web contract 的硬编码输出；候选路径现在围绕已确认 Outcome 生成，中文输入会提供“最小对比板”等通用可运行路径。普通 Web 模板仍有固定框架和能力边界；原型能否产生真实价值尚未验证。
- 证据：`docs/product-studio/iterations/2026-09-21-a6-first-slice-calibration.md`；`src/psyteardown/product/models.py` 的 Web contract 限制；`src/psyteardown/product/source_model.py` 的模型源码边界。
- 当前处理：可以直接用自己的问题建立项目并生成通用候选路径；本轮不把短原型体验当作价值证据。持久化、真实外部数据和长期效果仍超出当前 Web 生成器边界，后续另行定范围。

### PS-U007 — 结果契约提案的 severity 提示与本地 schema 不一致

- 状态：`Resolved`（2026-09-28）
- 观察到的情境：生成“临时选择对比板”的结果契约时，界面报错：`The provider proposal did not satisfy the local schema: severity: Input should be 'hard', 'strong_avoidance' or 'watch`，提案 Job 失败。
- 已复核的当前行为：运行时模型接受 `hard`、`strong_avoidance`、`watch`；本轮已把真实 OutcomeContract prompt 的 JSON 示例和规则统一为这三个值，解析边界兼容旧 prompt 可能返回的 `soft`（映射为 `strong_avoidance`）。此错误发生在 provider proposal 本地校验阶段，不是用户输入格式错误，也不是原型运行失败。
- 证据：`src/psyteardown/product/contract_model.py` 的 `OUTCOME_SYSTEM`；`src/psyteardown/product/models.py` 的 `ProhibitedOutcome`；`src/psyteardown/product/jobs.py` 的 `provider_schema_invalid` 错误摘要。
- 已完成：统一 prompt/schema 枚举；补充合法值和 legacy `soft` 兼容测试；ValidationError 摘要现在会明确提示字段路径及允许值。失败 Job 可按新的规则重试。
- 当前恢复：本机 SQLite 中“临时选择对比板”项目最新失败 Job pin 的仍是当前 intent r3 / problem r7；失败发生在真实 provider 的 severity schema 校验，不是“仍未知”未答完。修复代码后重启本地 API，再对这个仍绑定当前输入的 failed Job 点击“带着错误重试”；若 API 未重启，内存中的旧 prompt 仍可能继续失败。其他输入 revision 已变化的旧 Job 应新建提案，而不是反复重试旧输入。

### PS-U008 — “仍未知”像是必须填写的问卷，但没有说明如何回答

- 状态：`Resolved`（2026-09-28：编辑器和问题模型展示处补充解释）
- 观察到的情境：用户看到问题模型中的“仍未知”，不清楚自己要如何回答；同时正卡在结果契约提案失败，容易误以为必须先清空未知项。
- 已复核的当前行为：`ProblemUnknown` 表达需要后续观察/询问的开放问题，不是结果契约 Job 的前置字段；OutcomeContract Job 只要求 ProductIntent 与 ProblemModel 已确认。编辑器原先只有“每行一个问题”，没有告诉用户答案应写在哪里，也没有解释未知项可以保留。
- 当前处理：问题模型展示处说明未知不阻止生成结果契约；编辑器说明：自己确知/观察到的回答可写进“有来源的事实”并移除已解决问题，暂时不知道则保留，不要猜。此处记录的是当前用户的个人经验，不应扩写成其他用户或市场事实。
- 证据：`studio/src/views/ContractView.tsx`；`studio/src/components/ContractProposalEditors.tsx`；`src/psyteardown/product/jobs.py` 的 OutcomeContract 前置条件；`studio/src/components/ContractProposalEditors.test.tsx`。

### PS-U009 — B4 浏览器验证因契约 ID 静态识别与 primary-flow harness 不匹配而失败

- 状态：`Resolved`（2026-09-28：保存源码本地复核、生成新 workspace，最新 B4 四步成功）
- 观察到的情境：用户先遇到 `The model draft was rejected by the static gate (11 issue(s)): screen id ... is missing`，修复后又遇到 workspace browser/repair 失败。
- 根因复核：模型回复用 literal prefix + template literals 精确组合 screen/task/content-slot IDs；旧 Gate 只搜索完整源码子串而误拒绝。随后平台测试 fixture 缺少 `tasks`/`primary_flow_task_ids`；修正后 primary-flow 检查仍在 dirty flow state 开始，且未等待 400ms 本地任务 transition 就导航，造成 harness race。saved-source child 还曾使用通用模板测试而非契约派生测试。上述不是 App.tsx/Styles 构建失败；B5 无 allowlisted repair 是对未知/平台测试缺陷拒绝猜补丁，并且原源码没有被改。
- 当前处理：静态 Gate 仅解析 literal/常量前缀/简单 template literal（不执行 JS）；prompt 允许精确组合长 ID。契约测试先独立从 ready/step 0 验证主旅程，每个 task 等到允许终态后才切换 screen。保存的模型回复可经新 API 本地重校验，再通过独立 `saved_model` child Job 重建平台测试/固定文件；source/App/CSS、原 provider outcome、旧 workspace、revision 与 execution 均保留，不发起新模型调用。child renderer 也已固定用契约派生测试，不再落入模板占位 Playwright 文件。B5 对 unsupported diagnosis 不重复重试。
- 实际证据：本地 source job `generation-job-9ca0dd676a6243beb7dab6d32260209e` / revision r14 的已保存回应通过 `b7m-static-gate-v3` 本地复核，provider 原始 outcome 仍为 rejected。新的 saved-source workspace `generation-job-a38ad51b0ba54891ac1f4fbe19ce389c` 使用 `b7m-workspace-v5` 和契约派生 browser test；B4 `execution-job-778d5b56139d450793c7e4adffa8af99` 的 install、build、preview、browser 全部 succeeded。整个恢复路径没有新增 provider 调用。
- 验证边界：这证明该本地保存的源码及当前确定性平台 Gate/Chromium 链路通过；不是新的一次 DeepSeek 调用，也不是现实用户结果或 C1 观察。
- 证据：`src/psyteardown/product/source_model.py`；`src/psyteardown/product/generation.py`；`src/psyteardown/product/execution.py`；`src/psyteardown/product/repair.py`；`tests/product/test_source_model.py`；`tests/api/test_source_model_api.py`；本 iteration 记录。


### PS-U010 — 获取交付包后不知道如何启动交互版本

- 状态：`Resolved`（2026-09-29：补充下载包使用路径、本地双进程启动说明和工作台提示）
- 观察到的情境：用户点击“下载交付包 (.zip)”后，不清楚这个 ZIP 应该直接打开、重新安装源码，还是回到工作台预览；原 `DELIVERY.md` 只给了从 `source/` 重新安装和构建的开发路径，没有先说明已验证的 `build/` 可以直接静态服务。
- 当前处理：工作台明确区分“内嵌预览/反馈”和“下载包保存/分享”；下载包说明改为解压后对 `build/` 运行 `python -m http.server 4174 --bind 127.0.0.1`，并明确禁止 `file://`/双击 `index.html`。Product Studio 工作台的继续使用补充 API + Web 两个进程的启动命令；`psyteardown-studio-api` 保留为可选等价命令。
- 证据：`docs/product-studio/README.md`；`docs/product-studio/OPERATING_GUIDE.md`；`studio/README.md`；`src/psyteardown/product/delivery.py`；`studio/src/views/WorkbenchView.tsx`。
- 验证：最新本地交付 ZIP 解压后由静态 HTTP 服务访问根页面成功；API health、交付/反馈 Python 回归、前端 35 项测试和生产构建通过。


### PS-U011 — 技术验证通过但交互包没有核心产品内容，C1 前置门槛过早

- 状态：`Resolved`（2026-09-29：新增 Product Usability Gate，并把首条 fake Web 原型改为具体选项对比板）
- 观察到的情境：用户遵循 Product Studio 开发日志完成 Product Contract、Web contract、B4/B6 后，下载的交互包只有“结构化决策画布”和几个通用状态按钮，`fixture.json` 为空，没有选项、标准、已知信息、顾虑或可完成的核心对比任务。
- 根因：Phase B/C1 原先把“可构建、可启动、浏览器测试通过、交付包 provenance 正确”当成真实任务观察的充分前置；C1 start 只检查 C2 plan、当前 Web contract 和 B6 pin，没有要求 host 先确认核心任务真的可完成。Web generation contract 又使用了内容最小化的通用状态演示；源码模型只接收 Web contract，因此无法恢复被稀释的产品语义。
- 当前处理：C1 API/UI 新增 `product_usability_confirmed`，没有 host 明确确认不得创建 envelope；UI 明确提示 B4/B6 不等于产品可用。fake Web contract 改为包含两个本地选项、决策标准、已知信息、顾虑、用户自己的倾向和未知项；deterministic template 改为实际渲染可编辑对比板，源码模型提示禁止只生成通用按钮演示。
- 证据：`src/psyteardown/product/c1.py`；`src/psyteardown/api/schemas.py`；`studio/src/views/C1Panel.tsx`；`src/psyteardown/product/providers.py`；`src/psyteardown/product/generation.py`；新 iteration 记录。
- 边界：已有旧 revision/交付包保持不可变，不自动变成新产品；必须重新生成 Web contract、workspace、B4 和 B6。当前项目已确认稳定契约 ID 的 r10 revision，双选项记录已改为每个选项独立字段，并增加决定设定、JSON 导出/导入重开；尚未生成 r10 对应的新 B6，已有 r2/r5 B6 保持不变。C1 真实试用仍未启动。

## 后续问题

后续遇到问题时，按上面的格式追加新的 `PS-Uxxx`，记录发生步骤、实际文案/行为、影响和复现条件；不要求用户先判断它是 bug、设计问题还是新需求。
