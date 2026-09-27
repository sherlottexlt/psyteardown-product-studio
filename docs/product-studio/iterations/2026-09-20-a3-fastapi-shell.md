# Iteration：A3 FastAPI `/api/v1` 壳

- 日期：2026-09-20
- 状态：Closed（A3.1 已补齐完整 HTTP 契约与恢复矩阵）
- 路线图工作包：A3
- 类型：API

## 目标

通过本地优先的 FastAPI `/api/v1` 暴露 A2 的项目与四对象命令/查询能力，建立稳定的 transport DTO、错误契约、lifespan Repository 管理和 OpenAPI，为 React Product Studio 提供不会绕过领域层的后端入口。

## 基线

- A2 已完成 ProductApplicationService、InMemory/SQLite adapter 和 ProductProjectView；完整测试 438 passed、2 skipped。
- 环境已有 FastAPI 0.115.6、HTTPX 0.28.1、Uvicorn 0.34.0，但尚未声明为项目依赖。
- North Star §11.1 明确 `/api/v1`、命令写入和 localhost 优先；旧 ADR 0085、0061 只记录旧内核选择，其中 0085 被 North Star 明确引用。

## 范围

- FastAPI app factory、lifespan、SQLite service 注入、健康检查和 `/api/v1` router；
- 项目 create/read/status 与四对象 proposal/confirmation/disposition endpoints；
- HTTP request/response DTO，不把领域 snapshot 直接作为请求模型；
- 统一 request ID 与 validation/not-found/conflict/domain-gate/internal 错误 envelope；
- localhost/testserver Host 限制和 Vite 本地开发 origin 配置；
- OpenAPI 与临时 SQLite HTTP 集成测试，包括重启恢复；
- 声明 FastAPI/Uvicorn/HTTPX 依赖和服务启动入口。

## 非目标

- 不实现 React UI、认证、多租户或互联网部署；
- 不在 HTTP 请求中调用 LLM、执行生成代码或启动长任务；
- 不实现 Job/SSE；
- 不实现 ProductThesis → DesignBrief realization adapter。

## 验收条件

- API 请求经过 transport DTO 后构造既有 Command，路由不直接写 Repository；
- OpenAPI 包含项目与四对象 command schemas；
- HTTP 可走通“项目 → intent confirm → problem confirm → contract confirm → thesis selection”；
- stale expected revision 返回 409 且不写新 revision/event；
- schema validation 返回 422，完整用户输入不出现在错误体；
- 未确认上游触发稳定 domain-gate 错误；未知项目返回 404；
- 同一 SQLite 文件关闭 app、重新创建 app 后可以读取项目视图；
- 完整测试通过并同步项目台账。

## 实施记录

1. 写入 `src/psyteardown/api/` 的 app factory、路由、请求/响应 DTO、错误处理与 SQLite lifespan 草稿，更新 `pyproject.toml` 声明 FastAPI/Uvicorn/HTTPX。
2. 第一次启动检查失败：本机 FastAPI 0.115.6 与 Starlette 1.3.1 在 `APIRouter` 初始化处不兼容；HTTP 路由与 OpenAPI 均未完成运行验证。
3. 用户指出旧 ADR 的适用范围被错误继承，随后确认删除本轮新增七篇 ADR 并暂停 A3；此处保留未验证代码草稿，不将其标记为已交付 API。
4. A4 实施时恢复 A3：重新复现并定位为 FastAPI 0.115.6 与 Starlette 1.3.1 的版本冲突，而不是路由或领域代码错误。
5. 将项目 FastAPI 兼容线约束为 `>=0.141,<0.142`，安装解析到 FastAPI 0.141.1 / Starlette 1.6.0；`pip check` 返回无破损依赖。
6. 新增临时 SQLite HTTP 冒烟测试，验证项目创建、ProductIntent proposal、项目读取以及 404 request ID；真实启动 Uvicorn 与 Vite proxy 后，health/create/read 分别返回 200/201/200。
7. 没有把最小冒烟扩写成“稳定 API”：四对象完整 command chain、409/422/domain gate 和 HTTP 重启恢复仍需覆盖。
8. 后续 A3.1 已补齐上述矩阵：完整四对象流程、Gate、冲突、validation 脱敏、OpenAPI commands 和 SQLite app 重启恢复均通过。

## 变更清单

| 区域 | 当前状态 | 证据 |
|---|---|---|
| API 原型 | app factory、路由、DTO、错误处理、host/CORS 和 SQLite lifespan 可启动 | `src/psyteardown/api/` |
| 依赖声明 | FastAPI 兼容线已固定并通过依赖一致性检查 | `pyproject.toml`、`python -m pip check` |
| HTTP 冒烟 | create project → submit intent → read view 与结构化 404 通过 | `tests/api/test_product_studio_smoke.py` |
| 真实联调 | Uvicorn + Vite proxy 下 health/create/read 成功 | 本 iteration 验证记录 |

## 决策与偏差

- 薄 HTTP adapter 符合 North Star §11.1 的方向，但具体 DTO/错误映射是未验证原型；原先误标为 accepted 的新 ADR 已删除。

## 验证

- 初始失败：FastAPI 0.115.6 / Starlette 1.3.1 导入 `APIRouter` 失败；作为历史保留。
- 修复后：`pytest -q tests/api/test_product_studio_smoke.py` 为 2 passed；完整 `pytest -q` 为 440 passed、2 skipped、2 warnings。
- 依赖：`python -m pip check` 为 `No broken requirements found`。
- 真实 HTTP：Vite proxy 访问 health 200；project create 201；project read 200。
- A3.1：`pytest -q tests/api/test_http_contract_matrix.py` 4 passed；完整回归 445 passed、2 skipped、2 warnings。
- 仍未运行远程部署/认证测试，因为它们不属于 localhost-only A3 范围。

## 数据与迁移

- 复用 A2 `product_*` SQLite schema；A3 不新增领域数据表。
- 新增 HTTP 契约但尚无公开发布版本；破坏性变更仍需记录。

## 遗留项与风险

- A4 前需冻结 Product Contract 页面所需的最小 read projection。
- 当前 localhost 限制不是身份认证；任何远程/企业部署前必须加入正式安全边界。
- 当前 FastAPI 上限是兼容性基线，不代表未来禁止升级；升级时必须重跑 API contract 测试。
- TestClient 报告迁移至 `httpx2` 的上游 deprecation warning，需在生态稳定后单独处理。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`

## 下一最小工作包

A5 fake-provider 薄纵向集成；详细 HTTP 矩阵见 [`2026-09-20-a3-1-http-contract-matrix.md`](2026-09-20-a3-1-http-contract-matrix.md)。
