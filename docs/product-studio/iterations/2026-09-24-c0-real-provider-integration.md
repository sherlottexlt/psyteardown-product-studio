# C0 — Phase C 前置：真实 provider 接入与端到端链路

- 工作包 ID：C0
- 开始日期：2026-09-24
- 关闭日期：2026-09-25
- 状态：Closed
- 路线图工作包：C0
- 类型：Provider / Workflow / API / Validation
- 前置条件：Phase B Exit Review 完成
- 预计范围：决策 + 实现 + 至少一次端到端真实链路验证

> 历史阶段性 `blocked`/`verified` 行保留在正文中，分别表示外部 API key 阻塞和后续真实运行结果，不是本 iteration 的生命周期状态。

## 目标

Phase C 的目标是"真实结果验证"，需要真实生成的产品才能进行真实任务试用。本工作包作为 Phase C 前置条件，需要：

1. **决定真实 provider 的输入保留策略**：哪些字段保留？保留多久？如何处理敏感输入？
2. **决定真实 provider 的预算与费用计量**：金额预算？token 预算？失败重试策略？
3. **实现至少一个真实 provider 适配**：推荐 DeepSeek 或 Claude（B7m 已验证 DeepSeek 可用）
4. **从 ProductIntent 到 B6 交付包跑通至少一次端到端真实链路**
5. **记录真实链路的失败模式、成本与时间**

## 非目标

- 不要求多次稳定运行（稳定性评估在后续工作包）
- 不要求支持多个 provider（首个可用即可）
- 不要求实现金额级预算控制（先用 token/调用次数级预算）
- 不要求实现真实模型修复（B5 deterministic planner 保持不变）
- 不要求实现部署级隔离或视觉回归（Phase B 已知差距，不在 C0 范围）

## 前置条件验证

- [x] Phase B Exit Review 已完成
- [x] B7m 已证明 DeepSeek 可以生成 Web 产品源码
- [x] B1–B9 全链路在 fake provider 下可演示且可恢复
- [x] 当前测试基线：527 passed、3 skipped、2 warnings

## 待决策问题

### 决策 1：输入保留策略

**问题**：真实 provider 接入后，用户输入（ProductIntent 的原始文本、ProblemModel 的事实来源、OutcomeContract 的指标等）会被发送给外部模型。需要决定：

1. 哪些字段发送给 provider？
2. 这些输入保留多久？是否提供删除/撤回机制？
3. 如何处理敏感输入（个人信息、商业机密等）？

**选项**：

- **A. 最小保留**：只保留生成 proposal 所需的最小字段（如 ProductIntent.value_proposition），其余字段（如 what_stakeholders_cannot_do）不发送；保留时间与 Job 生命周期一致，Job 删除时一并删除输入。
- **B. 完整保留 + 用户同意**：发送前明确告知用户哪些字段会发送给外部 provider，要求显式同意；保留时间与项目生命周期一致，提供项目级删除入口。
- **C. 完整保留 + 本地 transcript**：与 B7m 一致，完整发送，transcript 仅存本机，不入交付包；不提供自动删除，由用户管理项目目录。

**暂定方案**（待确认）：选项 C，与 B7m 保持一致。理由：首条切片为本地个人版，用户完全控制项目目录；后续 Phase D 多用户/托管版本时再引入显式同意与保留策略。

### 决策 2：预算与费用计量

**问题**：真实 provider 调用会产生实际费用。需要决定：

1. 如何限制单个 Job 的费用上限？
2. 如何限制单个项目的累计费用？
3. 失败或 stale 时是否重试？重试几次？

**选项**：

- **A. Token 预算**：每个 Job 限制最大 token 数（如 input 8000 + output 4000），超限返回 `budget_exhausted`；项目级无累计限制。
- **B. 调用次数预算**：每个 Job 限制最大调用次数（如 Product Contract 每对象 2 次，Web generation 2 次），与 B7m 一致；项目级无累计限制。
- **C. 金额预算**：每个 Job 限制最大金额（如 $0.10），需要实现费用计量与汇率转换；项目级累计限制（如 $1.00）。

**暂定方案**（待确认）：选项 B，与 B7m 保持一致。理由：调用次数预算实现简单且足够保护本地个人版用户；金额预算需要费用计量与汇率转换，可在 Phase D 多用户/托管版本时再引入。

### 决策 3：失败重试策略

**问题**：真实 provider 可能因为网络、限流、模型错误等原因失败。需要决定：

1. 是否自动重试？
2. 重试几次？间隔多久？
3. 哪些错误类型应该重试？哪些不应该？

**选项**：

- **A. 不自动重试**：失败立即返回 `provider_failed`，由用户显式重试（通过 Job retry API）。
- **B. 有限自动重试**：对于可重试错误（网络、限流、5xx），最多重试 2 次，指数退避（1s、2s）；对于不可重试错误（4xx、模型拒绝），立即失败。
- **C. 预算内重试**：在调用次数预算内自动重试，超预算后返回 `budget_exhausted`。

**暂定方案**（待确认）：选项 A，不自动重试。理由：本地个人版用户可以直接观察 Job 状态并显式重试；自动重试会增加复杂度且可能在用户不知情时消耗预算；后续可根据真实使用反馈决定是否引入自动重试。

## 实施计划

### 阶段 1：决策确认（预计 0.5d）

- [ ] 确认或修改上述三个决策的暂定方案
- [ ] 更新 `DECISION_REGISTER.md`，记录决策与理由
- [ ] 如果选择与 B7m 不同的方案，说明差异与原因

### 阶段 2：实现 Product Contract provider 适配（预计 1d）

- [ ] 复用 B7m `ProductSourceModel` 的 DeepSeek 适配器
- [ ] 为 ProductIntent、ProblemModel、OutcomeContract 创建独立 provider 端口
- [ ] 实现 DeepSeek 适配，发送已确认的上游对象 + 用户输入，接收 proposal
- [ ] 添加静态门禁：检查 proposal schema、必填字段、未知项数量等
- [ ] 添加预算控制：每对象最多 2 次调用（与 B7m 一致）
- [ ] 添加单元测试：验证 prompt 构造、响应解析、门禁与预算

### 阶段 3：实现 Product Thesis provider 适配（预计 0.5d）

- [ ] 为 ProductThesis batch Job 创建 provider 端口
- [ ] 实现 DeepSeek 适配，发送 ProblemModel + OutcomeContract，接收 3 个 thesis
- [ ] 添加静态门禁与预算控制
- [ ] 添加单元测试

### 阶段 4：集成到现有 Job 工作流（预计 0.5d）

- [ ] 修改 `ProductProposalJob` 支持 `provider="real"` 选项（默认 `fake`）
- [ ] 修改工作台 UI，增加"使用真实 AI 生成"开关与提示
- [ ] 修改 API，支持创建 Job 时指定 provider
- [ ] 保持向后兼容：fake provider 仍是默认，现有测试不受影响

### 阶段 5：端到端真实链路验证（预计 1d）

- [ ] 从浏览器创建项目，输入真实用户意图
- [ ] 使用真实 provider 依次生成 ProductIntent、ProblemModel、OutcomeContract
- [ ] 纠正并确认三个对象（如果 proposal 质量不足）
- [ ] 使用真实 provider 生成 Product Thesis 候选
- [ ] 选择一个 thesis，生成并确认 Web generation contract
- [ ] 使用真实模型（B7m `source="model"`）生成源码
- [ ] 执行 B4 构建与验证
- [ ] 导出 B6 交付包
- [ ] 记录每一步的成本（调用次数、input/output tokens）、时间与失败情况

### 阶段 6：失败模式与成本分析（预计 0.5d）

- [ ] 记录真实链路中的失败模式（网络、限流、模型拒绝、schema 不匹配等）
- [ ] 记录每个对象生成的平均成本与时间
- [ ] 识别成本热点（哪个对象最贵？哪个环节最慢？）
- [ ] 评估当前预算设置是否合理
- [ ] 记录用户体验问题（等待时间、错误提示、重试流程等）

## 验收条件

### 必须满足

1. **至少一次端到端真实链路成功**：从真实 provider 生成的 Product Contract 到真实模型生成的 Web 产品，并成功导出 B6 交付包。
2. **输入保留、预算与重试策略已决定并记录**：在 `DECISION_REGISTER.md` 中有明确决策与理由。
3. **provider 适配实现并有单元测试**：覆盖 prompt 构造、响应解析、门禁与预算。
4. **失败模式与成本已记录**：知道真实链路在哪些地方失败、为什么失败、成本是多少。
5. **fake provider 仍是默认且现有测试不受影响**：527 passed、3 skipped 基线保持不变。

### 可选（如果时间允许）

1. 多次真实链路运行，评估稳定性
2. 支持多个 provider（Claude、OpenAI 等）
3. 实现更精细的错误分类与提示

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|---|---|---|---|
| 真实 provider API 限流或不可用 | 无法完成端到端验证 | 中 | 准备备用 provider（Claude）；非高峰时段测试 |
| 真实 provider 生成质量不足 | 需要多次纠正或无法通过门禁 | 中 | 记录失败模式，后续优化 prompt；允许纠正与重试 |
| 真实链路成本超预期 | 单次测试成本过高 | 低 | 先用最小输入测试；预算控制已在 B7m 验证 |
| 网络或环境问题导致调用失败 | 无法完成验证 | 低 | 确保网络稳定；准备本地 proxy 或 VPN |
| 真实 provider 响应时间过长 | 用户体验差，测试耗时 | 中 | 记录等待时间，评估是否需要进度提示或异步 worker |

## 依赖与假设

### 依赖

- DeepSeek API 可用且稳定（B7m 已验证）
- 本地网络可以访问外部 API
- B7m `ProductSourceModel` 适配器可以复用

### 假设

- 首条切片为本地个人版，用户完全控制项目目录，不需要复杂的输入保留策略
- 调用次数预算足以保护用户，不需要金额级预算
- 真实 provider 生成质量与 B7m 一次成功的质量相当或更好
- fake provider 仍是大多数测试的默认选择，真实 provider 只在集成测试或真实使用时调用

## 下一步

C0 完成后，Phase C 的下一个工作包可能是：

- **C1 — 真实任务试用框架**：定义如何邀请真实用户试用生成的产品，记录任务完成情况，收集反馈。
- **C2 — Outcome Contract 指标测量**：将 Outcome Contract 的抽象指标转成可执行测量计划，区分运行事件、用户报告与正式 Evidence。
- **C3 — 多次真实链路稳定性评估**：运行 10+ 次真实链路，评估成功率、成本分布、失败模式频率。

具体优先级在 C0 完成后根据真实链路反馈确定。

## 实施记录

_本节在实施过程中更新，记录实际进展、发现的问题、范围变化和关键权衡。_

### 2026-09-24 — 创建 C0 记录

- 状态：done
- 创建原因：Phase B Exit Review 确认 Phase C 前置条件为至少一次真实 provider 端到端链路
- 三个待决策问题已列出暂定方案，等待确认

### 2026-09-24 — 阶段 1：决策确认完成

- 状态：done
- 决策确认：
  - PS-O017：输入保留策略 = 与 B7m 一致（完整发送，transcript 本地，用户管理项目目录）
  - PS-O018：预算与费用 = 每对象最多 2 次调用（与 B7m 一致），无项目累计限制，只记调用次数/token
  - PS-O019：失败重试 = 不自动重试，用户显式重试
- 已更新 `DECISION_REGISTER.md`

### 2026-09-24 — 阶段 2：实现 Product Contract provider 适配

- 状态：done
- 已完成：
  - 创建 `contract_model.py`：DeepSeek 适配器、系统 prompt、解析函数
  - Intent/Problem/Outcome/Thesis 的 4 个系统 prompt 定义
  - Intent 的完整 parse/build 实现
  - Problem/Outcome/Thesis 的完整 parse/build 实现
  - 在 `providers.py` 添加 `RealModelProductContractProvider` 类
  - 创建 `build_provider_from_env()` 工厂函数
  - 添加单元测试（4 个 Intent 测试通过）
  - 完整 product 测试套件通过（102 passed, 1 skipped）
- 边界：
  - Web generation contract 仍委托给 fake provider（B7m 负责模型源码生成）
  - Feedback iteration 仍委托给 fake provider（B8 使用 fake 修订）
  - 未实现预算跟踪（调用次数限制需在 Job 层实现）
  - 未实现 transcript 保存（需在 Job 层实现）

### 2026-09-24 — 阶段 5-6：端到端验证与失败模式分析

- 状态：blocked
- 已完成：
  - 创建端到端测试脚本 `test_c0_real_provider_e2e.py`
  - 测试覆盖完整链路：Project → Intent → Problem → Outcome → Thesis
  - 创建 DeepSeek API 连接测试脚本
  - 验证 API 调用流程（request 构造、超时、错误处理）
- 阻塞原因：
  - DeepSeek API 返回 401 Authorization Required
  - 环境变量 `DEEPSEEK_API_KEY` 存在但可能已过期或无效
  - 需要有效的 API 密钥才能完成真实链路验证
- 测试结果：
  - ✅ Provider 初始化成功（`RealModelProductContractProvider`）
  - ✅ Job 创建成功（`provider="real"` 参数正确传递）
  - ✅ Job 运行流程正确（选择了 real provider 实例）
  - ❌ API 调用失败（HTTP 401）
- 下一步（需要有效 API 密钥）：
  1. 配置有效的 `DEEPSEEK_API_KEY`
  2. 运行 `test_c0_real_provider_e2e.py`
  3. 记录成本（input/output tokens）
  4. 记录时间（每个步骤的耗时）
  5. 分析失败模式（网络、超时、解析错误、静态门拒绝）

### 2026-09-24 — C0 总结

- 状态：基础设施完成，待外部验证
- 已完成的阶段：
  - ✅ 阶段 1：决策确认（PS-O017/O018/O019）
  - ✅ 阶段 2：Product Contract provider 适配（`contract_model.py` + `RealModelProductContractProvider`）
  - ✅ 阶段 4：Job 工作流集成（`create_job(provider="real")`）
  - 🔄 阶段 5-6：端到端验证（测试脚本完成，API 密钥问题阻塞）
- 交付成果：
  - `contract_model.py`：DeepSeek 适配器 + 4 个系统 prompt + 解析函数
  - `RealModelProductContractProvider`：真实 provider 实现
  - `ProductProposalJob.provider`：支持 `"real"` 选项
  - `create_job(provider="real")`：运行时 provider 选择
  - 单元测试：4 个 Intent 解析测试
  - 端到端测试：完整链路测试脚本
- 代码质量：
  - 完整 product 测试套件通过（102 passed, 1 skipped）
  - 无回归，fake provider 仍是默认
- Phase C 前置条件：
  - ✅ 至少一次真实 provider 端到端链路（基础设施就绪）
  - ⏳ 需要有效 API 密钥完成实际验证


### 2026-09-25 — 阶段 5-6：真实完整链路验证完成

- 状态：verified
- 运行入口：`pytest -q -s tests/product/test_c0_real_provider_e2e.py`
- 配置修复：Product Studio 读取仓库根目录 `.env.local`（支持 `export NAME=value`），项目本地配置优先于旧的 Windows 用户级环境变量；本次使用 `deepseek-flash`。
- 真实链路：
  - ✅ DeepSeek ProductIntent
  - ✅ DeepSeek ProblemModel
  - ✅ DeepSeek OutcomeContract
  - ✅ DeepSeek ProductThesis（3 个候选）
  - ✅ deterministic Web generation contract（C0 明确不要求其使用真实模型）
  - ✅ DeepSeek B7m source generation；静态门禁通过
  - ✅ B4 真实本地 subprocess：install → build → loopback preview → Playwright/axe
  - ✅ B6 内容寻址交付包导出
- 真实运行证据（2026-09-25）：
  - 总耗时：100.22 秒
  - Product Contract + source model 调用：5 次
  - input tokens：5,788
  - output tokens：7,824
  - 金额：未计算；按 PS-O018 只记录调用次数/token
  - B4：69.04 秒，4 个执行步骤均 succeeded
  - B6 archive：108,257 bytes；sha256 `c632289ee4f36cfe78090a054aa44ddac0055bf16301a173cdc8e2b24acbead0`
  - 机器可读报告：`output/product-studio/c0-real-provider/project-168579c1f5b84e48b8a11f5676296c1b/c0-metrics.json`
- 阶段 6 失败模式：
  - 旧 Windows 用户级 key `****d571`：DeepSeek HTTP 401 `invalid_request_error`；已通过项目 `.env.local` 优先读取修复。
  - 未启用 JSON mode 时，`deepseek-flash` 偶发返回不可解析内容；已增加 `response_format=json_object`。
  - Product Contract prompt 曾与当前 Pydantic schema 漂移（Problem/Outcome/Thesis 字段）；已按实际领域模型修正，并加入安全的 schema 错误摘要。
  - 本次完整运行失败数：0。
- 仍明确保留的边界：Product Contract 的 Web generation contract 仍使用 deterministic fake；没有金额预算、自动重试、部署级隔离、视觉回归或真实用户结果证据。

### 2026-09-25 — C0 结论

- 状态：done
- 阶段 5-6 验收条件已满足：至少一次从真实 provider Product Contract 到真实模型源码、B4 验证和 B6 导出的完整链路成功；token、耗时和失败模式已记录。
- 下一最小工作包：C1 真实任务试用框架，或先执行 C3 多次真实链路稳定性评估；优先级待 Phase C 计划确认。

### 2026-09-25 — API 与工作台入口补齐

- proposal Job HTTP request 支持 `provider: deterministic_fake | real`，响应保留实际 provider 标识；默认仍为 fake。
- 默认 SQLite API app 在项目 `.env.local` 可用时装配 `RealModelProductContractProvider`；没有配置时 real 请求返回明确的 domain error，不影响 fake 路径。
- Product Contract 页面增加 fake/real 选择；Web generation contract 和反馈迭代仍显式使用 fake，避免把 deterministic contract provider 误称为真实模型。
- OpenAPI 与前端生成类型已更新；Python 全量回归 `532 passed, 3 skipped, 2 warnings`，前端 `24 passed`，production build 成功。
