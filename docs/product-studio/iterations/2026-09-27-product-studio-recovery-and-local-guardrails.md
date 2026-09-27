# C1 真实体验验证前的本地体验约束补强

- 状态：`Closed`
- 日期：2026-09-27
- 所属阶段：Phase C
- 工作包：C1.1

## 背景

C1 的真实参与者/负责人真实体验验证先暂缓。当前阻塞体验的不是 C1 intake 本身，而是 Product Studio 的本地工作空间仍把若干已知约束直接暴露给用户：关闭浏览器后难以找回项目和未完成 Job、生成/验证 Job 缺少可见的继续和控制入口、原始输入没有明确边界、B4 使用固定 4173 端口容易被本机其他进程阻塞。

## 目标

在不改变 C1 同意、撤回、来源层和证据等级边界的前提下，让本地 Product Studio 在中断、失败和端口冲突时可恢复、可解释、可继续。

## 非目标

- 不招募参与者，不启动真实自试，不新增 `MeasurementObservation` 或 `EvidenceReview`。
- 不引入常驻 worker、队列基础设施或部署级 OS/container 隔离。
- 不做自动脱敏；原始输入仍按 C0 的本地-first provider/transcript 边界处理。
- 不把 Job 控件描述为对已经运行的同步子进程提供即时终止保证。

## 实施内容

1. **工作区恢复**
   - 新增 `GET /api/v1/projects`，从 Product repository 返回当前项目列表。
   - 首页展示最近本地工作区，可从列表恢复，不再只依赖一个 localStorage project ID。
2. **未完成 Job 恢复与控制**
   - 工作区主链路发现 `queued`/`running`/`paused` 的 proposal、generation 或 execution Job 时显示继续入口。
   - Generation Job 暴露暂停、继续、取消；Execution Job 暴露停止和失败后重试。
   - 所有操作仍通过已有 revisioned Job API，不建立第二套状态源。
3. **输入边界**
   - `product_intent` raw input 增加服务端和领域模型 4000 字符上限。
   - 新建项目表单增加 `maxlength`、计数和本地保存/发送提示。
4. **本地预览端口**
   - B4 优先使用 4173；占用时选择可用 loopback 端口。
   - 解析实际 preview command 的端口，并将同一 URL 传给健康检查和 Playwright `BASE_URL`。

## 验收与证据

- `tests/api/test_product_studio_smoke.py`：项目列表恢复。
- `tests/api/test_proposal_jobs.py`：raw input 超限在 Job 持久化前拒绝。
- `tests/product/test_execution.py`：既有预览端口安全边界仍通过；执行服务使用动态端口参数。
- `studio/e2e/product-studio.spec.ts`：新增 queued proposal 工作区恢复场景；Chromium E2E 3/3 通过，包含 axe serious/critical Gate。
- 前端 `npm test -- --run`：28 passed。
- 本地新建项目默认使用 deterministic fake；real provider 保留为 Product Contract 区的显式选择，避免本地恢复 Gate 被外部模型配置阻断。
- 前端 `npm run build`：成功。
- 目标 Python/API 回归与全量确定性回归：556 passed、3 skipped、2 warnings（既有 Pydantic 字段遮蔽与 Starlette/httpx 迁移 warning）。

## 遗留风险

- API action 是同步请求；如果另一个请求已经进入子进程，暂停/取消不能保证即时杀进程，需通过后续刷新确认最终持久化状态。
- 4000 字符上限是容量/风险边界，不是脱敏或隐私保护。
- 动态端口只解决本地冲突，不改变 B4 仍为本机 subprocess、无容器隔离的事实。
- C1 仍没有真实参与者数据；本批不改变 `Outcome Evidence`。
