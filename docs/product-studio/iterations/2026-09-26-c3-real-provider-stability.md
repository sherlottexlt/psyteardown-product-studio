# C3 — 多次真实链路稳定性评估

- 工作包 ID：C3
- 开始日期：2026-09-26
- 关闭日期：2026-09-26
- 状态：Closed
- 路线图工作包：C3
- 类型：Provider / Execution / Validation
- 前置：C0 至少一次全链路成功；C1 observation intake 独立于 C3，不是 C3 前置
- 评估范围：10 次相互独立、顺序执行的真实 DeepSeek Product Contract → deterministic Web generation contract → DeepSeek B7m source=model → B4 → B6 链路

> R1/R2/R3 的 `blocked`/诊断结论和 R4 的 10/10 通过是验证结果，不是生命周期状态；R4 不等于生产级稳定性保证。

## 目标

将 C0 的单次成功扩展为可复核的多次运行样本，记录完整链路成功率、阶段失败模式、模型调用/token 分布、阶段耗时及当前预算边界。评估只说明软件/provider 链路表现，不说明用户是否获得真实结果。

## 非目标与证据边界

- 不招募或模拟真实参与者，不写 MeasurementObservation/EvidenceReview，不将本次运行解释成用户价值证据。
- 不将 deterministic Web contract、Playwright、axe 或模型解释冒充真实用户/研究观察。
- 不推断金额费用，不新增金额预算、自动重试、持久化用户输入或部署级隔离。
- 保留 C0 当前纵向切片：真实 Product Contract 和 B7m 源码生成，中间 Web generation contract 使用 deterministic fake。

## 运行和预算协议

- 固定执行 10 次独立完整尝试；每次新建项目和隔离的临时输出根，顺序运行，不因失败提前停止，也不对失败的整条链路额外重跑。
- 现有 PS-O018 对每个 Product Contract proposal 最多 2 次 provider call；B7m 每 Job 最多 2 次 source-model call（首稿 + 一次由静态 Gate 驱动的显式修订）。按每条最多 4 个 Product Contract calls × 2 + B7m 2 = 最多 10 次模型调用估算，本批硬上限为 100 次模型调用。超出即停止后续运行并将本批标为未完成。
- 当前不计金额，不宣称 100 次调用等于某个费用上限；若 provider 本身无法提供 usage，则如实记为 unavailable，不用估算代替。
- 原始 prompt、模型响应、transcript、产品正文和 workspace 只存在于每次运行的临时目录，运行结束即清理；汇总报告只允许写入白名单字段（run 序号、阶段名/状态/耗时、错误码、provider/model、调用次数、token 数、静态 Gate 重试数、B6 archive 大小/hash）。不写入 API key、产品正文、原始错误文本或完整 project id。

## 验收条件

1. 一个显式 opt-in 的 runner 顺序执行 10 次真实完整链路；缺少 provider 配置时在任何付费调用前失败。
2. 单测覆盖报告聚合、部分失败/缺失 token、敏感字段白名单与停止边界；单测不访问网络。
3. B7m Gate 对每个契约 screen/task/required slot ID 的要求有回归断言；不通过删除 Gate、自动注入漏掉的 ID 或隐式增加重试来提高成功率。
4. 输出包含完整链路成功率、阶段失败模式、各 run/阶段耗时、每 run 调用数与 token 总量/分布、金额不可用声明及现有调用预算边界。
5. 10 次真实运行结果及原始命令记入本记录；确定性回归通过。任何失败均进入分母，只有完整通过 B6 才算完整成功。

## 实施记录

- [x] 编写有界、显式 opt-in 的 10 次运行器及无原文白名单报告。
- [x] 增加模型输出不得遗漏 screen/task/required slot ID 的静态 Gate 回归测试。
- [x] 执行 10 次真实完整链路并检查聚合报告。
- [x] 运行确定性回归并关闭或记录遗留项。

## 结果（2026-09-26）

- 原始命令：`python scripts/run_c3_real_provider_stability.py --output-root output/product-studio/c3-stability`。
- 10 次尝试全部执行；7 次完整通过 B6，成功率 70%；3 次失败均进入分母：`model_output_rejected`、`command_failed`、`provider_schema_invalid` 各 1 次。
- 总计 36 次模型调用，42,194 input tokens，60,844 output tokens；各 run 总耗时合计 577.78 秒，100 次调用硬上限未触发。金额保持 `unavailable_not_inferred`。
- 机器可读汇总：`output/product-studio/c3-stability/c3-stability-report.json`。报告只包含白名单运行字段；原始 C0 transcript/workspace 不作为 C3 证据发布。
- 结论：C3 的“10 次评估完成”门槛满足，但不能声称真实链路稳定通过；下一最小工作包是定位三个失败类别并决定是否修复后复测。C1 仍不因 C3 结果而解除 decision required。

## 有界重试复测（2026-09-26）

- 触发：首轮暴露 `model_output_rejected`、`provider_schema_invalid` 和 `command_failed`；先修正 ProductThesis prompt 的 `realization_modes` allowlist，并为 C3 runner 增加 killable child process、每阶段最多一次显式重试、每次运行 300 秒超时和逐次 checkpoint。
- 原始命令：`python scripts/run_c3_real_provider_stability.py --output-root output/product-studio/c3-stability-r2`。
- 结果：10 次尝试，8 次完整通过 B6，2 次失败，均为 B4 `command_failed`；2 次 `provider_schema_invalid` 在有限重试后恢复；`model_output_rejected` 未再成为最终失败。
- 资源：52 次模型调用，58,850 input tokens，86,279 output tokens；各 run 总耗时合计 746.48 秒；100 次调用硬上限未触发，金额保持 `unavailable_not_inferred`。
- 汇总：`output/product-studio/c3-stability-r2/c3-stability-report.json`。C3 评估完成但稳定性仍为 8/10；不能把有限重试结果提升为产品稳定性通过。
- 结论：Product Contract schema 漂移风险已有一个具体修正（prompt allowlist）；B4 `command_failed` 仍需单独取得安全的阶段级诊断或修复后再复测。C1 仍保持 decision required。

## B4 阶段诊断复测（2026-09-26）

- 触发：R2 的 2 次 `command_failed` 只能定位到 B4，无法区分 preview/run 与 browser 阶段。B4 runner 现在将浏览器命令失败标记为 `browser_command_failed`，并把 combined preview/browser runner 的成功 preview 阶段写入 `run` step；新增确定性测试。
- 原始命令：`python scripts/run_c3_real_provider_stability.py --output-root output/product-studio/c3-stability-r3`。
- 结果：R3 只完成 6/10 次后安全停止；4 次完整通过，1 次 `browser_command_failed`（B4 steps 为 install/build/run succeeded、browser failed），1 次 `run_timeout`。没有把不完整样本当作 C3 通过。
- 资源：25 次模型调用，28,430 input tokens，41,806 output tokens；记录总耗时 725.40 秒。R3 不产生新的稳定性通过结论。
- 汇总：`output/product-studio/c3-stability-r3/c3-stability-report.json`；R3 原始 raw 目录已清理。
- 结论：B4 诊断现在能区分 browser 失败与 run 超时；`browser_command_failed` 和 `run_timeout` 仍需后续独立修复/复测。C3 仍未达到稳定性通过门槛，C1 继续保持 decision required。

## 下一最小工作包（2026-09-26）

- 不立即启动第四轮全链路付费评估。先使用本地确定性测试验证新的 B4 安全诊断分类：`browser_assertion_failed`、`browser_accessibility_failed`、`browser_launch_failed`、`browser_timeout`。
- 只有在诊断分类通过本地 Gate、且明确 R3 `run_timeout` 的边界后，才决定是否进行下一次有限真实复测。

## B4 安全诊断分类本地 Gate（2026-09-26）

- 实现：B4 将浏览器阶段的非零退出、启动失败和超时映射为安全分类 `browser_assertion_failed`、`browser_accessibility_failed`、`browser_launch_failed`、`browser_timeout`；不保留浏览器原始输出。B4 浏览器超时严格受剩余执行预算约束，不再用额外的最小 1 秒延长总预算。
- 边界：`browser_timeout` 只表示 B4 内部浏览器命令超时；C3 runner 的进程级 watchdog 仍使用 `run_timeout`。两者在本地聚合回归中分别断言，不能互相替代。
- 本地 Gate：`pytest -q tests/product/test_execution.py tests/product/test_stability.py` → 21 passed、1 warning；覆盖四类浏览器诊断、缺失浏览器命令的启动失败、B4 浏览器超时预算状态，以及 C3 外层 `run_timeout` 与 B4 `browser_timeout` 的分离。
- 真实 provider：本地 Gate 之后已启动 R4；该本地 Gate 本身不产生真实链路结论，R4 结果见下节。
- 下一步：C3 本批已关闭；保留 R1/R2/R3 失败样本、R4 汇总和 B4 诊断边界。部署级隔离、金额预算和跨环境稳定性仍不在本批范围。

## R4 有界复测（2026-09-26）

- 触发：B4 安全诊断分类本地 Gate 已通过；按不新增自动重试、不改变调用上限的原则，启动一次新的 10 次真实完整链路复测。
- 原始命令：`python scripts/run_c3_real_provider_stability.py --output-root output/product-studio/c3-stability-r4`。
- 结果：10 次尝试全部完成，10 次完整通过 B6，成功率 100%；最终失败模式为空，恢复失败模式为空。
- 资源：50 次模型调用，57,724 input tokens，83,183 output tokens；100 次调用硬上限未触发；金额保持 `unavailable_not_inferred`。
- 汇总：`output/product-studio/c3-stability-r4/c3-stability-report.json`。10/10 报告已经写出且 raw workspace 已清理；首次运行在 Windows raw 清理遇到并发消失文件导致命令退出码为 1，随后修正清理器对 `FileNotFoundError` 的幂等处理。该清理异常发生在所有 10 次链路已完成并写出汇总之后，不改变链路样本结果。
- 结论：R4 达到 C3 评估的 10/10 完整链路通过门槛，但仍不把一次 10-run 样本解释成生产级稳定性保证；C3 可关闭为“本评估通过、剩余边界已记录”。
