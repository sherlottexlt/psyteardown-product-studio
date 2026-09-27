# Iteration：A4 Product Studio Web 壳（第一批）

- 日期：2026-09-20
- 状态：Closed（本批次完成；A4 路线图退出门槛仍有剩余项）
- 路线图工作包：A4
- 类型：UI / API integration

## 目标

建立可运行的 React/TypeScript/Vite Product Studio 工作空间，使用户能从浏览器创建项目和初始 ProductIntent，读取后端项目 projection，并在同一 revision 上下文中进入对话、产品契约、工作台、决策和证据五个区域。

## 基线

- A1/A2 的 Product 上位对象、Application Service 和 SQLite adapter 已有 438 个完整回归测试，但仍是待首条用户闭环校准的原型。
- A3 已有代码草稿，但 FastAPI 0.115.6 / Starlette 1.3.1 不兼容，尚无 HTTP 集成测试。
- 仓库没有 React、TypeScript、Vite、前端测试或浏览器工作空间。
- North Star §4、§10、§11、§13 要求 Web Product Studio 为主产品形态，同时禁止把聊天、仿真或未运行产物伪装成状态和证据。
- 流程偏差：本 iteration 记录没有在编码前创建；这是执行工作流时的遗漏。本文件在收尾时补建，后续批次必须先建立 iteration 再实施。

## 范围

- 建立独立 `studio/` React/TypeScript/Vite 工程、Query client、测试和 production build；
- 建立项目 onboarding：项目名称、希望改变的现实、受影响人群、协作模式和可选情境；
- 调用真实 `/api/v1` 创建 ProductProject 并提交初始 ProductIntent proposal；
- 读取 ProductProjectView，并提供五区导航、Product Contract projection、产品论点、决策和证据视图；
- 调用已有确认和 ProductThesis transition commands；
- 提供加载、空、错误、未知、revision impact 和未实现能力的明确界面；
- 恢复 A3 最小运行条件，增加 HTTP 冒烟和真实 Vite→FastAPI 代理联调。

## 非目标

- 不接真实 LLM，不从自然语言自动生成 ProblemModel、OutcomeContract 或 ProductThesis；
- 不实现已存在 Product Contract proposal 的字段编辑/修订；
- 不实现 Job/SSE、代码沙箱、产品生成、运行预览、Playwright 或导出；
- 不宣称浏览器单测、构建或界面展示证明任何用户结果；
- 不确认 A1/A2 的字段、聚合和存储为长期正式架构。

## 验收条件

- Given 本地 API 已启动，When 用户填写最小 onboarding，Then 前端依次创建项目和初始 ProductIntent，并只在两步成功后进入工作空间；
- When 打开项目 URL，Then 前端从 `/api/v1/projects/{id}` 读取同一 ProductProjectView，并在五区共享；
- When 当前对象需要具名人工确认，Then 决策区通过既有 Domain Command 写入，不直接修改客户端状态或 Repository；
- When 后端不可达、项目未知或能力尚未实现，Then 显示可区分的错误/空/未实现状态，不生成虚假成果；
- TypeScript 类型检查、Vite production build、前端单测、Python 回归、依赖审计和最小 HTTP 联调通过。

## 实施记录

1. 创建 `studio/` 工程和本地 `/api` proxy，选择 TanStack Query 管理服务端 project projection。
2. 建立暗色、成果物中心、响应式五区工作空间；对话生成和运行预览使用显式 unavailable state。
3. onboarding 使用两个既有命令，而不是在前端伪造一个跨聚合命令；若项目创建成功但 intent 失败，错误中保留 project ID 供恢复。
4. 前端 transport 类型暂时手工映射后端 response；记录为 schema 漂移风险，不视为 North Star 要求的最终生成/校验方案。
5. 首轮 production build 发现 `import.meta.env` 和 Vitest config 类型缺失，补充 `vite/client` 并改用 `vitest/config`。
6. API 集成首次运行复现 A3 依赖冲突；升级并约束 FastAPI 后新增 HTTP 冒烟。
7. `npm audit` 发现旧 Vitest 测试依赖的中等级路径穿越公告；升级到 Vitest 5.0.1 后审计归零并重跑测试/构建。
8. 移除 Google Fonts 网络导入，改用本机字体栈，避免本地工作空间仅因打开界面就向第三方发起请求。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| UI 工程 | React/TypeScript/Vite、Query client、响应式视觉系统 | `studio/package.json`、`studio/src/main.tsx`、`studio/src/styles.css` |
| Onboarding | 创建项目并保存初始 ProductIntent | `studio/src/views/NewProject.tsx`、`NewProject.test.tsx` |
| API client | create/read/intent/confirm/thesis transition 与稳定错误 | `studio/src/api/client.ts`、`client.test.ts` |
| Product Studio | 五区导航和共享 ProductProjectView | `studio/src/views/ProjectStudio.tsx` 及各 view |
| Projection | 阶段、待人决定和未知计数 | `studio/src/domain/project.ts`、`project.test.ts` |
| API 集成 | 临时 SQLite create/intent/read 与结构化错误 | `tests/api/test_product_studio_smoke.py` |
| 依赖边界 | FastAPI 兼容线、前端 lockfile、生成物忽略 | `pyproject.toml`、`studio/package-lock.json`、`.gitignore` |
| 开发入口 | 本地启动与能力边界 | 根 `README.md`、`studio/README.md` |

## 决策与偏差

- React/TypeScript/Vite、FastAPI 和 Web 主界面来自 North Star 已确认方向；TanStack Query、独立 `studio/` 目录、手工 transport types 和当前信息架构细节仅是可回退的原型选择，登记为 PS-H007。
- 没有等待 PS-O001 首个具体用户问题再搭壳；本批次只建立通用工作区和明确空态，不生成具体产品方案。PS-O001 仍是 Phase B 的硬 Gate。
- A4 完整退出门槛要求“纠正 Product Contract”和基础可访问性检查；本批次只有初始输入、查看与确认，没有字段修订、Playwright 或自动 a11y，因此路线图 A4 保持 `in progress`。
- 本批次先编码后补 iteration 记录，违反开发台账的开始前协议；已在演变日志显式记录，不将补文档写成原本已遵循流程。

## 验证

- `npm test`：3 files、6 tests passed（Vitest 5.0.1）。
- `npm run build`：TypeScript project build 和 Vite production build 成功；86 modules transformed。
- `npm audit`：0 vulnerabilities。
- `pytest -q tests/api/test_product_studio_smoke.py`：2 passed。
- `pytest -q`：440 passed、2 skipped、2 warnings。
- `python -m pip check`：No broken requirements found。
- 真实联调：Uvicorn `127.0.0.1:8000` 与 Vite `127.0.0.1:5173` 同时启动，经 Vite proxy 的 health=200、project create=201、project read=200。
- 未运行：真实浏览器 Playwright、自动可访问性、视觉回归和用户试用；因此不能证明键盘可用性、跨浏览器表现或用户价值。
- 现实证据边界：上述检查只证明覆盖范围内的代码、构建和 HTTP 集成，不证明 Product Studio 能生成产品，也不证明任何产品改善了真实结果。

## 数据与迁移

- 没有新增领域 schema 或数据库迁移；继续使用 A2 `product_*` SQLite schema。
- 前端引入 `package-lock.json` 固定依赖；`node_modules`、build 和 coverage 产物不入库。
- onboarding 两步写入不是原子事务；失败时已创建项目不会自动删除，属于可恢复的孤立项目，后续需项目列表或恢复命令处理。
- API 尚未公开发布；手工 TypeScript 类型变化前必须与 OpenAPI/response DTO 一起复核。

## 遗留项与风险

- 已存在 ProductIntent/ProblemModel/OutcomeContract 尚不能从浏览器编辑并提交新 proposal revision。
- 手工 TypeScript transport 类型可能与 OpenAPI 漂移。
- 没有浏览器 E2E、键盘、a11y 或视觉回归。
- 没有项目列表；只用 URL 和 localStorage 保存最后项目 ID。
- A3 完整 command/gate/conflict/restart HTTP 矩阵尚缺。
- 没有模型 provider、Job、SSE、代码生成、沙箱或可运行产品预览。
- 已更新 `DECISION_REGISTER.md` 的 PS-H006，并新增 PS-H007；没有新增正式 ADR，也没有提高现实证据等级。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档

## 下一最小工作包

A4.1：为现有 ProductIntent proposal 增加可编辑修订与 revision conflict UX，接入 OpenAPI 类型一致性检查，并用浏览器测试覆盖 onboarding、查看/纠正/确认、键盘操作和基础可访问性；不在该批次接 LLM 或生成产品。
