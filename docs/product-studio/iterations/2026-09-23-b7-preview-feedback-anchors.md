# Iteration：B7 预览与显式反馈锚点

- 日期：2026-09-23
- 状态：Closed
- 路线图工作包：Phase B 第 8 步（用户在 Product Studio 中直接使用 → 反馈锚定到页面、任务和 revision）
- 类型：Decision / Domain / Persistence / API / UI

## 目标

让用户在工作台内直接打开一个已导出（B6）交付包里的构建物，并提交**只由用户主动写下**的反馈；
每条反馈锚定到交付包 revision、执行 revision、Web 契约 revision 与页面（可选任务/状态），
提交前取得显式同意，提交者可随时撤回，撤回后正文从存储中清除。

## 基线

- B6 已关闭（`a344e7e`）；`pytest -q` 490 passed、3 skipped；前端 15 passed；Chromium E2E 2 passed；
- 工作台预览区仍是“运行环境尚未接入”占位；
- PS-O007 open。

## PS-O007 决策（用户于 2026-09-23 选择“仅显式反馈”）

- 采集粒度：仅用户主动提交的一条反馈 = 锚点（交付包/执行/契约 revision + screen + 可选 task/state）+ 类别（bug/confusing/missing/works）+ 文本 + 提交者 + 时间；
- 不采集：点击流、页面切换、输入内容、录屏、截图、停留时长或任何自动事件；预览 iframe 与工作台之间不建立消息通道；
- 同意：每次提交携带当前同意版本并显式勾选；服务端拒绝缺失或过期版本；
- 撤回：提交者可撤回；撤回产生 r2 墓碑，正文与类别清空，锚点与提交者保留作审计；SQLite 启用 `secure_delete`，被覆盖的正文不留在空闲页；
- 证据等级：`user_report`，不升级为 Outcome Evidence，不代表任务完成或真实结果。

## 范围

- 预览：从 B6 archive（下载前同样复核 sha256 与逐文件 hash）读取 `build/` 条目提供只读预览；CSP `sandbox allow-scripts`、`connect-src 'none'`、`nosniff`、`no-referrer`；工作台 iframe `sandbox="allow-scripts"`；
- 仅在服务预览时把 `index.html` 中根绝对 `/assets/` 引用改写为相对路径（Vite 默认 base），包字节不变；
- `PreviewFeedback` 领域对象、InMemory/SQLite 存储、提交/列表/撤回服务；
- `/delivery-bundles/{id}/preview/…`、`/delivery-bundles/{id}/feedback`、`/preview-feedback`、`/preview-feedback/{id}/withdrawal`、`/preview-feedback-policy`；
- 工作台预览 + 反馈表单 + 已提交列表与撤回。

## 非目标

- 不做 AI 根据反馈自动迭代（下一包）；不做版本差异视图；
- 不做多用户身份、远程分享链接、公网预览；
- 不做自动事件、任务自报表单（PS-O007 未选）；
- 不做视觉基线/跨浏览器/容器隔离。

## 验收条件

- 预览只服务 bundle 清单中 `build/` 下的文件；archive 或条目 hash 不符、路径穿越、未知类型均拒绝；
- 缺同意/同意版本不符 → 409 `domain_gate` 且不写记录；锚点不在 bundle 所 pin 的契约 revision 中 → 拒绝；
- 撤回仅限提交者与期望 revision；撤回后 API 与 SQLite 原始文件均不再含正文；重启可恢复列表；
- 真实浏览器中 iframe 能渲染真实 B3→B4→B6 构建物；
- Python/前端测试、OpenAPI drift、生产构建与 E2E 通过。

## 实施记录

1. 领域：`PreviewFeedback`/`PreviewFeedbackAnchor`/`PreviewFeedbackConsent` 与同意政策常量（`models.py`）；模型校验 submitted=r1 有正文、withdrawn=r2 无正文、同意人即提交者。
2. 服务 `ProductPreviewFeedbackService`：`preview_file` 先复核整个 archive hash，再复核条目 hash，只服务清单内 `build/` 下已知扩展名；`submit_feedback` 校验同意版本、正文长度与 bundle pin 的契约 revision 中的锚点；`withdraw_feedback` 仅限提交者与 expected revision。
3. 持久化：`product_preview_feedback` 单行表，撤回为条件 UPDATE；连接级 `PRAGMA secure_delete = ON`。测试直接扫描 SQLite 文件字节确认撤回正文消失。
4. API：`/preview-feedback-policy`、预览、提交、列表、撤回；预览响应带 CSP sandbox、nosniff、no-referrer、no-store 和 `Access-Control-Allow-Origin: *`（opaque origin 的 module script 是 CORS 请求）。
5. UI：`PreviewFeedbackPanel` 替换工作台占位；页面/任务/状态下拉来自与交付包同 revision 的契约（不一致时禁用并提示）；同意勾选每次提交后复位；撤回后显示墓碑。
6. 真实验证中发现并修正：反馈列表锚点显示内部 ID（改为页面标题/任务目标/状态类型）、沙箱徽标溢出。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain | PreviewFeedback 模型与政策常量 | `src/psyteardown/product/models.py` |
| service | 预览与反馈服务 | `src/psyteardown/product/feedback.py`、`tests/product/test_feedback.py`（12） |
| persistence | 单行反馈表、`secure_delete` | `src/psyteardown/product/sqlite.py` |
| api | 5 个端点 + OpenAPI | `src/psyteardown/api/preview_feedback.py`、`tests/api/test_preview_feedback.py`（2）、`studio/openapi.json` |
| ui | 预览 + 反馈面板 | `studio/src/views/{PreviewFeedbackPanel,WorkbenchView,ProjectStudio}.tsx`、`PreviewFeedbackPanel.test.tsx`（4）、`WorkbenchView.test.tsx`（+1） |

## 决策与偏差

- PS-O007 关闭（用户选择仅显式反馈）；新增 PS-H013。
- 偏离 revision 惯例：反馈撤回覆盖同一行而不保留 r1 快照——这是“撤回即擦除”的必要条件，已在 PS-H013 记录。
- 预览放在 API 同源路径下，依靠 CSP sandbox 获得 opaque origin，而不是另起端口/源；远程或多用户场景需重新评估。

## 验证

- `pytest -q`：504 passed、3 skipped、2 warnings；`npm test`：20 passed；`npm run build` 成功（OpenAPI 重新生成）；Chromium E2E：2 passed。
- 真实链路（无 fake runner）：B3 → B4（install/build/run/browser 共 43.0s，全部成功）→ B6（19 文件）→ B7：Studio 中 iframe 渲染 “Re-entry bookmark”，点击 Continue 后状态变为 “Local action confirmed.”；iframe 内 `fetch('/api/v1/health')` 被 `connect-src 'none'` 拒绝，访问 `window.parent.location` 被拒绝；未勾选同意时提交按钮禁用；提交与撤回成功；axe 无 serious/critical。
- 证据边界：以上只证明本机覆盖范围内的软件行为；反馈为 `user_report`，`outcome_evidence_level` 仍为 `none`。

## 数据与迁移

- 新表 `CREATE TABLE IF NOT EXISTS`，旧库打开即升级；`secure_delete` 仅影响之后的删除/覆盖。

## 遗留项与风险

- actor 仍是本地固定 `local-user`，“仅提交者可撤回”在单机下等同于同一用户；多用户需要真实身份；
- 反馈无保留期限；无编辑（只能撤回后重提）；
- 预览每次请求读取 zip（≤8 MiB，本地可接受）；
- E2E 未覆盖 B3→B7 UI 全链路（需真实 npm 安装约 40s），由本批一次性真实脚本验证代替。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`

## 下一最小工作包

B8 反馈驱动的迭代与版本差异：选定的显式反馈 pin 为新 Web 契约提案输入（人确认后）→ B3/B4/B6 → 工作台展示两个交付 revision 的差异与反馈处理状态。
