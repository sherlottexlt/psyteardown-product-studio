# Product Studio 操作、结果来源与使用边界指南

- 快照日期：2026-09-28
- 适用范围：当前本地 Product Studio 首条数字/Web 产品切片
- 性质：个人查看用的当前快照，不是项目权威入口
- 说明：项目持续更新后，本文件可能过时；遇到冲突时以代码和项目状态文档为准
- 参考入口：[`CURRENT_STATE.md`](CURRENT_STATE.md)、[`ROADMAP.md`](ROADMAP.md)、[`DECISION_REGISTER.md`](DECISION_REGISTER.md)、[`AI Product Studio 北极星与产品形态规格`](../superpowers/specs/2026-09-20-psyteardown-ai-product-studio-north-star.md)

## 1. 先给结论

当前 Product Studio 不是“自动判断产品是否成功”的系统，而是一个本地优先的产品推进和验证台：

> 把一个模糊的现实问题，逐步整理成可纠正的产品契约，比较产品路径，生成一个受控的 Web 原型，验证软件是否能运行，并为后续真实任务观察准备测量计划。

当前已经能够较可靠地证明的是：

- 某个想法是否被结构化成了 Product Contract；
- 人是否确认了关键价值、问题和结果边界；
- 某条产品路径是否被选择；
- 生成的 Web 原型是否在本地覆盖范围内构建、启动并通过浏览器检查；
- 一个交付包由哪个契约、生成 Job、执行 Job 和修复 lineage 产生。

当前不能直接证明的是：

- 用户是否真的需要这个产品；
- 产品是否改变了用户行为或体验；
- 产品是否有市场价值；
- 结果是否可以推广到更多用户；
- 产品是否已经达到生产部署、安全、合规或企业治理要求。

因此，看到“成功”时必须先说明成功指的是哪一层：模型提案、人工确认、软件运行、交付包，还是现实用户结果。

## 1.5 本地启动方式

要继续使用 Product Studio 工作台，需要同时运行 API 和 Web。使用两个 PowerShell 窗口：

```powershell
# 窗口 1：仓库根目录
python -m uvicorn psyteardown.api.app:app --host 127.0.0.1 --port 8000

# 窗口 2：
Set-Location .\studio
npm run dev -- --host 127.0.0.1
```

访问 `http://127.0.0.1:5173/`。下载后的交付包单独查看不需要这两个进程；只有工作台预览、反馈和下一轮迭代才需要 API + Web。

## 2. 完整操作流程

主链路如下：

```text
不完整想法
  → ProductIntent 提案
  → 人确认
  → ProblemModel 提案
  → 人确认
  → OutcomeContract 提案
  → 人确认
  → ProductThesis 候选与选择
  → WebProductGenerationContract
  → 人确认
  → 生成 Web workspace
  → B4 本地构建/预览/Chromium/axe 验证
  → B5 受限修复（如需要）
  → B6 交付包
  → 预览与显式反馈
  → C2 MeasurementPlan
  → 人确认
  → C1 真实任务观察（当前默认暂停）
```

### 2.1 输入一个不完整想法

从一句愿望、现实困扰、商业目标或现有产品问题开始。它进入 `ProductIntent`，而不是直接变成产品功能列表。

需要逐步明确：

- 为谁改变什么；
- 发生在什么情境；
- 当前已知约束；
- 明确不做什么；
- 隐私、资源和可撤销边界。

当前原始输入仍可能保存在本地 Job 中；使用真实 provider 时，按 C0 决策，完整输入和已确认上游对象会发送给 provider，transcript 保留在本机，不进入交付包。当前没有自动脱敏。

### 2.2 建立 Product Contract

#### ProductIntent

回答“想改变什么现实”。模型可以改写和整理，但必须由人纠正、确认。

#### ProblemModel

回答“目前如何理解现实”。它要区分：

- 有来源的事实；
- 竞争性解释；
- 尚未知晓的问题；
- 下一步验证方式。

至少保留竞争性解释，不能因为提案写得完整就把解释当成事实。

#### OutcomeContract

回答“怎样才算产生了结果”。它包括：

- 目标人群和情境；
- 目标结果；
- 可操作的成功指标和阈值；
- 禁止结果；
- 停止条件；
- 资源/注意力/数据边界；
- 需要的现实证据类型；
- 最低交付成熟度。

这三个对象确认后，才形成可以作为后续输入的 Product Contract。确认表示“这是当前工作假设和价值边界”，不表示现实已经验证。

### 2.3 生成并选择 ProductThesis

系统可以生成多条机制、实现和验证方式不同的产品路径。比较时重点看：

- 机制是否对应问题模型中的竞争解释；
- 关键未知是什么；
- 最低成本的证伪方式是什么；
- 失败风险和维护负担是什么；
- 哪条路径最值得先做，而不是哪条文字最完整。

选择 thesis 是人的决定，不能因为模型把某条路径写得最有说服力，就自动视为正确。

### 2.4 确认可运行的 Web 产品契约

选定路径后，形成 `WebProductGenerationContract`，冻结：

- 任务；
- 页面和状态；
- 成功/失败条件；
- 停止和恢复边界；
- 主流程；
- 浏览器检查。

当前首条主流程是一个本地 Decision Brief：

```text
写下这次要做的决定、背景和回看时间
  → 分别记录每个选项的决策标准、已知信息和顾虑
  → 查看并核对两列记录
  → 记录自己的倾向和下一步要核实的问题
  → 导出 JSON 简报
  → 需要时导入 JSON 重新打开
```

导出是显式的本地文件动作，不使用网络、浏览器持久化存储或自动上传；刷新页面前未导出的内容会丢失。它解决的是“留下一个可带走的成果”，还不代表长期决策结果已经改善。

如果工作台已经有旧 Web 契约，点击“重新生成 Web 契约提案”只会产生新的 `proposed` revision；先审阅，再点击“确认 Web 生成契约”，之后才可以生成新的 workspace、B4 和 B6。不会自动覆盖旧交付包。

### 2.5 生成、运行和导出

生成路径主要有两种：

- `deterministic_fake`：默认离线、稳定，用于验证 Product Studio 工作流；
- `real`：显式选择真实 DeepSeek provider，用于验证真实模型 proposal 或源码生成路径。

真实模型输出仍必须经过人工审阅和静态门禁。之后 B4 在本地执行：

1. 安装依赖；
2. 构建 workspace；
3. 启动 loopback 预览；
4. 运行 Chromium 任务检查；
5. 运行 axe 检查；
6. 保存安全错误摘要和 checkpoint。

失败时可以进入 B5 受限修复。修复只允许白名单补丁，原始 workspace 不直接覆盖，修复后必须重新验证。

B6 导出的交付包包括源码、构建物、验证产物、文件 hash、来源 revision 和未验证声明。它证明的是本机覆盖范围内的软件验证，不是用户价值或市场结果。

### 2.6 预览、反馈和迭代

B6 导出后有两条不同的使用路径，不能混为一个“打开包”动作：

1. **继续在 Product Studio 里试用并反馈**：留在“产品工作台”，使用交付包下方的内嵌预览；反馈会绑定到交付包、执行 revision、契约 revision、页面、任务和状态。
2. **在本机单独查看已验证版本**：下载 ZIP 后解压，进入解压目录的 `build/`，用静态 HTTP 服务打开：

   ```powershell
   Set-Location .\<bundle>\build
   python -m http.server 4174 --bind 127.0.0.1
   ```

   浏览器打开 `http://127.0.0.1:4174/`，结束时在服务窗口按 `Ctrl+C`。不要双击 `build/index.html`；`file://` 不是当前构建的验证路径。

下载的 `build/` 是已经验证过的静态交互产物，不需要先 `npm install`。只有要重新开发/构建源码时，才进入 `source/` 执行 `npm install --ignore-scripts`、`npm run build` 和 `npm run preview`。交付包中的 `source/` 不包含 `node_modules/` 和 `package-lock.json`，因此它不是可直接恢复的完整开发工作区。


用户可以在预览中提交显式反馈，并将反馈绑定到：

- 交付包；
- 执行 revision；
- 契约 revision；
- 页面、任务和状态。

反馈可以形成下一次 proposed revision，但平台不会自动判断反馈是否正确，也不会保证每条反馈都会改变源码。新的契约 revision 需要重新确认、生成、验证和导出。

### 2.7 C2 测量计划

在已确认 `OutcomeContract` 上，C2 会派生 `OutcomeMeasurementPlan`，明确：

- 每个目标如何测量；
- 来源层；
- 证据上限；
- 阈值；
- 缺失和矛盾处理；
- 禁止结果 guardrail；
- 样本、同意、撤回和停止条件。

`MeasurementPlan` 只回答“怎样测量”，不创建现实观察，也不提升 Outcome Evidence。

### 2.8 C1 真实任务观察

当前默认设置为：

```text
PSYTEARDOWN_C1_TRIAL_ENABLED=0
```

所以当前不会自动启动真实试用。只有负责人明确开启，并且同时具备已确认 C2 计划、当前 Web 契约、成功 B6 交付包，以及 host 对产品核心任务的明确可用性确认后，才可以启动 C1 envelope。B4/B6 只证明软件验证，不证明产品已经适合真实任务。

C1 流程为：

1. 启动 trial envelope；
2. 展示同意说明；
3. 生成随机 participant ID；
4. 主持一个明确任务；
5. 记录结构化 measure；
6. 记录成功、放弃、技术失败、无响应等路径；
7. 由与 host 分离的具名 reviewer 审查；
8. 可以 close/stop trial；
9. withdrawal 会擦除相关 C1 源记录；
10. envelope 关闭后 30 天，本地 cleanup 会清理源记录。

C1 当前只接受 `research_observation`，证据上限为 `observed`。这仍然不是可泛化的产品效果证据。

## 3. 结果是怎样得来的

### 3.1 结果来源链

每类结果都有不同来源：

```text
用户输入
  + provider
  → proposal revision
  + 人工纠正/确认
  → confirmed Product Contract revision
  + 选定 thesis
  → Web generation contract revision
  + generation Job
  → workspace
  + B4 execution Job
  → software verification result
  + B6 materialization
  → delivery bundle
```

真实结果则走另一条链：

```text
OutcomeContract
  → C2 MeasurementPlan
  + 明确任务、同意和参与者
  → C1 Observation
  + 独立人工 reviewer
  → 探索性 EvidenceReview
```

对象之间通过 revision、来源、执行 Job、delivery bundle、consent receipt 和 observation pin 关联。上游 revision 改变时，下游可能被标记为 `stale` 或 `review_required`，不能静默继续当作当前结果使用。

### 3.2 证据等级不能混用

| 看到的结果 | 实际说明 | 不能推出 |
|---|---|---|
| 模型 proposal | 模型对输入的结构化建议 | 现实事实或用户结果已经成立 |
| 人确认的 Contract | 当前工作假设和价值边界已被人确认 | 假设已经被现实验证 |
| ProductThesis | 一条候选机制和验证路径 | 机制一定有效 |
| Web 原型 | 软件实现了一条流程 | 用户一定理解、喜欢或持续使用 |
| Build/Playwright/axe 通过 | 本地覆盖范围内的软件检查通过 | 产品改变了真实行为 |
| B6 交付包 | 有来源和 hash 的本地交付物 | 已达到生产质量 |
| C2 MeasurementPlan | 已声明如何测量 | 结果已经发生 |
| C1 Observation | 某个具体任务中的结构化观察 | 可以推广到所有用户 |
| EvidenceReview | 具名 reviewer 审查了观察 | 已完成充分的市场或因果验证 |

当前仓库中的真实参与者数据仍为零。因此，任何“提高专注”“减少打断”“用户有效”等结论，不能从自动化测试或交付包直接推出。

## 4. 结果不好时的诊断方法

原则是：

> 先找链条中第一次偏离预期的位置，再修复对应层级；不要直接从最终页面跳到“产品想法错了”。

### 4.1 先定义“坏”是哪一种坏

| 表现 | 首先检查 | 典型处理 |
|---|---|---|
| 解决了错误的问题 | ProductIntent / ProblemModel / OutcomeContract | 回到上游纠正并创建新 revision |
| 问题理解对，但机制无效 | ProductThesis 和关键假设 | 重新比较、低成本证伪或换 thesis |
| 产品方向对，但页面流程错误 | WebProductGenerationContract / primary flow | 先修 Web 契约，再重新生成 |
| 产品契约正确，但代码错误 | generation Job / template / model output | 检查静态门禁、生成 lineage 或受限修复 |
| 构建、预览或浏览器检查失败 | B4 checkpoint、error code、safe summary | 区分环境、源码、浏览器和可访问性问题 |
| 软件能运行，但真实任务结果不好 | C2 plan / C1 observation / reviewer | 检查任务、情境、测量和机制，不把它归因于构建问题 |
| 改了上游后旧结果变差 | revision、stale、recorded impact | 重新确认、生成、执行和导出，不复用旧交付包 |

### 4.2 推荐的逐层排查顺序

1. **目标层**：为谁改变什么，是否一开始就错了？
2. **问题层**：事实、解释和未知有没有混淆？竞争解释是否被过早关闭？
3. **结果层**：指标是否真的代表目标结果？阈值、禁止结果和停止条件是否可执行？
4. **机制层**：选定的 ProductThesis 是否真的回应了问题模型？
5. **契约层**：Web contract 是否明确写出任务、状态、成功和恢复？
6. **实现层**：生成的源码是否忠实实现 contract？
7. **软件验证层**：B4 失败在哪个 checkpoint？是安装、构建、预览、浏览器、断言还是 axe？
8. **真实体验层**：真实任务中究竟发生了什么？是否有观察、失败原因和 reviewer？

### 4.3 三个常见误判

#### “测试都通过了，但用户体验不好”

这并不矛盾。测试证明的是软件在覆盖范围内行为正常，不证明用户目标实现。应该进入 C1/C2 的真实任务观察，而不是继续增加软件单测来替代用户验证。

#### “模型生成得很完整，所以方向应该正确”

完整度不是事实性，也不是有效性。模型输出只是在给定输入和 prompt 下形成的 proposal。需要回到 ProblemModel、OutcomeContract 和 ProductThesis 检查。

#### “修复成功了，所以产品结果变好了”

B5 修复成功只说明某个软件执行问题被修复。它不会改变现实结果证据等级。

## 5. 当前实现实际划定的使用范围

当前代码和首条切片有意把体验限制在以下范围：

### 5.1 用户范围

- 自主管理工作的知识工作者；
- 自由职业者、独立创作者或小团队中的个人贡献者；
- 主要使用桌面浏览器；
- 不处理雇主监控、团队审批、多租户和复杂组织权限。

### 5.2 产品范围

- 本地优先的 Web/SPA 原型；
- 一个主要用户；
- 一条清晰的 primary journey；
- 少量页面和状态；
- 可以在本机生成、构建、预览和验证。

当前首条体验切片围绕：

> 在有时间边界的工作时段减少非计划切换，同时保留对紧急联系的明确、可撤销控制。

### 5.3 明确不在当前范围

- 原生移动应用；
- 硬件和工业设计交付；
- 浏览器外的系统级通知代理；
- 跨应用自动识别并控制所有通知；
- 员工监控、生产力评分、排行榜；
- 多人协作、身份、权限和租户隔离；
- 生产级部署、自动发布和无人批准部署；
- 跨浏览器、移动端和视觉回归保证；
- 高风险医疗、法律、金融或安全结论；
- 通过自动测试推导真实用户效果。

### 5.4 C1 数据和试用范围

C1 是本地主持的小试用，不是行为监控系统。它只记录：

- 随机 participant ID；
- 结构化 measure 值；
- 任务完成状态；
- 人工观察时间。

不记录屏幕、键鼠、通知正文、消息正文、截图、遥测或参与者原始文本。C1 默认暂停；即使开启，也只能先按：

```text
participant_n = 1
session_k >= 1
```

理解结果。同一人多次 session 仍然是一个 participant，不能满足当前 C2 计划的 `minimum_n=3`，也不支持泛化效果声明。

## 6. 建议的当前使用方式

### 适合现在使用

- 澄清一个模糊产品想法；
- 把事实、解释、未知和价值边界分开；
- 比较多个产品机制；
- 生成一个小而明确的 Web 原型；
- 检查原型是否能构建、启动和完成主流程；
- 形成可审查的测量计划；
- 在 C1 明确开启后进行受控的 N=1 本地探索。

### 不适合现在使用

- 直接作为生产系统上线；
- 处理真实敏感信息或未经审查的企业数据；
- 做用户普遍需求、市场规模或商业成功判断；
- 做医疗、法律、金融、安全等高风险决策；
- 做员工监控或生产力评分；
- 让模型自动批准产品方向、证据或发布；
- 以自动化测试、模拟用户或模型解释冒充现实结果。

## 7. 每次使用前后的最小检查表

### 开始前

- [ ] 我能用一句话说明“为谁改变什么”；
- [ ] 我写出了明确不做什么；
- [ ] 我知道当前哪些是事实、哪些是解释、哪些仍未知；
- [ ] 我有一个可操作的结果指标和失败/停止条件；
- [ ] 我只选择一个主要用户和一条主要任务路径；
- [ ] 如果使用真实 provider，我没有把不应发送的数据放入输入。

### 生成后

- [ ] 我确认了 Product Contract，而不是直接接受模型提案；
- [ ] 我比较过至少两条有差异的产品路径；
- [ ] 我确认 Web contract 的任务、状态、成功和恢复边界；
- [ ] 我区分了生成失败、执行失败和产品方向失败；
- [ ] 我查看了 B4 的具体 checkpoint 和错误摘要；
- [ ] 我知道当前交付包绑定的契约和 execution revision。

### 宣称结果前

- [ ] 我说明了结果属于 proposal、contract、software verification 还是 real-world observation；
- [ ] 我没有把 C2 MeasurementPlan 当成观察结果；
- [ ] 我没有把 build/Playwright/axe 通过当成用户效果；
- [ ] 如果有 C1 观察，我记录了参与者、任务、情境和非成功路径；
- [ ] EvidenceReview 已由与 host 分离的具名 reviewer 完成，或明确标为未审查；
- [ ] 我没有把 N=1 或同一人多次 session 当成多个用户。

## 8. 维护和权威来源

当本指南与代码或其他文档不一致时，按以下顺序核对：

1. 当前代码、迁移和实际测试结果：说明系统实际上做什么；
2. `CURRENT_STATE.md`：说明当前项目事实和验证基线；
3. `ROADMAP.md`：说明工作包和退出门槛；
4. `DECISION_REGISTER.md`：说明已接受方向、原型假设和待决问题；
5. iteration 记录：说明某一批实现当时如何完成，不应静默改写历史。

本指南是当前使用说明和边界说明，不把路线图中的计划写成已经实现的功能，也不把软件测试升级为现实证据。

