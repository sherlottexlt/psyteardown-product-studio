# Iteration：A3.1 HTTP 契约与恢复矩阵

- 日期：2026-09-20
- 状态：Closed
- 路线图工作包：A3
- 类型：API / Validation

## 目标

从真实 HTTP 边界验证 Product Studio 四对象命令链、revision conflict、domain gate、请求校验脱敏和 SQLite app 重启恢复，判断 A3 是否达到退出门槛。

## 基线

- FastAPI app、路由、DTO、错误 envelope、localhost host/CORS 和 SQLite lifespan 已实现。
- A4.1 已锁定 OpenAPI schema 与生成客户端类型，并验证最小 ProductIntent amendment/conflict HTTP 路径。
- A1/A2 领域与应用层测试已覆盖完整对象流，但不能替代 HTTP adapter 的字段映射、状态码和事务恢复验证。
- 完整回归为 441 passed、2 skipped；API smoke 3 passed。

## 范围

- HTTP 完整 happy path：project → intent confirm → problem confirm → outcome contract confirm → thesis → disposition；
- 未确认 upstream 的 domain gate；
- stale `expected_revision` 返回 409 且 current revision 不改变；
- 422 validation error 不回显敏感/完整 rejected input；
- 同一 SQLite 文件关闭第一个 app、创建第二个 app 后读取完整 project view；
- OpenAPI 必须继续表达所有 command schemas。

## 非目标

- 不新增 API 资源或领域字段；
- 不实现 Job/SSE、认证、远程部署或跨项目权限；
- 不修改 A1/A2 原型的业务 Gate；
- 不接模型 provider。

## 验收条件

- 所有写路由只构造现有 Command，完整 happy path 返回预期 revision/status；
- domain gate、revision conflict、validation 和 not-found 拥有稳定 code/status/request ID；
- 失败写入不改变 current projection；
- app lifespan 关闭并重开后 SQLite projection、confirmation、disposition 和 impact 可恢复；
- OpenAPI drift、API matrix、全量 Python 与前端回归通过。

## 实施记录

1. 在 A4.1 关闭后先建立本 iteration，范围限定为验证现有 adapter，不新增路由或领域状态。
2. 初版尝试复用 `tests/product/test_service.py` 的 helper，但 pytest 收集环境不提供 `tests` 顶层包；收集即失败，未执行测试。
3. 将有效 HTTP payload 提取为 `tests/api/payloads.py`，使 API tests 自包含且不依赖其他测试模块的导入副作用。
4. 完整 HTTP 流程依次创建/确认 ProductIntent、ProblemModel、OutcomeContract，创建并选择 ProductThesis。
5. 对已选择 thesis 发起 stale transition，验证 409 `revision_conflict`、request ID 和 current projection 不变。
6. 关闭第一个 FastAPI lifespan 后，以同一 SQLite 文件创建新 app，验证四对象 confirmation/disposition 完整恢复。
7. 单独验证 unconfirmed ProductIntent 阻止 ProblemModel proposal，返回 409 `domain_gate` 且不写 current problem。
8. 发送包含敏感 marker 的无效 proposal，验证 422 issues 有字段位置/错误类型但 response 不回显被拒绝输入。
9. 验证 OpenAPI 包含所有项目/四对象 command request、错误和 project view schemas。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| Payload fixtures | 自包含的有效四对象 HTTP payload | `tests/api/payloads.py` |
| Happy path | 四对象 proposal/confirm/disposition command chain | `tests/api/test_http_contract_matrix.py` |
| Error matrix | domain gate、stale 409、422 输入脱敏 | `tests/api/test_http_contract_matrix.py` |
| Recovery | 同 SQLite 跨 app lifespan 恢复完整 projection | `tests/api/test_http_contract_matrix.py` |
| Schema | 全 command schema OpenAPI presence | `tests/api/test_http_contract_matrix.py` |

## 决策与偏差

- 本批只验证现有 HTTP 原型，不因测试通过把 A1/A2 字段与聚合升级为正式长期架构。
- 测试 payload 留在 API test package，不提升为生产 fixture 或产品默认内容。

## 验证

- `pytest -q tests/api/test_http_contract_matrix.py`：4 passed、2 warnings。
- `pytest -q`：445 passed、2 skipped、2 warnings。
- `npm test`：4 files、9 tests passed。
- `npm run build`：OpenAPI generation、TypeScript/Vite production build 成功。
- `npm run test:e2e`：Chromium 1 passed。
- `npm audit`：0 vulnerabilities；`python -m pip check`：无破损依赖。
- 初次 targeted test 在 collection 失败（跨 test package import）；改为自包含 payload 后通过，已记录而未隐藏。

## 数据与迁移

- 不新增 schema；验证当前 `product_*` SQLite 数据能跨 app lifespan 恢复。

## 遗留项与风险

- FastAPI TestClient 仍提示未来迁移 `httpx2`；这是上游生态迁移 warning，不影响当前契约行为。
- localhost host/CORS 是本地开发边界，不是身份认证，不能用于远程部署。
- A3 验证的是当前 prototype schema；A1/A2 产品字段和聚合仍需真实用户切片校准。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（无新决策；更新既有原型状态）
- [x] `EVOLUTION_LOG.md`
- [x] 用户/开发者入口文档（不需要新增启动方式）

## 下一最小工作包

A5：先确定 fake provider proposal 与未来持久化 Job 的边界，再走通“已确认意图 → 问题 proposal → 人工确认 → 结果契约 proposal → 人工确认”；不在同步 HTTP 路由中偷渡真实模型调用。
