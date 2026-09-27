# Iteration：B7m 真实模型源码生成切片

- 日期：2026-09-23
- 状态：Closed
- 路线图工作包：插入在 B7 与 B8 之间（B8 之前先验证“生成器本身”）
- 类型：Decision / Provider / Domain / Execution Gate / API / UI

## 目标

让 B3 在人显式选择时，用真实模型（DeepSeek）根据**已确认的 Web 生成契约**写出 `src/App.tsx` 与 `src/styles.css`，
其余模板文件保持固定；模型输出先经静态门禁，再由 B4 用**从契约确定性生成**的 Playwright/axe 测试真实验证，
以检验 B2–B7 的门禁与数据结构在真实模型输出下是否成立。

## 基线

- B7 已关闭（`cecd99a`）；`pytest -q` 504 passed、3 skipped；前端 20 passed；E2E 2 passed。
- B3 的 App.tsx 与浏览器测试都是硬编码模板：无论契约写什么，产物都是同一页三个按钮。
- PS-O011、PS-O012 open；仓库已有 `LLMProvider`/`DeepSeekProvider`，`.env.local` 有 DeepSeek key。

## 决策（用户于 2026-09-23 选择）

- Provider：DeepSeek（复用 `psyteardown.llm.deepseek.DeepSeekProvider`，零新依赖）。
- PS-O011：只发送人已确认的 Web 生成契约（标题、页面、任务、状态、内容槽位、验收检查）；不发送原始输入、Intent、ProblemModel、OutcomeContract、Thesis；
  每次模型调用的请求与响应全文保存在本地 job 转写目录（workspace 之外，不进入交付包）供审查，job 记录 sha256。
- PS-O012：每个模型 job 由人显式触发；输出通过静态门禁才写入 workspace，再经 B4 真实验证才能导出；
  每 job 最多 2 次模型调用（重试时只回传上一次静态门禁拒绝原因，不回传构建日志）；B5 修复仍为确定性白名单，不调用模型。

## 范围

- `ProductSourceModel` 端口 + DeepSeek 适配；fake 实现用于测试（不触网）。
- `ProductGenerationJob.provider = "model_source"`、`materialization_kind = "model"`、`model_calls` 记录。
- 静态门禁：import 白名单（`react`、`./styles.css`）、禁止网络/存储/父窗口/动态代码/外链、尺寸上限、契约 ID 必须出现。
- 契约派生的 DOM 协议与测试：`data-screen-link`/`data-screen-id`/`data-task-id`/`data-slot-id`、唯一 `role="status"` + `data-state-kind`。
- API：创建 job 时 `source: template | model`；`/product-source-model-policy`。
- UI：“用模型生成源码”入口、外发说明、模型调用记录。
- B6 接受 `model` lineage 并在交付说明中写明模型与未审阅声明。

## 非目标

- 不让模型改契约/论题链（仍为 fake provider）；不让模型写测试、依赖、配置；
- 不做模型修复、不做流式、不做后台 worker；
- 不做费用金额核算（只计调用次数与 token 用量）。

## 验收条件

- 模型输出违反门禁 → job `failed` / `model_output_rejected`，workspace 不写入，转写仍保留；
- 未配置 provider → 409 `domain_gate`；
- 契约派生测试对模板无关、对每个页面/任务/必需槽位都有断言；
- 真实 DeepSeek → B4 → B6 → B7 至少一次端到端结果（成功或失败）如实记录；
- Python/前端测试、OpenAPI drift、生产构建与 E2E 通过。

## 实施记录

1. 新增 `ProductSourceModel` 端口与 DeepSeek OpenAI-compatible 适配器；调用保留 provider/model、token usage、耗时和 request/response hash，完整转写落在 workspace 外的本地目录。
2. 新增 `ProductGenerationJob` 的 `model` lineage、最多两次调用预算、静态源码门禁、契约派生 Playwright/axe 测试和 transcript 查询 API；拒绝或 provider 错误不会创建 workspace，重试只携带上一轮门禁原因。
3. 工作台增加模型可用性/外发边界、调用记录和受限重试入口；B6 交付说明标记模型源码未经人工审阅，B7 仍只提供显式反馈。
4. 发现并修复模型回复解析边界：必须严格按顺序只包含一个 TSX 与一个 CSS fenced block；provider 返回无效 JSON 或非文本 content 时统一记录为 `model_call_failed`。
5. 2026-09-24 使用真实 DeepSeek 执行一次独立链路：1 次调用接受，随后 B4 install/build/run/browser 全部成功，B6 交付包创建成功；未将完整 prompt/response 放入本记录。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain | `ProductGenerationJob.materialization_kind=model`、`ModelCallRecord`、固定模型预算与 provenance | `src/psyteardown/product/models.py`、`src/psyteardown/product/generation.py` |
| provider/gate | DeepSeek 适配器、契约最小输入、源码静态门禁、契约派生浏览器测试 | `src/psyteardown/product/source_model.py`、`tests/product/test_source_model.py` |
| API | source policy、model job、transcript 和 retry endpoints；OpenAPI/types 重生成 | `src/psyteardown/api/generation_jobs.py`、`tests/api/test_source_model_api.py`、`studio/openapi.json` |
| UI/delivery | 模型入口、边界说明、调用记录、受限重试和 delivery provenance | `studio/src/views/{ProjectStudio,WorkbenchView}.tsx`、`src/psyteardown/product/delivery.py` |
| real-e2e | 真实模型到交付包的红acted summary | [`tmp/b7m/live-eval-20260924-101831-802d4efc/summary.json`](../../../tmp/b7m/live-eval-20260924-101831-802d4efc/summary.json) |

## 决策与偏差

- PS-O011 在首条切片范围内落实为：只发送已确认 Web generation contract；完整 transcript 仅本机保存，workspace 和 delivery bundle 不包含 transcript。
- PS-O012 在首条切片范围内落实为：模型 job 显式触发、最多两次调用、门禁失败可携带原因重试；B5 仍是确定性 repair，不调用模型。
- 本批没有把真实模型成功升级为 Product Contract、Outcome 或用户结果证据；真实链路只证明 provider、门禁、执行和导出在这一次输入上可运行。

## 验证

- 命令：`pytest -q`；`npm test -- --run`；`npm run build`；真实链路由 `python tmp/b7m/chain.py deepseek <isolated-dir>` 执行。
- 结果：Python 端新增模型/解析/provider 测试通过；真实 DeepSeek：generation `succeeded`、1 次 accepted call（约 9.0s）；B4 install/build/run/browser 全部 `succeeded`；B6 bundle created；总耗时约 50.0s，进程退出码 0。
- 现实证据边界：这证明一次真实 provider 输出通过软件门禁并完成本机执行/导出；不证明模型稳定性、费用可接受性、代码安全完备性、真实用户结果或部署级隔离。

## 数据与迁移

- SQLite job JSON revision 向后兼容：旧 template/repair job 默认无 `model_calls`；新增 transcript 存储为 workspace 外独立本地文件，不进入交付包。
- API/OpenAPI 增加 `source`、policy、model call record 和 transcript response；不改变既有 template/repair 创建语义。

## 遗留项与风险

- provider/model、token 与耗时目前只作为调用 provenance，不做金额核算；PS-O011/PS-O012 的保留期限、费用和多租户策略仍需后续复核。
- 真实链路仅一次，尚无稳定性评测、跨模型比较、跨浏览器或部署级隔离；B8 仍不得自动把反馈转成已确认契约。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（PS-O011/PS-O012）
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档（README）

## 下一最小工作包

B8：把一条显式反馈 pin 到新的 Web generation contract proposal，要求人确认后重新走 B3→B4→B6，并展示两个交付 revision 的契约/源码差异与反馈处理状态。
