# C1 — 首轮真实任务观察接入预案

- 工作包 ID：C1
- 建立日期：2026-09-26
- 状态：Active（Product-side backend/API 与主持面板已实现；未招募、未收集真实参与者数据）
- 路线图工作包：C1
- 类型：Workflow / API / UI / Validation
- 前置：C2 OutcomeMeasurementPlan 已实现；C0 已有一次真实链路成功，但重复运行在 B7m 静态 Gate 失败
- 目标切片：A6 冻结的自主管理知识工作者桌面专注时段

## 目标

为小规模、人工主持、明确同意的真实任务试用准备一个可复核的 Product-side intake 和主持面板；每条人工记录都绑定已确认测量计划 revision、实际交付构建和有效同意范围，之后由具名人工执行 `EvidenceReview`。本工作包目前完成软件准备和确定性演练，不把测试数据当作真实观察，也不自动增加运行时采集。

## 已核对的现有构件与缺口

- `OutcomeMeasurementPlan`（Product 域）可 pin Outcome Contract 并规定 measure、阈值、样本、同意/撤回文字；当前它是计划，不是运行、参与者或 consent receipt。
- `OutcomeObservation`（Experience 域）有 participant/presentation/measure/value/status/evidence refs，但没有类型化的 Product 测量计划 revision、B6 bundle/execution revision 或同意回执字段；目前没有对应的 ExperienceApplicationService intake/API 流程。
- `ParticipantRecord` 只有可选 `consent_scope_revision_id`，仓库中没有可复用的、可撤回的参与者同意回执对象/命令。
- `MeasurementObservation` 的现有导入/复核服务绑定 `PrototypeRun`，正式研究还可要求 DesignBrief/ExperimentPlan/M2 分析 lineage；不能直接假设它就是 Web Product C1 的适配器。`EvidenceReview` 虽是人工审查，但目前没有按 C2 source-layer ceiling 验证其可提升的上限。
- Product 与 Experience 使用不同应用服务和 repository；Product Studio API 目前只组装 Product 服务。`PS-O010` 仍 open，跨域写入/事务/存储边界尚未决定。
- B7 的撤回语义针对显式预览反馈（擦除该反馈正文/类别），不自动适用于参与者的原始观察、录音/附件、研究笔记或包含已撤回个体的派生汇总。

## 需要先由产品负责人明确的决策

### D1 — 同意、最小数据与撤回/保留

建议默认：仅本地主持；不采姓名、邮箱、雇主、键盘/鼠标、通知内容、屏幕录像或自动事件；参与者用随机短 ID；开始每次任务前记录当前同意政策 revision、授权范围、时间和主持人；参与者可随时无责退出。撤回后停止任务，清除该参与者可识别的原始 observation/附件及其分析贡献，保留不含内容的撤回 tombstone/审计事实。是否允许保留不可逆聚合统计须在同意文本中明说，默认不保留。

需确认：本地存储位置/访问者、同意文字与版本、是否记录年龄/人口属性（建议不记录）、原始材料类型、撤回后删除范围、备份/SQLite/WAL 中物理擦除要求、保留期限，以及是否允许匿名汇总。

### D2 — Product ↔ Experience 的 observation 写入边界

建议默认：Product 命令校验当前项目、已确认测量计划、measure 和当前交付包；之后通过一个显式 C1 adapter 将已验证的 typed refs 与人工原始记录写入 Experience observation store；不在两个 repository 间假设跨库原子事务，失败时 observation 保持未关联/待恢复，禁止丢失 pin 或静默变成证据。

需确认：继续使用 Experience `OutcomeObservation` 并补充 typed provenance，还是建立 Product 的 observation intake aggregate；Product 与 Experience 是否共用一个 SQLite 文件、如何处理部分失败/恢复、哪一个应用服务拥有唯一写边界。此项需同时复核 `PS-O010`。

### D3 — 人工 EvidenceReview 与等级上限

建议默认：所有 observation 初始均为 draft/未确认；只能具名人工复核；复核绑定每条观察、C2 measure/source layer、同意回执、测量计划 revision 和交付 revision；模型只可协助整理，不可代审或写入 review；允许等级不得高于 PS-O020 的 source-layer ceiling，`software_check` 不能成为现实用户结果证据。

需确认：谁可担任 reviewer（是否必须与主持人分离）、每个来源层可用的 EvidenceReview 决策与等级映射、矛盾/缺失数据如何审查、达到什么门槛才允许回退/修订 Product Thesis 或 Outcome Contract。

## 决策通过后的最小实施范围

1. 创建/开始一次试用 envelope，pin：project ID、confirmed MeasurementPlan revision、一个当前 B6 bundle ID、其 `execution_job_revision_id` 和 Web Contract revision。
2. 校验 measure 属于 pin 的计划；计划仍为当前/confirmed；bundle 与 execution/contract provenance 一致；当前计划的样本、同意、停止条件与 withdrawal policy 完整。
3. 每位参与者开始前写入同意 receipt revision 和随机 participant ID；未经同意不得创建任务 presentation 或 observation。
4. 主持人手动提交结构化 OutcomeObservation（包括明确 missing/withdrawn 状态）；不采集预览遥测，不上传参与者原始文本给模型。
5. 撤回命令按批准政策清理数据并留下最小 tombstone；退出者不应继续进入分析分母。
6. 具名 reviewer 在 source ceiling Gate 下创建 EvidenceReview；Review 才是证据等级的人工边界。C1 首批不自动修改产品论点或契约，只呈现观察与待审结果。
7. 提供 SQLite 重启/恢复、冲突、未同意拒绝、撤回/擦除和 source-ceiling 越权拒绝测试；浏览器端只需支持人工录入与状态查看，不引入后台采集。

## 非目标

- 不在未批准 D1/D2/D3 前新增 observation、consent 或 review schema/API/UI；
- 不录制参与者屏幕、键鼠、通知或运行时事件；不把 B7 `user_report` 反馈自动当作 C1 Observation；
- 不做统计显著性或预注册实验；是否接入 ExperimentPlan/M2 另行决策；
- 不让模型判定参与者同意、观察真伪、EvidenceReview 或产品成功；
- 不把 C0 provider 成功率、Chromium E2E、C2 计划确认当作真实结果证据。

## 验收条件（决策确认后再冻结）

- 每条 observation 可追到 C2 plan + measure + B6 delivered revision + consent receipt；任一 pin stale/撤回/不匹配时写入拒绝路径。
- 未同意无法开始；撤回按批准范围删除/排除数据且经 SQLite 文件/恢复测试验证。
- 只有具名人工 EvidenceReview 可以提升等级，且不能超过 source-layer ceiling。
- 所有原始观察均保留缺失、跳过、退出、技术失败等非成功路径；不把缺失解释成失败或成功。
- 全量确定性测试、HTTP/API、前端浏览器流程与 axe Gate 通过；再邀请参与者前由负责人审阅最终同意文案和数据处理说明。

## 决策确认（2026-09-26）

本批按预案默认值冻结最小本地试用边界；这不是托管、多用户或法律合规承诺，进入远程招募/企业场景时必须重新审阅。

### D1 — 同意、最小数据与撤回/保留：approved_for_local_pilot

- 仅本地主持；不采姓名、邮箱、雇主、人口属性、键盘/鼠标、通知、屏幕录像、截图、自动运行事件或参与者原始文本；参与者只获得随机短 ID。
- 同意政策 revision 固定为 `c1-local-v1`；每次试用开始前单独记录 consent receipt、范围、时间、主持人和访问者（本地主持、具名 reviewer）。
- 结构化记录只允许随机 ID、任务 measure 值、任务状态和人工记录时间；不把记录发送给模型。
- 保留期限声明为 envelope 关闭后最多 30 天；本地 C1 不保留不可逆匿名聚合。SQLite 开启 `secure_delete=ON`，撤回会删除 receipt/presentation/observation/review source rows、删除对应 C1 audit rows，并尝试截断 WAL；应用不管理操作者自行复制的外部备份，不能对其物理擦除作承诺。
- 撤回立即停止该参与者后续任务，删除其可关联源记录和 review，保留只含计数与哈希的 withdrawal tombstone；退出、跳过、无响应、技术失败等非成功路径仍可记录。

### D2 — Product ↔ Experience 写入边界：approved_for_first_c1_slice

- 采用 Product-side `C1TrialEnvelope`、`C1ConsentReceipt`、`C1Participant`、`C1TaskPresentation`、`C1OutcomeObservation`、`C1EvidenceReview` 和 `C1WithdrawalTombstone`，不把 C1 首批写入既有 Experience `OutcomeObservation`/`EvidenceReview`。
- C1 application service 是唯一命令写边界；它先只读校验当前 confirmed C2 plan、当前 Web contract 和 B6 bundle 的 typed pins，再写专用 C1 repository。Product 与 Experience 不假设跨库原子事务；本批没有跨域写入，因此不存在“半写成证据”的回退路径。
- InMemory 与 SQLite 适配器均支持原子 batch、重启恢复和 withdrawal hard-delete；SQLite 与既有 Product store 共用文件但使用专用表，后续若需要 Experience 投影另开 adapter/决策，不在本批隐式复制事实。

### D3 — 人工 EvidenceReview 与等级上限：approved_for_first_c1_slice

- reviewer 必须是具名人工，且与主持人分离；模型不可创建、修改或代审 review。
- C1 只接受 `research_observation`；source-layer ceiling 固定为 `observed`。`software_check`、`runtime_event`、`model_interpretation` 不能成为 C1 现实任务结果证据。
- observation 初始没有 EvidenceReview；只有单独的接受/修改 review 才可提升到 `exploratory` 或 `observed`。非成功/缺失路径不可被接受为成功结果；rejected/insufficient review 保留 `none`。
- 首批 review 不自动修改 Product Thesis、Outcome Contract 或生成契约；矛盾结果只作为待人工讨论的回退输入。

## 已实现（backend/API slice）

- `src/psyteardown/product/c1.py`：C1 typed records、显式 consent、plan/delivery/contract pin 校验、measure value-kind 校验、人工 reviewer ceiling、withdrawal tombstone、InMemory/SQLite repository。
- `src/psyteardown/api/c1.py`：policy、envelope、participant、presentation、manual observation、withdrawal、EvidenceReview 的 HTTP 命令/查询端点；新增 transport schema、dependency wiring 和 OpenAPI/generated types。
- C1 不接收 preview 遥测，不接收模型输入，不自动把 B7 `user_report` 转换成 C1 observation。

## 验证（backend/API slice）

- `pytest -q tests/api/test_c1.py` → 2 passed、2 warnings；覆盖拒绝未同意、C2/B6 pin、手动 observation、source ceiling、review、SQLite 重启和 withdrawal 后源记录清除。
- `pytest -q tests/product tests/api --ignore=tests/product/test_c0_real_provider_e2e.py` → 147 passed、1 skipped、2 warnings。
- OpenAPI 已重新生成：`studio/openapi.json`、`studio/src/api/schema.ts`。

## 本批继续实施：主持面板与负责人自试准备

2026-09-26 已把原先“backend slice”之后的最小 UI 批次并入本 Active 工作包；随后根据本地首轮使用方式，不再把非参与者演练设为负责人自试前的强制 Gate；这不是一次新的长期架构决策，也没有改变 PS-O022/PS-O023/PS-O024。

- `studio/src/views/C1Panel.tsx` 已接入 Evidence 区：展示冻结的同意政策，只有确认的 C2 plan、当前 Web contract 和成功的 B6 bundle 才能开始 envelope；随后按“同意 → 随机 participant ID → task presentation → 结构化 observation → 人工 review / withdrawal”顺序操作。
- C1 observation 仍只接受 `research_observation`；非成功路径记录 `value=null` 和人工填写的 completion cause，不把技术失败或缺失解释成成功。
- review UI 每次只提交一个 observation/measure，并显示已 review 与待 review 状态，避免触发后端“review one measure at a time”边界；rejected/insufficient 必须保留等级 `none`，非成功路径不能被 UI 或后端升级为结果证据。
- `studio/src/views/C1Panel.test.tsx` 覆盖无当前交付时的启动 Gate、非成功路径值边界、单条人工 review；C1 API 仍不接收预览遥测、屏幕/键鼠数据或模型输入。

## 验证（主持面板批次）

- `pytest -q tests/api/test_c1.py` → 2 passed、2 warnings。
- `npm test -- --run src/views/C1Panel.test.tsx` → 2 passed。
- `npm test -- --run` → 28 passed。
- `npm run build` → 成功；同时重新生成 `studio/openapi.json` 与 `studio/src/api/schema.ts`。
- `npm run test:e2e` → 2 passed；第二条 Chromium flow 验证已确认测量计划下显示 C1 panel，并在缺少当前 B6 delivery 时保持启动按钮 disabled，同时通过 axe Gate。
- 这些结果证明的是命令/API/UI 在确定性测试和本地构建中的行为；它们不证明同意文案已获负责人签批，也不构成真实参与者结果。

## 当前剩余项与下一最小工作包

- 尚无实际负责人自试数据、reviewer 名单确认、retention sweeper 或真实参与者数据。
- 下一最小工作包：`C1 负责人本地自试与独立人工 review`。负责人可直接作为首位真实参与者在本机完成一次自试；这同时验证真实任务和主持流程，不要求先做独立非参与者演练。
- 该 N=1 participant 可以产生多个真实 task session，但仍按 `participant_n=1, session_k>=1` 计算；它不满足当前 C2 计划的 participant `minimum_n=3`，不支持泛化效果声明。EvidenceReview 仍须由与 host 分离的具名人工完成，否则保留为未 review observation。
- 负责人仍需确认实际展示的同意文案、访问者名单和外部备份处理说明；该确认不等同于法律意见。
