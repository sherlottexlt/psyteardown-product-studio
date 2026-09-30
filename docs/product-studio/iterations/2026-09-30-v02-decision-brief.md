# Iteration：V0.2 Decision Brief

- 日期：2026-09-30
- 状态：已关闭
- 范围：B2 Web generation contract、B3 deterministic renderer、B4 contract-derived browser test

## 判断

当前 V0.1 对比板适合作为“最小可验证原型”，但不像产品，因为用户只能在当前页面临时记录，刷新后没有成果，且没有明确的决定框架和可带走的产物。本轮不扩展到推荐、AI 评分、账号、云同步或真实结果承诺，只补最小产品闭环：把一次近期决定整理成一个用户拥有的 Decision Brief。

## V0.2 主链路

```text
设定决定（问题 / 背景 / 回看时间）
  → 两个选项分别记录标准 / 已知信息 / 顾虑
  → 记录个人倾向和下一步核实问题
  → 导出 decision-brief.json
  → 之后导入 JSON 重新打开
```

- 导出/导入是显式本地文件动作；不使用网络、localStorage、IndexedDB、cookie 或自动上传。
- 文件 schema 标记为 `decision-brief.v1`，便于后续演变为持久化 DecisionBrief aggregate。
- 产品不排序、不评分、不替用户做决定；简报只是用户自己的可复核工作成果。

## 实现

- fake Web contract 增加第三个“决策简报”页面、决定设定字段、回看时间、下一步问题和 save brief task。
- deterministic renderer 改为完整的 setup → compare → brief flow，并提供 JSON download/import controls。
- generated fixture 标记 `decision-brief.v1` 和 `explicit_json_export_import_only`，明确本地边界。
- B7m prompt 要求在存在 save/export contract 时渲染本地 JSON 导入/导出，不允许用网络或浏览器存储替代。
- 当前项目已生成稳定契约 ID 的 `web-contract-391dfa4a03174521a289d42c2b16d0b9.r7`，状态为 `proposed`；r4/r6 与已有的 r2/r5 B6 交付包均未被改写。

## 验证

- Python 目标回归：`36 passed, 1 warning`（provider/source-model/generation/execution）。
- r7 generated workspace：`npm install`、`npm run build`、contract-derived Playwright/axe `1 passed`。
- 独立浏览器 journey：填写决定、双选项信息、倾向和下一问题，下载 `decision-brief.json`，再导入并恢复字段，`1 passed`。
- 全量确定性 Python 回归：`573 passed, 3 skipped, 2 warnings`；前端 `36 passed`，生产 build 成功；没有自动确认 r7，没有生成 r7 对应的新 B6，没有启动 C1。

## 下一步

先由负责人审阅并确认 r7 Web contract，再生成新的 workspace/B4/B6。真实使用时先观察“用户是否愿意把第二个真实决定也保存为简报”，不要马上测试长期决策质量。若复用信号成立，再把 JSON 文件演变为 SQLite-backed DecisionBrief；在此之前不增加账号、推荐、复杂外部数据接入或大规模 C1。
