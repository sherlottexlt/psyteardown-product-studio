# Iteration：C1 主链路收敛与真实模型生成韧性补强

- 日期：2026-09-27
- 状态：Closed
- 路线图工作包：C1 / B7m / Product Studio Web shell
- 类型：Workflow / Contract / UI / Validation

## 背景

负责人完成了完整流程体验，但无法判断最后获得的真实产品结果；真实模型生成过程中还存在主链路分散、模型失败后缺少清晰恢复、Web 交付契约不能表达连续体验路径等问题。因此暂缓下一轮 C1 真实自试，先收敛为一个可以复核的真实范例：

> 申明一个具体的小任务 → 开始 bounded focus session → 处理一个非紧急打断（允许/延后/停止）→ 回到任务并完成 → 看见延后的事项。

## 本批实现

- Product Studio 项目页新增“主链路”引导，显示当前唯一下一步，并可直接跳转到对应工作区。
- 默认新项目和后续 Product Contract 提案使用真实 provider；fake 仍保留为显式离线工作流选项。
- Product Contract 失败或 stale 后，界面可以直接带着当前错误重试 proposal job，不必回到隐蔽的后台状态。
- Web generation contract 增加 `primary_flow_task_ids`，确定性首条切片固定一个连续体验路径；Workbench 展示该路径，不再把所有按钮并列为同等主任务。
- B7m source prompt 只在存在主链路时要求 `data-primary-flow-step`，并生成 contract-derived browser check 验证主链路步骤推进；旧契约保持兼容。
- 10 分钟 bounded task、非紧急 interruption、finish/recover 主线替代原先仅有“开始 session / review interruption”的松散 demo。

## 验证

- `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py` → 553 passed、3 skipped、2 warnings。
- `pytest -q tests/product/test_source_model.py tests/api/test_http_contract_matrix.py` → 27 passed、2 warnings。
- `npm test -- --run` → 28 passed。
- `npm run build` → 成功，重新生成 `studio/openapi.json` 与 `studio/src/api/schema.ts`。

## 暂不声称

本批只证明主链路表达、模型失败恢复和确定性 Gate 的软件行为；未重新运行付费真实 provider，也不产生 C1 现实任务结果。下一次真实测试应先使用同一条 primary journey，并只验证该 journey 是否能让负责人完成一个明确小任务。


## 收口复核（2026-09-28）

实现范围已完成；本次收口复核未启动真实 C1 试用、未启用 `PSYTEARDOWN_C1_TRIAL_ENABLED`、未调用付费真实 provider，也未创建真实参与者记录（自动化测试仅使用隔离数据）。

- `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py`：561 passed、3 skipped、2 warnings。
- `npm test -- --run`：29 passed。
- `npm run build`：成功，OpenAPI/transport type 生成无待提交差异。
- `npm run test:e2e`：Chromium 3 passed；覆盖 Product Contract/C2 流程、缺少 B6 时 C1 面板禁用、工作区恢复与 axe 检查，不等于 C1 真实观察。

软件准备退出；剩余下一步属于负责人控制的真实体验验证：选定满足 C1 pin 条件的当前项目，审阅实际展示的 `c1-local-v1` 同意与数据边界，并在明确决定后才启用开关。观察可先保留为未 review；任何 EvidenceReview 等级提升仍要求与 host 分离的具名 reviewer。
