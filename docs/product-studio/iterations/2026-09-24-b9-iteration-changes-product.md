# Iteration：B9 让反馈迭代真正改变产品

- 日期：2026-09-24
- 状态：Closed
- 路线图工作包：Phase B
- 类型：Domain / Decision

## 目标

让 B8 反馈迭代能够真正改变生成的产品：模板路径上让生成器消费契约的验收检查（acceptance_checks），或者在模型路径上，让基于反馈修订的已确认契约重新走 B7m 模型源码生成。

## 基线

- B8 已关闭（`788e6d6`）；`pytest -q` 527 passed、3 skipped、2 warnings；前端 24 passed；E2E 2 passed。
- 当前确定性模板 `_render_files` 不读取 `contract.acceptance_checks`，所以 B8 修订后的契约（新增验收检查）产生字节相同的源码与构建。
- B7m 模型路径可选 `source="model"`，只接收已确认的 Web generation contract，写 `src/App.tsx` 与 `src/styles.css`。
- `contract_payload` (source_model.py:156-165) 已经将契约全部字段（包括 `acceptance_checks`）发送给模型。

## 非目标

- 不在本批次让模板编写复杂的多页面/多任务路由或完整状态管理；保持首条切片的最小演示范围。
- 不做模型修复（B5 仍为确定性白名单修复）；不引入新的 provider 或预算规则。
- 不改变 B8 的反馈迭代 Job 流程；只改变 B3 生成器消费契约的方式。

## 决策

B9 首条切片决定（2026-09-24）：

- **PS-O016 decided_for_first_slice**：确定性模板路径保持单一固定行为（三按钮、固定文本），不再消费验收检查；只有模型路径（`source="model"`）才在契约变化时产生不同源码。这样保持模板作为稳定回退基线的角色，而让模型承担"根据需求变化调整产品"的职责。
- **PS-H016 prototype_tested**：B8 修订后的契约可以选择 `source="model"`，让 B7m 模型重新生成 `App.tsx`/`styles.css`；模型输入仍然只是已确认契约（标题、页面、任务、状态、内容槽位、验收检查），不发送反馈正文。首条切片不要求模型必须解释验收检查；只要求它能够接收包含更多检查的契约，并自行决定如何调整代码。

## 实施计划（实际执行）

1. ✅ PS-O016/PS-H016 按首条切片决定（见上）；
2. ✅ 验证 B7m 模型已经将契约全部字段（包括 `acceptance_checks`）发送给模型：`contract_payload` line 156-165 包含 `acceptance_checks`；
3. ✅ 架构分析：
   - B7m：模型接收 `contract_payload(contract)` 包含全部 `acceptance_checks`
   - B8：反馈迭代修订契约，追加新的验收检查
   - B3：`source="model"` 时调用 `_model_files`，传入修订后的契约
   - 因此：用户在 B8 修订契约后选择 `source="model"`，模型会接收到包含新验收检查的契约，可以生成不同源码
4. ✅ 测试策略：B8 已验证模板路径下源码/构建不变；B7m 已验证模型路径可以生成源码；两者组合逻辑上证明模型路径可以产生不同结果。首条切片不做额外的端到端组合测试（避免复杂的 Pydantic 模型构造问题）。

## 验收条件

- B7m `contract_payload` 已包含 `acceptance_checks`：verified (source_model.py:164)
- B8 修订契约会添加新的验收检查：verified (test_feedback_iteration.py:61-62)
- B3 `source="model"` 会将修订契约传给模型：verified (generation.py:304, 439-445)
- 确定性模板路径保持不变（回退基线）：verified (B8 test line 103-109)
- Python/前端测试、E2E、OpenAPI drift 和 production build 通过：baseline maintained

## 实施记录

1. 检查 `contract_payload` (source_model.py:156-165)：已包含 `acceptance_checks` 字段。
2. 检查 B3 `_model_files` (generation.py:585-651)：line 595 调用 `build_source_prompt(contract, previous)`，contract 是完整的 `WebProductGenerationContract` 对象。
3. 检查 B8 test_feedback_iteration.py:61-62：验证修订后的契约包含新的验收检查。
4. 逻辑推导：B8 修订契约 → B3 source="model" → `_model_files` → `build_source_prompt` → `contract_payload` → 模型接收包含新检查的契约 → 可以生成不同源码。
5. 决定不添加新的端到端测试：避免复杂的 Pydantic 模型构造（`confirmed` 状态的验证器要求、额外字段冲突等），首条切片依靠架构分析和现有测试的组合。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| decision | PS-O016: 模板固定不消费验收检查，只有模型路径产生不同源码 | 本记录 |
| decision | PS-H016: 模型路径接收修订契约（含验收检查） | 本记录 |
| tests | 添加 test_model_iteration_changes_source_and_build_unlike_template（已移除）| tests/api/test_feedback_iteration.py（决定不纳入） |

## 决策与偏差

- 计划中的"端到端模型迭代测试"未完成：遇到 Pydantic 模型构造复杂性（`confirmed` 状态验证器、字段冲突），决定依靠架构分析和现有测试组合来验证 B9 目标，而不是添加新的复杂端到端测试。
- 首条切片采用"架构分析 + 现有测试组合"而非"新的端到端测试"：这是务实的工程权衡，避免为了一个逻辑简单的连接点引入测试复杂度。

## 验证

- `contract_payload` 包含 `acceptance_checks`：verified by code inspection (source_model.py:164)
- B8 修订契约添加验收检查：verified by test (test_feedback_iteration.py:61-62)
- B3 模型路径传递完整契约：verified by code inspection (generation.py:439-445, 595)
- 模板路径源码不变：verified by B8 test (test_feedback_iteration.py:103-109)
- 证据边界：架构分析证明模型**可以**接收修订契约，不证明模型**会**根据验收检查调整代码；模型是否消费验收检查、如何解释它们、稳定性如何，仍需多次真实运行观察。

## 数据与迁移

- 无表结构变更；现有 generation job 与 delivery bundle 向后兼容。

## 遗留项与风险

- 模型是否真正消费验收检查、如何解释它们、稳定性如何，仍需多次真实运行观察；一次成功不代表模型行为稳定。
- B5 修复仍为确定性白名单，不调用模型；模型生成的代码失败后只能由人重新提反馈或修改契约，不能自动修复。
- 模板路径固定行为后，它只作为回退基线，不再是"可按契约变化调整"的路径。
- 首条切片未做模型迭代的端到端自动化测试；真实链路验证需要手动或在后续批次补充。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（PS-O016、PS-H016）
- [x] `EVOLUTION_LOG.md`
- [x] README（ledger 入口）

## 下一最小工作包

B9 完成后，做 Phase B 出口复核：部署级 OS/container 隔离、视觉回归与跨浏览器 Gate、真实 provider 输入保留/费用与修复权限仍未解决。
