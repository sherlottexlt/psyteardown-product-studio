# Iteration：B7m 静态 Gate 与 B4 契约测试恢复

- 日期：2026-09-28
- 状态：Closed
- 路线图工作包：B3 / B4 / B5 / B7m
- 类型：Bugfix / Contract / Validation / Recovery

## 触发与复核

用户先遇到 `The model draft was rejected by the static gate (11 issue(s)): screen id ... is missing`。本地 transcript 显示模型通过 `const P = "proposal-job-..."` 和 `` `${P}-focus-screen` `` 组合 screen/task/content-slot ID。旧 Gate 只搜索完整 ID 子串，误拒绝了源码中可静态解析的准确 ID。provider 的完整响应与 hash transcript 均保留，未再次调用模型。

之后 B4 暴露了连续的两个测试 harness 问题：contract-derived fixture 漏了 `tasks` 与 `primary_flow_task_ids`；补齐后 primary-flow test 又在完成 per-screen sweep 后才要求 flowStep 归零，并在 400ms 状态转换结束前切换 screen，导致 app timer 被 navigation 清除。首次 saved-source child 还继承了通用模板 Playwright 文件，没有覆盖确认契约。B5 因没有匹配的 allowlisted app-source patch 而安全拒绝，原 `App.tsx` / `styles.css` 始终未被修改。

## 本批修改

- Static gate 增加受限的 JS literal / prefix constant / simple template literal 静态解析；不执行模型 JavaScript，也不接受动态计算 ID。Prompt 明确允许精确前缀组合并要求保持 ID 原值。
- Contract-derived browser test 加齐 task lookup 和主流程数据，先从 ready/step 0 验证 primary journey；每个任务等待 screen 允许的终态后再导航读取 tracker；之后独立 sweep 所有 screen/task/state。
- saved-model child generation 由固定 renderer 生成其余文件和契约浏览器测试，只从 parent generation revision 复制经过 manifest + transcript hash + 当前静态 Gate 验证的 `src/App.tsx` / `src/styles.css`。它是独立、revision-pinned 的 `saved_model` Job；不覆盖源 Job/workspace、不产生 DeepSeek 调用、不计模型成本。
- Provider 原始 `ModelCallRecord.outcome=rejected` 保持不变；静态 Gate 的本地复核版本作为单独字段和 transcript audit 保存。
- B3 template cache version 为 `b3-v2`；saved-source renderer fingerprint 为 `b7m-workspace-v5`。B5 unsupported diagnosis 不重复消耗修复尝试；UI 提供从本地已保存源码创建新验证 lineage 的入口。

## 验证

- `pytest -q --ignore=tests/product/test_c0_real_provider_e2e.py`：568 passed、6 skipped、2 warnings。
- `npm test`：35 passed；`npm run build` 成功，OpenAPI 与前端 schema 已同步生成。
- 使用已保存源 Job `generation-job-9ca0dd676a6243beb7dab6d32260209e.r14`，零新增 provider 调用生成 saved-source workspace `generation-job-a38ad51b0ba54891ac1f4fbe19ce389c`。
- B4 `execution-job-778d5b56139d450793c7e4adffa8af99` 的 install / build / preview / browser 四步全部 `succeeded`。这是本地保存源码与确定性 Chromium harness 的软件验证，不是新的模型调用、现实用户结果或 C1 证据。
- 旧失败 workspace、原始 provider rejection、execution 和 B5 unsupported 记录均保留；未手工改写旧源码或 SQLite 历史。
