# Iteration：B8 反馈驱动的迭代与版本差异

- 日期：2026-09-24
- 状态：Closed
- 路线图工作包：Phase B
- 类型：Domain / Command / API / UI

## 目标

把一条或多条显式反馈 pin 到新的 Web generation contract **proposal**，要求人确认后重新走 B3→B4→B6，并在工作台展示两个交付 revision 的契约/源码差异与反馈的处理状态。反馈本身不自动改变项目状态。

## 基线

- B7m 已关闭（`2373c4f`）；`pytest -q` 523 passed、3 skipped；前端 22 passed；E2E 2 passed。
- `PreviewFeedback` 可以创建、列出和撤回，但尚未有任何消费者。
- 当前 B2 Web generation contract 提案由人直接从 Product Thesis "授权探索" 或 "选择" 触发，没有反馈输入。

## 非目标

- 不让反馈自动确认新的 contract（仍需人工确认）；
- 不在本批次处理多轮迭代链或版本树视图；
- 不做反馈优先级、聚合或自动分类；
- 不增加新的 feedback 字段或自动任务完成度；单纯把 submitted feedback 转成可审查的 contract proposal。

## 决策

B8 首条切片决定（2026-09-24）：

- **PS-O013 decided_for_first_slice**：人一次选择**一条** submitted feedback，触发**一条** Web generation contract proposal Job；Job 的 `input_dependencies` 包含前一个 confirmed contract + 该条 feedback。首条切片不做反馈聚合、批量选择或独立"改进意图"对象。
- **PS-O014 decided_for_first_slice**：新 contract proposal 必须 pin 前一个 confirmed contract 作为 baseline（类似 B5 repair pin 失败的 execution）；provider 只接收 baseline contract + 单条 feedback 的 ID/anchor/category；**反馈正文不进入 provider 或契约**（否则契约 revision 不可变，会破坏 B7 撤回即擦除），也不接收原始 Intent/ProblemModel。这让差异可追溯。
- **PS-O015 decided_for_first_slice**：首条切片只比较**文件级 SHA256**（哪些文件变了、新增、删除），不做行级 diff 或语义摘要。工作台显示两个 bundle 的文件清单对比与 feedback 的 `submitted`/`incorporated`/`deferred` 状态（人工标记，不自动推断）。

## 实施计划（实际执行）

1. ✅ PS-O013/O014/O015 按首条切片决定（见上）；
2. ✅ `ProductProposalJob.kind` 仍为 `web_generation_contract`，新增可选 `feedback_id`；带反馈时 `input_dependencies` = baseline contract + preview_feedback，`result_object_id`/`result_expected_revision` 固定为 baseline，产出同一 contract 聚合的下一 revision；
3. ✅ fake provider `propose_web_generation_contract_from_feedback`：保留全部 baseline ID，只追加一条引用反馈 ID + 类别的验收检查与 `preview_feedback` source ref；**不复制反馈正文**；
4. ✅ API：`POST /proposal-jobs` 接受 `feedback_id`；`POST /preview-feedback/{id}/disposition`；`GET /delivery-bundles/{id}/diff?base_bundle_id=`；
5. ✅ 工作台：反馈条目“基于此反馈提出新契约”、处理状态标记；修订提案说明；交付版本差异面板（契约变化、文件变化、来源反馈）。

## 验收条件

- 至少一条 submitted feedback → 新 contract proposal → 人确认 → B3→B4→B6 的完整链路有自动化测试；
- 工作台可以从预览反馈触发新迭代、查看契约差异和源码差异；
- 反馈本身不会因为生成新 proposal 而改变状态（submitted 保持 submitted）；
- Python/前端测试、E2E、OpenAPI drift 和 production build 通过。

## 实施记录

1. 首轮实现把 `feedback_id` 加入领域 Job 但未加入 `ProductProposalJobResponse`（`extra="forbid"`），导致所有 proposal job 响应 422；同时引用了不存在的 `application.feedback_service`，且 fake provider 引用了不存在的类型/字段。已全部重写，而非打补丁。
2. 反馈不在 product repository 中，`_inputs_are_current` 原本无法看到它：新增 `PreviewFeedbackReader` 并由 app 注入同一 feedback repository（SQLite 为同一连接；InMemory 由 app 共享实例）。反馈按身份而非 revision pin：处理状态变化不使 Job stale，撤回则使 Job `stale_input` 且不提交任何结果。
3. 隐私：首版 provider 若把反馈正文写入契约，会让 B7“撤回即擦除”失效（契约 revision 不可变）。最终只使用 anchor、类别与 ID。
4. 反馈 revision 不再固定 r1/r2：处理状态是一次新 revision；撤回始终是“当前 revision + 1”的墓碑并清空处理状态；SQLite `secure_delete` 下正文仍从文件中消失（新增测试）。
5. 真实发现：在确定性模板路径上，修订后的契约（新增验收检查）产生**字节相同的源码与构建**；diff 只显示 `DELIVERY.md`、`bundle-manifest.json`、`verification/execution-summary.json` 变化。测试锁定这一事实，工作台明确提示“源码与构建未变化”。只有 B7m 模型路径或人工修改能让反馈真正改变产品。
6. `_fingerprint` 未加 `feedback_id` 字段：反馈已在 dependencies 中，额外字段会改变所有既有 Job 的 fingerprint。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain | `ProductProposalJob.feedback_id` 与校验；`PreviewFeedback.disposition`、可变长 revision 链；`SourceReference.source_type=preview_feedback` | `src/psyteardown/product/models.py` |
| job/provider | 反馈迭代分支、`PreviewFeedbackReader`、撤回即 stale；fake 修订只加检查不复制正文 | `src/psyteardown/product/{jobs,providers}.py`、`tests/product/test_jobs.py` |
| feedback/delivery | `set_disposition`；`diff_bundles`（sha256 + 契约集合 ID 级变化） | `src/psyteardown/product/{feedback,delivery}.py`、`tests/product/test_feedback.py` |
| API | proposal `feedback_id`、disposition、bundle diff；OpenAPI/types 重生成 | `src/psyteardown/api/*`、`tests/api/test_feedback_iteration.py`、`studio/openapi.json` |
| UI | 迭代入口、处理状态、修订说明、版本差异面板 | `studio/src/views/{PreviewFeedbackPanel,WorkbenchView,ProjectStudio}.tsx` 与测试 |

## 决策与偏差

- 计划中的“新 kind / 独立命令 DTO”未采用：沿用 `web_generation_contract` kind + 可选 `feedback_id`，因为结果仍是同一 contract 聚合的 revision。
- 处理状态（disposition）是 B7 反馈模型的新字段，与非目标“不增加新的 feedback 字段”存在偏差；这是 PS-O015 显示“处理状态”的最小必要字段，只能由人显式设置。
- 未做 B8 专项真实 npm/Chromium 链路：本批未改动 B3/B4 执行代码，B4 使用 fake runner 覆盖；真实链路沿用 B7m 2026-09-24 结果。

## 验证

- `pytest -q`：527 passed、3 skipped、2 warnings（新增 B8 API 2、feedback 1、jobs 1、OpenAPI drift 重新生成）。
- 前端 `vitest`：24 passed；`npm run build`（含 OpenAPI 生成与 `tsc -b`）成功；Chromium E2E 2 passed。
- 覆盖链路：submitted feedback → iteration Job（幂等）→ proposed r+1（ID 不变、正文未复制）→ 人工确认 → B3 → B4（fake runner）→ B6 → diff → disposition → 撤回（正文清除、状态复位）；撤回后 Job `stale_input` 且契约不变。
- 证据边界：只证明软件在覆盖范围内的行为；反馈仍是 `user_report`，迭代不构成用户结果证据。

## 数据与迁移

- SQLite 反馈 JSON 向后兼容：旧行缺 `disposition` 时默认为 `pending`；旧 r2 墓碑仍有效。旧 proposal Job 缺 `feedback_id` 默认为 `None`，fingerprint 不变。
- 无表结构变更。

## 遗留项与风险

- 模板路径下反馈迭代不会改变产品；需要让模板消费验收检查，或把迭代与 B7m 模型生成结合（模型仍只收已确认契约，不收反馈正文）。
- diff 只到文件 sha256 与契约集合 ID；无逐行差异、无视觉差异。
- 契约 `source_refs` 会随迭代累积；多轮迭代链与版本树视图未做。
- 单用户 actor；处理状态无多人审阅。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（PS-O013/O014/O015、PS-H015）
- [x] `EVOLUTION_LOG.md`
- [x] README（ledger 入口）

## 下一最小工作包

B9：让反馈迭代能真正改变产品——模板消费契约验收检查，或在已确认修订契约上走 B7m 模型源码生成；随后做 Phase B 出口复核（部署级隔离、视觉回归/跨浏览器 Gate 仍未解决）。
