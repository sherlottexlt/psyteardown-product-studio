# Product Studio 开发台账

- 状态：Active
- 建立日期：2026-09-20
- 适用范围：psyteardown 从“可信研发内核”演进为 AI Product Studio 的全部工作
- 上位方向：[`AI Product Studio 北极星与产品形态规格`](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md)
- 既有内核实施基线（仅限其原有范围）：[`未来方向与实施计划`](../superpowers/specs/2026-09-08-psyteardown-future-direction-and-implementation-plan.md)

## 这个目录解决什么问题

大型项目最容易出现的不是“没有文档”，而是状态、计划、决策和历史混在一起，后来无法判断什么已经实现、什么只是设想。本目录是 Product Studio 的长期开发入口，用来回答四个问题：

1. 现在真实具备什么能力；
2. 当前在推进什么，完成门槛是什么；
3. 为什么作出关键选择；
4. 各部分如何随代码、测试和现实证据演变。

本目录不复制所有规格、ADR 或代码说明，而是索引它们并记录项目级演变。旧内核 ADR 不是 Product Studio 的默认决策来源；A1/A2 已按 A6 首条数字产品切片校准为当前基线（不等于最终通用架构），A3/A4/A5 已完成并有端到端证据，Phase A 已关闭。

## 文档地图

| 文档 | 用途 | 更新方式 |
|---|---|---|
| [`CURRENT_STATE.md`](CURRENT_STATE.md) | 当前能力、缺口、验证基线和最近下一步 | 每个实现批次结束时覆盖更新 |
| [`OPERATING_GUIDE.md`](OPERATING_GUIDE.md) | 当前本地使用流程、结果来源与边界 | 本地使用流程变化时更新 |
| [`ROADMAP.md`](ROADMAP.md) | 阶段、工作包、依赖与退出门槛 | 计划或优先级变化时更新 |
| [`DECISION_REGISTER.md`](DECISION_REGISTER.md) | North Star 决策、原型假设和待决问题的索引 | 决策、试验结果或范围变化时更新 |
| [`USER_FEEDBACK.md`](USER_FEEDBACK.md) | 实际使用反馈与待共同解决的问题 | 使用中发现问题时追加；讨论后更新状态与证据 |
| [`EVOLUTION_LOG.md`](EVOLUTION_LOG.md) | 项目级时间线 | 只在末尾追加，不改写历史 |
| [`architecture/domain-boundaries.md`](architecture/domain-boundaries.md) | Product 上位域与既有研发内核的职责及集成方向 | 边界或跨域写入规则变化时更新 |
| [`workstreams/phase-a-foundation.md`](workstreams/phase-a-foundation.md) | 当前 Phase A 的实施分解和验收条件 | 工作包推进时更新 |
| [`iterations/2026-09-20-project-ledger-bootstrap.md`](iterations/2026-09-20-project-ledger-bootstrap.md) | 第一次实施记录 | 关闭后保持不变；纠错另记 |
| [`iterations/2026-09-20-a1-upper-domain-contracts.md`](iterations/2026-09-20-a1-upper-domain-contracts.md) | A1 上位领域契约实现记录 | 已关闭；保持不变 |
| [`iterations/2026-09-20-a2-project-application-service.md`](iterations/2026-09-20-a2-project-application-service.md) | A2 项目应用服务与持久化记录 | 已关闭；保持不变 |
| [`iterations/2026-09-20-a3-fastapi-shell.md`](iterations/2026-09-20-a3-fastapi-shell.md) | A3 FastAPI 实施记录 | 已关闭；保持不变 |
| [`iterations/2026-09-20-a4-product-studio-web-shell.md`](iterations/2026-09-20-a4-product-studio-web-shell.md) | A4 第一批 Product Studio Web 壳实现记录 | 本批次已关闭；A4 剩余项另开记录 |
| [`iterations/2026-09-20-a4-1-contract-correction-and-browser-gates.md`](iterations/2026-09-20-a4-1-contract-correction-and-browser-gates.md) | A4.1 契约纠正、生成类型与浏览器 Gate | 已关闭；保持不变 |
| [`iterations/2026-09-20-a3-1-http-contract-matrix.md`](iterations/2026-09-20-a3-1-http-contract-matrix.md) | A3.1 HTTP 契约与恢复矩阵 | 已关闭；保持不变 |
| [`iterations/2026-09-20-a5-fake-provider-product-contract.md`](iterations/2026-09-20-a5-fake-provider-product-contract.md) | A5 fake provider 与持久化 Product Contract Job | 已关闭；保持不变 |
| [`iterations/2026-09-21-a6-first-slice-calibration.md`](iterations/2026-09-21-a6-first-slice-calibration.md) | A6 首条数字产品切片、字段/人工 Gate 与 Outcome Contract 校准 | 已关闭；Phase B 前置基线 |
| [`iterations/2026-09-21-b1-product-thesis-search.md`](iterations/2026-09-21-b1-product-thesis-search.md) | B1 Product Thesis 搜索、比较与人工选择 | 本批次关闭；B2 模板决策待开始 |
| [`iterations/2026-09-21-b2-web-template-generation-contract.md`](iterations/2026-09-21-b2-web-template-generation-contract.md) | B2 单一 Web 模板与内容最小化生成契约 | 本批次关闭；B3 沙箱/预算决策待开始 |
| [`iterations/2026-09-21-b3-generation-job-workspace.md`](iterations/2026-09-21-b3-generation-job-workspace.md) | B3 受预算约束的 Web 生成 Job workspace | 本批次已关闭；执行权限由独立 B4 Job 处理 |
| [`iterations/2026-09-22-b4-isolated-execution.md`](iterations/2026-09-22-b4-isolated-execution.md) | B4 受隔离执行的构建、运行与浏览器验证 | 本地执行切片已关闭；OS/container 隔离与真实任务反馈仍待后续 |
| [`iterations/2026-09-22-b5-bounded-repair-loop.md`](iterations/2026-09-22-b5-bounded-repair-loop.md) | B5 受限失败定位与修复闭环 | 本地 deterministic repair 切片已关闭；真实模型/跨框架修复、部署级隔离与真实反馈仍待后续 |
| [`iterations/2026-09-23-b6-delivery-bundle.md`](iterations/2026-09-23-b6-delivery-bundle.md) | B6 可追溯导出交付包与 B4 真实链路修复 | 已关闭；B7 需先关闭 PS-O007 |
| [`iterations/2026-09-23-b7-preview-feedback-anchors.md`](iterations/2026-09-23-b7-preview-feedback-anchors.md) | B7 预览与显式、同意、可撤回反馈锚点；PS-O007 关闭 | 已关闭；B8 反馈驱动迭代待开始 |
| [`iterations/2026-09-23-b7m-model-source-generation.md`](iterations/2026-09-23-b7m-model-source-generation.md) | B7m 真实模型源码生成、静态门禁与 B3→B4→B6→B7 真实链路 | 已关闭；B8 反馈驱动迭代待开始 |
| [`iterations/2026-09-24-b8-feedback-driven-iteration.md`](iterations/2026-09-24-b8-feedback-driven-iteration.md) | B8 反馈驱动迭代提案、人工处理状态与交付版本差异 | 已关闭；B9 让迭代改变产品待开始 |
| [`iterations/2026-09-24-b9-iteration-changes-product.md`](iterations/2026-09-24-b9-iteration-changes-product.md) | B9 让反馈迭代真正改变产品（模板固定、模型路径可变） | 已关闭；Phase B 出口复核已完成 |
| [`iterations/2026-09-24-phase-b-exit-review.md`](iterations/2026-09-24-phase-b-exit-review.md) | Phase B 出口复核：验证退出门槛、识别差距、决定 Phase C 前置 | 已关闭；Phase B 已关闭 |
| [`iterations/2026-09-24-c0-real-provider-integration.md`](iterations/2026-09-24-c0-real-provider-integration.md) | C0 真实 provider 接入与端到端链路 | 已关闭；阶段 5-6 已完成真实 Product Contract→B7m→B4→B6 链路 |
| [`iterations/2026-09-25-c2-outcome-measurement-plan.md`](iterations/2026-09-25-c2-outcome-measurement-plan.md) | C2 Outcome Contract 指标测量计划 | 已关闭；C1 backend/API/UI slice 已实现，C3 已关闭；本文件的下一步文字仅保留为历史记录 |
| [`iterations/2026-09-26-c1-outcome-observation-intake.md`](iterations/2026-09-26-c1-outcome-observation-intake.md) | C1 真实任务观察接入、Product-side intake 与主持面板 | Active；D1/D2/D3 已冻结，backend/API/UI 与确定性测试已实现；未招募或收集真实参与者 |
| [`iterations/2026-09-26-c3-real-provider-stability.md`](iterations/2026-09-26-c3-real-provider-stability.md) | C3 多次真实 provider 链路稳定性评估 | 已关闭；R4 10/10 完整通过本批 Gate；早期失败样本与 B4 安全边界保留 |
| [`iterations/2026-09-20-adr-scope-correction.md`](iterations/2026-09-20-adr-scope-correction.md) | 新旧 ADR 范围校正与文件清理 | 已关闭；纠错另记 |
| [`templates/iteration-record.md`](templates/iteration-record.md) | 后续实现记录模板 | 仅在记录制度变化时更新 |
| [`iterations/2026-09-26-work-package-record-normalization.md`](iterations/2026-09-26-work-package-record-normalization.md) | 最近工作包记录格式与状态语义校正 | 已关闭；不改写历史事实，统一当前台账解释 |
| [`iterations/2026-09-26-c1-self-pilot-scope-correction.md`](iterations/2026-09-26-c1-self-pilot-scope-correction.md) | C1 负责人自试与非参与者演练 Gate 范围校正 | 已关闭；负责人自试可直接启动，N=1 证据边界不变 |
| [`iterations/2026-09-27-product-studio-recovery-and-local-guardrails.md`](iterations/2026-09-27-product-studio-recovery-and-local-guardrails.md) | C1 真实体验验证前的工作区恢复、Job 控制与本地边界补强 | 已关闭；真实参与者验证暂缓 |
| [`iterations/2026-09-27-c1-trial-pause-and-orphan-recovery.md`](iterations/2026-09-27-c1-trial-pause-and-orphan-recovery.md) | C1 暂停门禁、独立审查与中断 Job 恢复 | 已关闭；真实参与者验证继续暂缓 |
| [`iterations/2026-09-27-c1-trial-lifecycle-and-retention.md`](iterations/2026-09-27-c1-trial-lifecycle-and-retention.md) | C1.3 trial lifecycle、close/stop 与本地 30 天 retention enforcement | 已关闭；真实参与者验证继续暂缓 |
| [`iterations/2026-09-28-b4-contract-test-harness-fix.md`](iterations/2026-09-28-b4-contract-test-harness-fix.md) | B4 契约浏览器测试 harness 修复与 B5 unsupported recovery | 确定性回归通过；当前用户项目重跑待负责人启动 |
| [`iterations/2026-09-27-c1-mainline-and-model-resilience.md`](iterations/2026-09-27-c1-mainline-and-model-resilience.md) | C1 主链路收敛与模型生成韧性补强 | 实现范围已关闭；未启动真实 C1 试用 |
| [`iterations/2026-09-28-c1-self-test-readiness.md`](iterations/2026-09-28-c1-self-test-readiness.md) | C1 负责人本地自试前就绪复核 | 软件门槛已验证；启动仍由负责人决定 |
| [`iterations/2026-09-29-product-usability-gate-and-comparison-board.md`](iterations/2026-09-29-product-usability-gate-and-comparison-board.md) | 修正 C1 前置门槛并让首条 Web 原型具备真实对比任务 | 已关闭；旧交付包不变，需重新生成新契约/交付包 |
| [`iterations/2026-09-29-product-usability-follow-up.md`](iterations/2026-09-29-product-usability-follow-up.md) | 修复稳定契约重提案、双选项独立记录和 r4 本地旅程验收 | 已关闭；r4 仍待人工确认，C1 未启动 |
| [`iterations/2026-09-30-v02-decision-brief.md`](iterations/2026-09-30-v02-decision-brief.md) | 将对比板推进为可保存、可重开的 Decision Brief | 已关闭；r7 仍待人工确认，C1 未启动 |

后续按需要增加以下内容，而不是预先建立大量空目录：

- `workstreams/`：一个长期工作流一份活文档；
- `iterations/`：一次可验证实现批次一份记录；
- `architecture/`：跨领域才需要说明清楚的系统视图，明确区分现状与设想；
- `operations/`：构建、迁移、部署和恢复手册。

## 当前优先级校正

C1 真实参与者/负责人真实体验验证尚未启动。2026-09-29 已补上此前缺失的 Product Usability Gate：C1 除 C2 plan、当前 Web contract、成功 B6 delivery pin 外，还必须由 host 明确确认“已亲自完成核心任务，交互有真实输入/内容和完成结果”；B4/B6 通过本身不再足够。首条 fake Web contract 和 deterministic template 也已改为具体的选项对比板，而不是通用状态演示。保持 C1 开关默认关闭；旧交付包不会自动变化；当前项目已确认同一稳定契约 ID 的 r10 Web contract，下一步是生成 workspace、B4 和 B6。

## 本地启动（第一次使用）

如果要在 Product Studio 里继续预览、提交反馈或重新生成，不是只启动 Vite：需要同时启动 **API** 和 **Web** 两个进程。建议用两个 PowerShell 窗口：

```powershell
# 窗口 1：在仓库根目录 D:\app\app-mental
python -m uvicorn psyteardown.api.app:app --host 127.0.0.1 --port 8000

# 窗口 2：
Set-Location D:\app\app-mental\studio
npm run dev -- --host 127.0.0.1
```

然后打开 `http://127.0.0.1:5173/`。窗口 1 如果提示端口 8000 被占用，说明 API 可能已经在运行；可先访问 `http://127.0.0.1:8000/api/v1/health`，返回健康结果后不要再启动第二个 API。若已安装项目命令，也可以把窗口 1 的命令替换为 `psyteardown-studio-api`。

若只想查看已经下载的 ZIP，不需要启动这两个服务，直接按下面“获取交互包后怎么做”操作即可。

## 获取交互包后怎么做（当前本地流程）

这里要区分两个东西：**工作台里的预览**和**下载的交付包**。

- **想继续体验、记录反馈、提出下一轮修改**：不要先解压 ZIP。留在项目的“产品工作台”，在“交付包”出现后直接看上方的预览；体验后在预览下方提交反馈，再用“基于此反馈提出新契约”进入下一轮。
- **想把当前已验证版本保存下来或发给别人查看**：点击“下载交付包 (.zip)”。这个 ZIP 是交付/审计材料，不是需要双击打开的网页文件。

下载 ZIP 后，按下面步骤在本机打开交互版本：

```powershell
# 在下载文件所在目录执行；把 <bundle>.zip 换成实际文件名
Expand-Archive .\<bundle>.zip -DestinationPath .\<bundle>
Set-Location .\<bundle>\build
python -m http.server 4174 --bind 127.0.0.1
```

然后打开 <http://127.0.0.1:4174/>。保持这个 PowerShell 窗口运行，结束时按 `Ctrl+C`。

**不要**直接双击 ZIP、双击 `build/index.html`，也不要用 `file://.../build/index.html` 打开；当前构建使用浏览器模块和相对资源，直接以文件方式打开不是验证过的流程，常见结果是白屏或资源加载失败。

ZIP 中的目录含义：

- `build/`：已经通过 B4 验证的静态交互版本，体验时使用它；
- `source/`：生成源码，仅在需要开发/重新构建时使用；
- `verification/`：本次本地构建、预览、浏览器检查的安全摘要和产物；
- `DELIVERY.md`、`bundle-manifest.json`：来源、hash 和未验证声明。

如果要修改产品，不要直接改下载包后把它当成下一版：回到 Product Studio 预览中提交反馈，确认新 Web 契约，再重新生成、B4 验证并导出新的交付包。下载包本身不会把反馈回传给 Product Studio，也不代表已经部署到公网或达到真实用户验证。

## 工作包记录的统一口径

最近几个 Phase C 记录把“生命周期状态”和“验证结果/阶段中间状态”混写在同一文件里，容易出现 `done`、`verified`、`blocked`、`decision required` 与 `in progress` 并列，甚至出现历史的下一步文字落后于当前代码。自 2026-09-26 起按下面规则阅读和新增记录：

- iteration 顶部的 `状态` 只使用模板中的生命周期值：`Planned`、`Active`、`Paused`、`Closed`、`Superseded`。`done` 等旧写法只在已关闭历史记录中保留，不作为新的顶部状态。
- `verified`、`blocked`、`decision required` 是验收结果、失败边界或待决事项，不是生命周期状态；应放在“验证/遗留项/决策与偏差”小节。
- `CURRENT_STATE.md` 和 `ROADMAP.md` 是当前状态权威入口；已关闭 iteration 不静默改写，发现旧结论或旧“下一步”时另开纠错记录并在入口处说明。
- 一个 iteration 记录一个可验证实现批次。继续实现同一工作包时，保留 Active 记录并追加“本批继续实施”；若前一批已经 Closed，则新建带日期的新 iteration，不把新代码倒填进旧历史。
- 当前（2026-09-28）的统一解释是：Phase B 已 Closed；C0/C2/C3 已 Closed；C1 软件侧准备已验证，但真实自试尚未启动，默认开关关闭。负责人可在明确决定并满足项目 pin/同意边界后作为首位参与者，不要求独立非参与者演练；N=1（即使有多个 session）不满足 C2 `minimum_n=3`，也不支持泛化结果声明。

## 事实与权威来源

不同问题使用不同权威来源：

| 问题 | 权威来源 |
|---|---|
| 产品为什么存在、服务谁、不能做什么 | North Star 规格 |
| 新 Product Studio 的已确认方向 | North Star 明确写出的选择；后续需单独确认的新决策记入本目录 |
| 既有研发内核为什么这样实现 | 在其原有范围内适用的 `docs/adr/` 历史记录 |
| 当前探索方案为何如此实现 | iteration 的实施记录与测试，不等同于已确认架构 |
| 当前软件实际上做什么 | 源代码、迁移和自动化测试 |
| 当前能声称什么验证等级 | 原始工具结果、现实证据和具名审查 |
| 项目正在做什么、下一步是什么 | 本目录的状态、路线图和工作记录 |

如果这些来源互相冲突，不要静默选择一个版本：先在实现记录中标出差异，再明确适用范围与后续决策。不能因为旧 ADR 标为 `accepted`，就把它自动升级为新平台约束；也不能因为原型测试通过，就认为产品或架构已获批准。`CURRENT_STATE.md` 只能总结事实，不能把计划写成已实现能力。

## 2026-09-28 使用阻塞修复摘要

本轮先处理影响继续试用的入口和契约问题，验证证据如下：

- **首次提案 provider 可在新建项目时选择**：默认仍是本地 `fake`，也可明确选择 `real（DeepSeek）`；真实 provider 的外发边界在表单中明示。见 `studio/src/views/NewProject.tsx` 与 `studio/src/api/client.ts`。
- **中文输入的 fake Product Contract / Thesis / Web 提案跟随中文**：fake 仍明确是合成内容，不冒充研究；现有英文 revision 不会被隐式翻译。候选路径不再硬编码为专注场景，而是围绕已确认 Outcome 生成。见 `src/psyteardown/product/providers.py`。
- **Outcome severity 契约已统一**：prompt 使用运行时允许的 `hard`、`strong_avoidance`、`watch`；旧 `soft` 只在解析边界兼容为 `strong_avoidance`，并补充了契约测试。见 `src/psyteardown/product/contract_model.py` 与 `tests/product/test_contract_model.py`。
- **“仍未知”已明确为待查问题，而非生成 Gate**：知道答案就补进“有来源的事实”并移除已解决的问题；不知道可以保留，不需要清空未知即可确认问题模型、生成结果契约。见 `studio/src/components/ContractProposalEditors.tsx` 与 `studio/src/views/ContractView.tsx`。
- **项目可从首页归档/恢复**：这是可逆的列表整理，不是永久删除；永久清理仍需单独定义 transcript、workspace、导出物、WAL/备份的边界。见 `studio/src/views/NewProject.tsx` 与 `src/psyteardown/product/transitions.py`。
- **“开始”分层已前置说明**：建立项目、预览原型、记录 C1 真实任务观察不再写成同一个开始动作。
- **B4 model source recovery 已走通**：Gate 可识别 literal-prefix/template-literal 契约 ID；浏览器测试 fixture、primary-flow 起始状态/异步等待和 saved-source child 的测试覆盖已修复。最新 saved-source workspace 的 B4 install/build/preview/browser 四步均成功；使用本地保存回复，没有新增 provider 调用。原失败 workspace/job 与 provider 原始 rejection 均保留。见 `iterations/2026-09-28-b4-contract-test-harness-fix.md`。

本轮不把以下内容误报为已完成：永久删除、把所有历史 revision 自动翻译成中文、以及首条专注切片对个人价值的真实验证。对应状态继续以 `USER_FEEDBACK.md` 和 `CURRENT_STATE.md` 为准。

## 每个实现批次的维护协议

### 开始前

1. 阅读 North Star、`CURRENT_STATE.md`、`ROADMAP.md` 和本工作包需要的旧内核资料；
2. 在 `iterations/` 新建记录，写清目标、非目标、基线和验收条件；
3. 如果工作涉及新的长期边界，先在 `DECISION_REGISTER.md` 标明待决与暂定方案；只有确定必要性与适用范围后才新增正式决策文件。

### 实施中

1. 记录范围变化、关键权衡和发现的历史债务；
2. 所有“已完成”都必须能链接到代码、测试、迁移、截图或其他可复核证据；
3. 使用 `planned`、`implemented`、`verified`、`blocked`、`unknown` 等明确状态，避免模糊的完成百分比。

### 结束时

1. 运行与风险相称的测试并记录结果；
2. 更新 `CURRENT_STATE.md` 中受影响的事实与缺口；
3. 更新 `ROADMAP.md` 的工作包状态；
4. 将一条摘要追加到 `EVOLUTION_LOG.md`；
5. 关闭本次 iteration 记录，列出遗留项和下一最小工作包。

## 防漂移规则

- 第一条主线始终是“模糊意图到可运行数字产品的完整闭环”，不是继续横向增加旧内核对象。
- 现有 revision、provenance、dependency、stale/invalidation 和 Gate 能力优先复用，不另建平行真相源。
- 聊天和模型输出只是 proposal；确认后的结构化对象与 Domain Command 才能改变项目状态。
- 仿真、渲染、模型自评和自动测试不得冒充真实用户、物理、法规或商业结果。
- 在首条闭环完成前，不引入 North Star 明确排除的基础设施复杂度。
