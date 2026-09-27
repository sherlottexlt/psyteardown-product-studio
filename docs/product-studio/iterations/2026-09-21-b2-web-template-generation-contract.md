# Iteration：B2 单一 Web 模板与内容最小化生成契约

- 日期：2026-09-21
- 状态：Closed
- 路线图工作包：Phase B 第 3 步
- 类型：Domain / API / UI / Documentation / Validation

## 目标

为首条数字产品切片关闭 PS-O004：确定唯一受支持的 Web realization 模板，并把 Product Thesis 到代码生成之间的最小输入表达为可版本化、可人工确认的 `WebProductGenerationContract`。

本批次只冻结模板边界与生成输入契约，不执行依赖安装、代码生成、构建、浏览器测试或沙箱操作。

## 基线

- B1 已在确认的 Outcome Contract 上生成三条 ProductThesis，并支持人类选择或授权低成本探索。
- 现有仓库自身使用 React/TypeScript/Vite，但此前没有声明它是首条 realization 的受支持模板，也没有页面/任务/状态/内容最小字段。
- 现有 ProductApplicationService、SQLite repository、HTTP schema 和五区 Web workspace 可复用；代码执行边界 PS-O005、预算 PS-O006 仍未决。

## 决策（关闭 PS-O004）

首条切片唯一模板为 `react_typescript_vite_spa`：

- React + TypeScript + Vite，浏览器 SPA，不引入 SSR、Next.js、React Router 或任意框架代码生成；
- runtime 依赖只允许 `react`、`react-dom`；开发/验证依赖只允许模板锁定的 Vite、TypeScript、React plugin、Vitest、Playwright 和 axe 组合；
- 默认数据模式为本地 fixture + 内存/浏览器本地状态，默认禁用外部网络、账号登录、消息正文访问、隐藏行为采集和第三方 analytics；
- 输出目录和入口固定为 `src/main.tsx`、`src/App.tsx`、`src/styles.css`、`tests/`、`public/`；B3 才定义具体 workspace、锁文件和执行策略；
- 所有生成输入必须绑定 confirmed OutcomeContract 与 selected/exploring ProductThesis revision；页面、任务、状态和内容槽位必须能追溯到这两个 revision；
- 生成契约只允许语义内容槽位，不把未经确认的营销文案或真实结果写成事实；每个关键任务必须有 ready/loading/empty/error 状态与确定性验收检查。

## 范围

- 新增模板常量和最小生成契约领域对象；
- 允许从 B1 的 exploring/selected thesis 自动形成可纠正 proposal，并由人确认；
- ProductProjectView/API/Web 工作台显示当前 Web 生成契约和确认 Gate；
- 记录模板约束、允许依赖和内容槽位的确定性测试。

## 非目标

- 不生成或写入产品源码；
- 不安装 npm 依赖、不启动生成产品、不执行 Playwright；
- 不决定容器/进程/网络/Secret 隔离（PS-O005）；
- 不决定模型、工具、重试、时间或费用预算（PS-O006）；
- 不接入真实 provider、外部账号、消息系统或用户反馈采集。

## 验收条件

- Given confirmed OutcomeContract 和 exploring/selected ProductThesis，When 创建 Web 生成契约 proposal，Then 只使用 `react_typescript_vite_spa` 模板，并固定允许依赖、数据边界和输出布局；
- When proposal 缺少页面、关键任务、必需状态、内容槽位或确定性检查，Then 领域校验拒绝，不写入 current revision；
- When thesis 仍是 proposed/rejected，或 thesis/outcome revision 不匹配，Then API 返回显式 domain gate；
- When 用户确认契约，Then 保存不可变 revision、确认者、来源与 thesis/outcome 依赖；上游变化记录 `stale` impact；
- Web 工作台显示契约状态、模板、页面/任务/状态摘要和“代码生成尚未接入”，不能伪装成可运行产品；
- Python/API/前端测试、OpenAPI 类型生成、production build 和既有 Chromium E2E 通过。

## 实施记录

- 2026-09-21：B2 开始。选择复用现有 React/TypeScript/Vite 技术方向，但将其收窄为首条切片唯一模板；使用语义内容槽位替代自由文案，避免把生成结果当作已验证事实。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain | 新增 `WebProductGenerationContract`、页面/任务/状态/内容槽位/验收检查值对象与固定模板常量 | `src/psyteardown/product/models.py`, `src/psyteardown/product/commands.py` |
| workflow | Web generation contract proposal Job 固定 confirmed OutcomeContract + exploring/selected thesis revision | `src/psyteardown/product/jobs.py`, `src/psyteardown/product/providers.py` |
| API | proposal/confirmation endpoint、ProjectView projection、OpenAPI transport types | `src/psyteardown/api/projects.py`, `src/psyteardown/api/schemas.py`, `studio/openapi.json` |
| UI | 工作台显示/确认生成契约，并明确未生成源码或运行产品 | `studio/src/views/WorkbenchView.tsx`, `studio/src/views/ProjectStudio.tsx` |
| tests | B2 Job/API/template boundary tests | `tests/product/test_jobs.py`, `tests/api/test_proposal_jobs.py` |

## 决策与偏差

- PS-O004 在本批次关闭；PS-O005/PS-O006 保持 open，不因模板选择而默认批准代码执行。
- `WebProductGenerationContract` 是 realization 输入契约，不是最终代码工程 schema；B3 仍需验证页面/状态字段是否足够。

## 验证

- 命令：`pytest -q`; `Push-Location studio; npm test -- --run; npm run build; npm run test:e2e; Pop-Location`
- 结果：Python 461 passed、2 skipped、2 warnings；前端 11 passed；production build 成功；Chromium 2 passed（含 axe）
- 现实证据边界：契约校验只证明输入边界与追溯关系，不证明生成产品可用、可访问、可靠或改善真实任务结果。

## 数据与迁移

- 使用现有 `product_revisions`/`product_current` 通用表新增对象类型，不新增 SQLite 表；旧数据库可通过 `CREATE TABLE IF NOT EXISTS` 路径继续打开。
- ProductProjectView/API 增加 nullable `web_generation_contract` 字段；前端 OpenAPI 类型重新生成。

## 遗留项与风险

- B3 需要定义实际模板锁文件、workspace、生成 Job、预算和沙箱；
- 单页模板是否需要真实多路由要由第一条生成产品的任务测试复核；
- 本批不提高任何现实证据等级。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档（如适用）

## 下一最小工作包

关闭 PS-O005/PS-O006 的最小决策，并为已确认 Web 生成契约建立持久化生成 Job 的 workspace/预算边界；在此之前不执行任意生成代码。
