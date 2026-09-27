# Iteration：B3 受预算约束的 Web 生成 Job workspace

- 日期：2026-09-21
- 状态：Closed
- 路线图工作包：Phase B 第 4 步（生成 Job 的首条本地切片）
- 类型：Domain / Job / Sandbox / API / UI / Validation

## 目标

在已确认的 `WebProductGenerationContract` 上建立一条可恢复、幂等且受预算约束的本地生成路径。关闭首条切片的 PS-O005（沙箱边界）和 PS-O006（预算边界），由确定性的模板生成器把契约物化为一个受控 workspace，并保存文件清单、校验摘要和 Job checkpoint。

本批次验证的是“契约 → 受限源码 workspace”的软件闭环，不把生成源码、静态校验或自动化测试当作真实用户结果，也不宣称已经完成产品运行、Playwright 验证或部署。

## 基线

- B2 已确认唯一模板 `react_typescript_vite_spa` 及页面、任务、状态、内容槽位和确定性验收检查。
- 现有 proposal Job 已能 enqueue、单步运行、重试、处理 stale input 并在 SQLite 重启后恢复，但不能生成源码或记录资源消耗。
- Product Studio 的本地 API 只允许 localhost，浏览器仍通过显式 command 触发长任务。

## 决策（关闭 PS-O005 / PS-O006）

### PS-O005：本地 sandbox 边界

- 每个生成 Job 使用 `workspace_root/<project_id>/<job_id>/` 的独立目录；项目和 Job 标识只能由安全字符组成，解析后的路径必须位于配置的 workspace root 内。
- 生成器只能写入该 workspace 的相对路径；拒绝绝对路径、`..` 穿越、符号链接和受保护文件名（`.env`、凭据、私钥等）。
- 运行时数据边界继续为本地 fixture、无外部网络、无 Secret 注入；Job 日志和 API 只返回安全摘要，不返回任意文件路径或文件内容。
- B3 不执行生成源码、不安装依赖、不启动子进程；执行/预览前仍需单独的运行 sandbox Gate。这样本批次的验证不会把本机 Python 进程当成隔离容器。
- workspace 由确定性生成器和 manifest 校验器管理，最大文件数和总字节数由预算约束；写入采用临时目录后原子替换，失败不覆盖已确认的 workspace。

### PS-O006：首条切片预算

默认 `GenerationBudget` 为：一次生成尝试、三个逻辑步骤（prepare/generate/validate）、最多 64 个文件、总大小 1 MiB、最长 60 秒、1 个成本单位。成本单位只表示本地生成工作量，不是模型或现实货币费用；当前 provider 没有外部模型费用。

Job 可暂停、恢复、取消和重试，但任何重试都必须重新检查输入 revision，并受 `max_attempts` 限制；超出限制进入 `budget_exhausted`，不会继续写 workspace。预算可在创建 Job 时收紧，不能超过模板默认上限。

## 范围

- `ProductGenerationJob` revision 模型、预算/沙箱值对象、workspace manifest 和 SQLite/InMemory 持久化；
- 确认后的 Web generation contract 才能创建生成 Job；fingerprint 保证重复请求复用同一 Job；上游 revision 变化进入 `stale_input`；
- 确定性 `react_typescript_vite_spa` 模板生成最小源码、配置和确定性检查文件；不访问网络、不读取 Secret；
- HTTP `/generation-jobs` 命令/状态入口和 Web 工作台的生成状态、workspace/预算边界呈现；
- 针对路径穿越、预算耗尽、取消/恢复、stale、重启和 manifest 校验的测试。

## 非目标

- 真实模型/研究 provider、自由代码生成或代码修复；
- npm 依赖安装、构建、Playwright、浏览器预览、SSE 或常驻 worker；
- 容器/Kubernetes、远程执行、多租户 Secret 管理和部署；
- 现实用户、可访问性、性能、商业或 Outcome Contract 结果证据。

## 验收条件

- Given confirmed Web generation contract，When 创建并运行 Job，Then 只在安全 workspace 下产生模板源码和 manifest，保存输入 revision、attempt、预算消耗和确定性校验结果；
- When 重复请求相同契约和预算，Then 复用同一活跃/成功 Job，不重复写入新的 workspace；
- When 上游 thesis/outcome/contract revision 变化，Then Job 标记 `stale_input`，不提交新 workspace；
- When 请求超过文件/字节/尝试预算或命中 sandbox 规则，Then 进入显式失败/`budget_exhausted`，不泄露内部路径或 Secret；
- When Job 暂停、恢复、取消或 SQLite 重启，Then 状态、checkpoint 和 manifest 可恢复；
- API、前端类型、生产构建、既有测试和新增 B3 测试通过。

## 当前实施记录

- 2026-09-21：建立本记录，冻结本地无网络/无 Secret/不执行源码的 sandbox 边界，以及一次尝试、三步、1 MiB workspace 的默认预算。
- 2026-09-21：实现 `ProductGenerationJob`、SQLite/InMemory adapter、固定模板物化器、Generation Job API 与工作台入口；补齐幂等、stale、预算耗尽、路径校验、重启恢复和 HTTP 测试。

## 遗留项

- B4 再决定依赖安装、构建、运行和 Playwright 的独立执行 sandbox；
- 首次真实任务观察后复核页面/状态字段、模板锁文件和预算是否足够；
- 生成源码仍是软件产物，不提升现实证据等级。

## 验证

- `pytest -q`：469 passed、2 skipped、2 warnings；
- `Push-Location studio; npm test -- --run; npm run build; Pop-Location`：11 passed，production build 成功；
- 新增证据：`tests/product/test_generation.py`、`tests/api/test_generation_jobs.py`；OpenAPI 与 `studio/src/api/schema.ts` 已重新生成并通过 drift test。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`
- [x] `README.md` / `studio/README.md`

## 下一最小工作包

B4：为现有 workspace 定义独立依赖安装、构建、运行与 Playwright/axe 验证 sandbox；执行权限必须继续与源码生成权限分离。
