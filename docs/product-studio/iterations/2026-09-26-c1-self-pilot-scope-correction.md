# Iteration：C1 负责人自试与非参与者演练 Gate 范围校正

- 日期：2026-09-26
- 状态：Closed
- 路线图工作包：C1
- 类型：Documentation / Governance / Validation

## 目标

根据本地首轮使用方式，校正 C1 的下一步：不再把“非参与者人工演练”设为真实自试前的强制 Gate。项目负责人可以直接作为首位真实参与者，在本机完成一次明确同意、人工主持、可撤回的自我试用。

## 决定

- **不要求独立非参与者演练。** 对本地单用户首轮而言，负责人自试同时覆盖真实任务观察和主持流程验证，额外先录一轮演练只会重复同一流程。
- **负责人 N=1 是真实但有限的观察。** 可以做多个真实 task session / presentation，并观察重复性、学习效应和疲劳效应；但必须记录为 `participant_n=1, session_k>=1`，不能把同一个人计作多个用户。它不能满足当前 C2 派生计划的 participant `minimum_n=3`，也不能支持面向目标人群的泛化效果声明。
- **D1 边界不变。** 仍使用 `c1-local-v1`，只在本机记录随机 ID、结构化 measure、任务状态和人工时间；不采集屏幕、键鼠、通知、截图、自动遥测或参与者原始文本。
- **D3 边界不变。** 负责人可以是 participant，也可以实际操作 host 流程；但按当前冻结规则，EvidenceReview 的 reviewer 仍必须是与 host 分离的具名人工。若只有负责人一人，则记录可以保留为未 review 的观察，不能提升 evidence level。
- **不是法律或合规判断。** 本地自试只是首轮产品验证安排；远程招募、托管、多用户和企业场景仍需重新审阅。

## 影响

- C1 下一最小工作包改为：`负责人本地自试与独立人工 review`。
- `CURRENT_STATE.md`、`ROADMAP.md`、`README.md` 和 C1 iteration 不再把非参与者演练列为前置条件。
- C1 Active 状态不变；真实自试完成前，不产生现实结果声明；自试完成后也只允许声明一条本地、N=1、来源为 `research_observation` 的受限观察。

## 验证边界

软件测试和 Chromium E2E 已覆盖启动 Gate、非成功路径和 axe；它们不替代负责人真实自试，也不替代独立 reviewer 的 EvidenceReview。

## 下一最小工作包

负责人在本机使用当前确认的 C2 plan + B6 delivery 完成一次真实自试；随后由与 host 分离的具名 reviewer 审阅，或者明确保留为未 review observation。
