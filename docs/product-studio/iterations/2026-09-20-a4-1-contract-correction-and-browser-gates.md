# Iteration：A4.1 Product Contract 纠正与浏览器 Gate

- 日期：2026-09-20
- 状态：Closed
- 路线图工作包：A4
- 类型：UI / API integration / Validation

## 目标

让用户可以在 Product Studio 中纠正当前 ProductIntent 并创建新的 proposal revision，在并发 revision 冲突时保留用户输入并恢复到最新服务端状态；同时以 OpenAPI 生成前端 transport 类型，并用真实浏览器验证 onboarding、纠正、确认、键盘操作和基础可访问性。

## 基线

- A4 第一批已经提供五区 Web 壳、项目创建、初始 ProductIntent、projection、确认与 ProductThesis transition；前端 6 tests、production build 和最小 HTTP 联调通过。
- 后端 `SubmitProductIntentProposal` 已支持 `intent_id` 与 `expected_revision`，可以复用现有 Domain Command 创建修订，不新增平行写路径。
- 当前前端 transport 类型为手工维护，没有现有 proposal 编辑器、revision conflict UX、Playwright 或自动 a11y Gate。
- North Star §4、§11、§12 要求用户可纠正结构化理解、客户端类型基于 API schema 生成或校验，写入使用显式 Domain Command 和 `expected_revision`。

## 范围

- ProductIntent 编辑表单，覆盖希望改变的现实、受影响者、当前情境、明确非目标、已知约束和资源倾向；
- 提交时携带 stable `intent_id` 与 `expected_revision`，成功后展示新 proposal revision；
- revision conflict 时自动刷新最新 projection，同时保留本地草稿并明确提示用户复核后重试；
- 可取消编辑、键盘访问和提交中状态；
- 从 FastAPI OpenAPI 生成 TypeScript transport types，并提供可重复的一致性命令；
- Playwright 浏览器 E2E 与 axe 基础可访问性检查；
- 对 ProductIntent amendment 与 conflict 增加 HTTP 覆盖。

## 非目标

- 不编辑 ProblemModel 或 OutcomeContract；
- 不从自然语言或模型自动生成 proposal；
- 不实现自动 merge、离线编辑、多用户身份或项目列表；
- 不接 Job/SSE、代码生成、产品预览或 Phase B 能力；
- 不把浏览器/a11y 检查解释为真实用户结果证据。

## 验收条件

- Given 当前 ProductIntent，When 用户修改字段并保存，Then API 使用相同 `intent_id` 和当前 `expected_revision` 创建新 proposal revision，历史不被覆盖；
- Given ProductIntent 已 confirmed，When 用户纠正，Then 新 revision 回到 proposed，必须重新具名确认；
- Given 另一个客户端已经写入新 revision，When 用户提交旧 revision，Then UI 显示冲突、刷新服务端 revision、保留本地草稿且不自动合并；
- Given 用户只使用键盘，When 打开、编辑、取消或保存，Then 焦点、label、按钮与错误消息均可操作和理解；
- OpenAPI 生成命令可重复运行且 production build 只引用生成的 response/request schema；
- Playwright 覆盖 onboarding → 查看 → 纠正 → 确认，并通过 axe critical/serious violation Gate；
- Python、前端单测、production build、依赖审计和全量回归通过。

## 实施记录

1. 在任何代码改动前建立本 iteration，并明确只纠正 ProductIntent、不扩张到 LLM 或产品生成。
2. 新增 ProductIntent 编辑器，提交 stable `intent_id`、`expected_revision` 和完整 proposal；confirmed revision 被纠正后由现有领域转换回 proposed。
3. revision conflict 时刷新最新 ProductProjectView，但保持编辑器本地 state；用户看到最新 revision 后必须主动再次保存，不做自动 merge。
4. 新增 deterministic OpenAPI exporter，并在 build 前用 `openapi-typescript` 生成 schema；手写 UI aliases 只从生成 schema 派生。
5. 后端测试锁定已提交 `openapi.json` 与 FastAPI 实际 schema 相等，并扩展 HTTP 冒烟覆盖 confirm → correct → stale conflict → current view。
6. 引入 Playwright/Chromium 与 axe；第一次浏览器运行发现原暗色设计的侧栏编号、阶段标签、revision 和未知提示不满足 WCAG AA 对比度，统一提高语义次要文字对比度后通过。
7. E2E 覆盖键盘 Enter 打开编辑、焦点进入标题、Esc 取消并回焦触发按钮，以及并发写入冲突后保留草稿/重试/确认。
8. 全量并行验证发现 Vitest 误加载 Playwright spec；将单元测试发现范围显式限制为 `src/**/*.test.{ts,tsx}` 后两套测试独立通过。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| ProductIntent UI | 完整字段纠正、取消、focus 与 revision 状态 | `studio/src/components/IntentEditor.tsx`、`IntentEditor.test.tsx` |
| API client | stable ID + expected revision amendment | `studio/src/api/client.ts`、`client.test.ts` |
| OpenAPI types | deterministic schema export 与生成 TypeScript types | `src/psyteardown/api/openapi.py`、`studio/openapi.json`、`studio/src/api/schema.ts` |
| HTTP contract | confirm/correct/conflict/current view 与 schema drift | `tests/api/test_product_studio_smoke.py` |
| Browser Gate | onboarding/correction/conflict/confirmation、keyboard、axe | `studio/e2e/product-studio.spec.ts`、`studio/playwright.config.ts` |
| Visual accessibility | 提高暗色主题语义文本对比度 | `studio/src/styles.css` |

## 决策与偏差

- 复用现有 ProductIntent proposal command；不新增专用 `PATCH`，避免绕开 revision/confirmation 语义。
- 冲突不自动合并价值字段；客户端刷新权威 revision 并保留本地草稿，必须由用户再次提交。
- 生成类型是 transport 边界，不替代面向 UI 的小型别名和 projection helper。
- OpenAPI 生成类型保留 Pydantic 对 default fields 的 optional 表达；UI response aliases 将服务端实际总是返回的 default fields 收窄为 required。这一收窄必须由 HTTP/schema tests 继续保护。

## 验证

- `pytest -q`：441 passed、2 skipped、2 warnings。
- `pytest -q tests/api/test_product_studio_smoke.py`：3 passed。
- `npm test`：4 files、9 tests passed。
- `npm run build`：OpenAPI export、TypeScript build 与 Vite production build 成功；87 modules transformed。
- `npm run test:e2e`：Chromium 1 passed；覆盖 onboarding、键盘、纠正、真实 409 conflict 恢复、确认和三处 axe WCAG A/AA Gate。
- `npm audit`：0 vulnerabilities。
- `python -m pip check`：No broken requirements found。
- 初次浏览器 Gate 失败：axe 报告低对比度文本；修复后连续两次 E2E 通过。初次失败作为有效发现保留在实施记录中。
- 现实证据边界：自动测试只证明覆盖范围内的代码行为、浏览器可操作性和静态规则，不证明真实用户理解或产品价值。

## 数据与迁移

- 不新增数据库 schema；ProductIntent 继续创建不可变 revision。
- OpenAPI 与生成类型纳入源码；生成命令应能检测漂移。

## 遗留项与风险

- 当前只纠正 ProductIntent；ProblemModel 和 OutcomeContract 的浏览器 amendment 尚未实现。
- 冲突恢复会保留内存草稿，但页面刷新/浏览器关闭仍会丢失未提交内容；未实现离线草稿。
- E2E 使用单 Chromium 桌面配置，不代表跨浏览器或移动设备已验证。
- Playwright browser binary 是开发机缓存，不进入仓库；新环境需运行 `npx playwright install chromium`。
- A3 完整 HTTP command/gate/restart matrix 仍缺，已转入下一工作包。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（如适用）
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档（如适用）

## 下一最小工作包

A3.1：从 HTTP 边界补齐四对象 command chain、domain gate、409/422 脱敏错误和 SQLite app 重启恢复，完成 A3 退出门槛后再进入 A5。
