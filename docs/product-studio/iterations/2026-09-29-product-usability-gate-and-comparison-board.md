# Iteration：Product Usability Gate 与真实选项对比板首条原型修正

- 日期：2026-09-29
- 状态：Closed
- 工作包：C1 前置门槛 / B2 Web generation contract / B3 deterministic renderer
- 类型：Workflow / Contract / Domain / API / UI / Validation

## 背景

用户按照既有开发日志完成 Product Contract、Web generation contract、B4 和 B6 后，获得的交互包只有通用状态按钮，没有完成“选项对比板”的核心任务。此前 C1 readiness 只检查 C2 plan、当前 Web contract 和成功 B6 pin，把软件可运行误当成真实任务可用。

本批修正两个问题：

1. C1 在后端和前端增加明确的 Product Usability Gate；
2. 首条 fake Web contract 与 deterministic template 必须生成真实的最小对比任务，而不是只演示状态切换。

## 本批范围

### 1. C1 产品可用性确认

- `StartC1EnvelopeRequest` 增加 `product_usability_confirmed`；
- C1 service 在创建 envelope 前拒绝未确认请求；错误明确说明 B4/B6 软件验证不等于产品可用；
- C1 Panel 展示不可跳过的 host 确认：已亲自完成核心任务，且交互包含真实输入/内容和完成结果；
- C1 envelope 记录该确认，便于之后审查启动前置。

### 2. Web generation contract

fake Web contract 不再固定生成“开始 session / 做一个选择 / 停止”的抽象流程，而是描述一个可运行的最小选项对比板：

- 两个本地选项；
- 决策标准；
- 已知信息；
- 顾虑；
- 用户自己的当前倾向；
- 仍待确认的未知；
- 不排序、不评分、不替用户做决定。

主流程变为：

```text
添加/确认两个选项 → 分开查看标准、已知信息和顾虑 → 记录自己的倾向与下一问题
```

### 3. 生成器与模型提示

- deterministic template 由通用 `Continue / Show error / Stop` 占位页改为可编辑的 comparison board；
- `fixture.json` 至少包含两个本地选项和三类记录；
- template 的浏览器测试改为使用 contract-derived test，不再检查硬编码的通用按钮；
- B7m source prompt 明确禁止只生成通用按钮演示；当 contract 含 options/standards/facts/concerns/user leaning 时，必须渲染真实的本地选项和可编辑控件。

## 非目标

- 不把本地 fixture 或自动化测试升级为真实用户结果；
- 不修改已有 revision、workspace 或交付包；
- 不自动让旧交付包具备新交互；
- 不启动 C1 真实试用；
- 不把 host 自我确认当成独立 reviewer 或统计证据。

## 验收与验证

- C1 API：未提供 `product_usability_confirmed` 时拒绝创建 envelope；确认后既有 C1 pin 流程继续通过；
- Python：C1、generation、execution 目标测试 `31 passed`；
- 前端：`npm test -- --run` `35 passed`；
- 前端生产构建成功，OpenAPI/transport types 重新生成；
- 新 deterministic template workspace：
  - `npm run build` 成功；
  - contract-derived Playwright/axe 测试 `1 passed`；
  - 测试覆盖页面、任务、required content slots、primary flow 和 accessibility；
- 旧交付包仍保持原内容，需由负责人重新生成新 Web contract、workspace、B4 和 B6 才能获得新版本。

## 结论

C1 的软件基础设施仍可复用，但当前真实试用不应启动。下一次负责人操作必须先确认新的交互包真的能完成核心对比任务；如果仍只有通用按钮或空内容，应停在 Web contract/生成阶段，不进入 C1。

## 遗留项

- 真实模型生成的具体视觉和文案仍需在新 contract 上重新运行并由人审阅；
- Product Usability Gate 目前是具名 host 的显式确认，不是自动理解产品价值的模型判定；
- C1 的 N=1 观察仍不满足 C2 `minimum_n=3`，也不支持泛化结论。
