# Iteration：A6 首条数字产品切片校准

- 日期：2026-09-21
- 关闭日期：2026-09-21
- 状态：Closed
- 路线图工作包：A6（Phase A 出口 / Phase B 前置 Gate）
- 类型：Product decision / domain calibration / validation

## 目标

用一个具体、可在浏览器中验证的数字产品切片复核 A1/A2 的四对象最小字段、人工确认范围和项目聚合边界，并冻结 Phase B 的第一版 `OutcomeContract`。

本记录是产品决策和确定性代码校准，不是现实用户结果研究。切片可以进入 Phase B 的生成与测试，但在真实任务试用前不能宣称它改善了专注、生产力或沟通结果。

## PS-O001 决定：首条切片

### 目标用户

一名自主管理工作的知识工作者（自由职业者、独立创作者或小团队中的个人贡献者），主要在桌面浏览器中完成需要连续注意力的任务。第一条切片只建模一个主要使用者，不处理雇主监控、团队审批或多租户权限。

### 现实问题

在 25–60 分钟的自定节奏工作时段，邮件、聊天和任务工具的异步通知造成非计划的上下文切换。用户希望降低非紧急打扰，同时保留对紧急联系的明确、可撤销控制；现阶段不知道主要原因是通知时机、任务不明确，还是两者共同作用。

### 产品形态边界

首条实现是一个本地优先的 Web 产品原型：用户声明一个有时间边界的专注任务，非紧急事项可以被延后，紧急事项仍需逐次接受、拒绝或稍后处理。原型不读取或上传消息正文，不对个人生产力打分，也不假设能够跨应用可靠识别所有通知。

### 非目标

- 不做员工/团队监控、排行榜或生产力评分；
- 不承诺屏蔽所有通知或保证用户完成任务；
- 不生成原生移动应用、硬件、浏览器外的系统级通知代理；
- 不把当前切片、自动化测试或模型解释当作真实用户证据。

## PS-O002 决定：四对象最小字段与边界

校准结论是：A1 的现有字段足以表达这个单人 Web 切片，A2 的独立项目聚合、子对象 revision、`expected_revision` 和只读 projection 边界保留；不为首条切片增加字段。以下是字段如何落到该切片的明确解释：

| 对象 | 本切片必需表达 | 人必须确认 | 可由 proposal/来源先提供 | 首条切片的边界决定 |
|---|---|---|---|---|
| `ProductIntent` | 想减少什么打扰、主要使用者、当前桌面情境、拒绝监控/静默紧急联系、浏览器/本地优先/可撤销约束、设置时间偏好 | `desired_change`、`affected_people`、`current_situation`、`explicit_non_goals`、`known_constraints`、`resource_preferences`；确认者和理由进入 revision | 原句归一化、字段分组和缺失项提示；`source_refs` 必须保留用户输入来源 | 单人切片把主要目标用户记录在 `affected_people`；不新增 `decision_owner`，多方决策出现时重新校准 |
| `ProblemModel` | 用户报告的切换事实、通知驱动/任务歧义等竞争解释、未知和最便宜的证伪方式 | 事实是否忠实、事实来源、至少两个竞争解释及其证伪路径；不能把解释升级成事实 | 提案可整理事实、假设、未知、利益张力；研究/工具来源未来必须带 provenance | `facts`、`unknowns`、`competing_explanations` 足以覆盖单人情境；`stakeholder_tensions` 可为空，不强造组织冲突 |
| `OutcomeContract` | 目标人群和桌面时段、减少非计划切换、保留紧急联系控制、禁止监控/不可撤销干预、时间/注意/数据边界、停止条件、最低交付成熟度和现实证据要求 | 所有价值和风险边界：`target_segments`、`applicable_contexts`、目标与指标阈值、禁止结果审查、资源边界、停止条件、成熟度和证据要求 | AI 可草拟指标定义、观察方法和阈值候选，但不能确认；`required_real_world_evidence` 不能被自动测试替代 | 本切片冻结为 `runnable_prototype` 目标；结果指标仍是待真实任务观察的契约，不是已达成结果 |
| `ProductThesis` | 后续候选路径的机制、可证伪预测、验证步骤和维护代价 | 生成不等于选择；进入 `selected` 必须有人决定或有显式授权 | AI 可生成 2–3 个有差异的 Web 路径和验证提案 | A6 不创建或选择 thesis；Phase B 以冻结的 Outcome Contract 为上游输入 |

### 状态与 revision 结论

- proposal、confirmed、修订回 proposal 的状态语义保留；模型输出不能直接成为权威状态；
- 确认、纠正和替代都创建新的不可变 revision，保留父 revision、创建者、时间、理由和来源；
- `ProblemModel` 必须有至少一个有来源事实和两个竞争解释才能 confirmed；
- `OutcomeContract` confirmed 必须有人确认目标人群/情境、至少一个带指标的目标、禁止结果审查、资源边界、停止条件和现实证据要求；
- 上游修订不删除历史。ProblemModel 直接受影响时标为 `review_required`，OutcomeContract/ProductThesis 受影响时标为 `stale`；
- 项目、Intent、ProblemModel 和 OutcomeContract 继续由独立 current pointer 组成一个只读 `ProductProjectView`。跨对象写入仍通过 Application Service 的原子 command，并携带已有聚合的 `expected_revision`。

## PS-O003 决定：人工确认范围

人工确认的最小高信息量边界如下：

1. **Intent gate**：用户确认“为谁改变什么”、当前情境是否准确、明确不接受的结果、隐私/资源/可撤销限制。AI 可以改写表达，但不能替用户选择价值边界。
2. **Problem gate**：用户或具名 reviewer 确认引用的事实没有被模型发明，至少两个竞争解释仍然合理，并接受每个解释的最低成本证伪路径。未知可以保持未知，不能因为提案完整而自动关闭。
3. **Outcome gate**：用户确认结果目标、适用场景、可观察指标及阈值、禁止结果、预算/注意/数据边界、停止动作、最低成熟度和现实证据类型。自动测试只验证软件行为，不满足这一 Gate。
4. **Thesis gate**：AI 可提案和比较路径；选择或授权低成本证伪仍是人的决定。A6 不把 thesis 选择提前塞入 Product Contract。

## 冻结的首条 `OutcomeContract`

下面的值是 Phase B 的第一版产品契约输入，所有未来修订必须创建新 revision：

| 字段 | 冻结值 |
|---|---|
| `target_segments` | `self-directed knowledge workers` |
| `applicable_contexts` | `25–60 minute self-directed desktop work sessions` |
| `target_outcomes` | 在计划的专注任务中减少非计划切换，同时保留对紧急联系的明确控制 |
| `success_indicators` | `unplanned task switches during a declared focus session`；通过获同意的任务时段观察和产品事件记录；方向为减少；阈值为“在预注册试用中低于同一用户的无辅助基线”；证据类型为 `real_user_observation` |
| `prohibited_outcomes` | 未经明确选择延误紧急联系；用户无法立即停止或恢复干预；隐式收集或上传消息正文；生产力评分/监控 |
| `resource_boundary` | 设置少于 1 分钟；每次 surfaced interruption 最多需要一次决定；不进行隐藏活动收集或消息正文上传 |
| `stop_conditions` | 无法立即停止/恢复 → `stop`；紧急联系被无明确选择地漏掉或延误 → `reframe` |
| `minimum_delivery_maturity` | `runnable_prototype` |
| `required_real_world_evidence` | 获同意的目标任务观察；用户报告的控制感和中断恢复情况 |

该契约的阈值是待试验的预注册目标，不是已经观察到的结果；首次真实任务试用前必须由具体参与者、任务和观察方案补齐。

## 验证与证据

- 新增确定性领域测试：[`tests/product/test_a6_first_slice.py`](../../../tests/product/test_a6_first_slice.py)，覆盖该切片从 Intent proposal → human confirmation → ProblemModel proposal/confirmation → OutcomeContract proposal/confirmation 的完整命令路径，并锁定最小字段和 `runnable_prototype` 成熟度；
- 既有服务测试覆盖 InMemory/SQLite 双适配器、revision 冲突、上游 Gate、直接 impact 和重启恢复；
- 测试只证明领域命令和存储行为，不证明该产品改善真实用户结果；
- 本记录没有引入真实模型调用、外部研究或新的现实证据。

## A6 结论与后续 Gate

- PS-O001 已为首条数字产品切片作出决定；
- PS-O002/O003 已在该切片范围内关闭，A1/A2 从“未经切片校准的 prototype tested”升级为“首条切片基线”；它们不因此成为所有用户和未来 realization pack 的最终架构；
- Phase A 可以关闭；
- Phase B 的第一步是用冻结的 Outcome Contract 生成并比较 2–3 个 Product Thesis，然后在真实用户试用前补齐可执行的观察方案；
- 重新出现多方利益相关者、跨应用系统权限、移动场景、团队治理或不同结果指标时，必须重新打开 PS-O002/O003，而不是静默扩展本记录。
