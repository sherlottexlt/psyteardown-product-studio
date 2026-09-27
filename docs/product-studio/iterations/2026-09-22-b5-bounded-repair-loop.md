# Iteration：B5 受限失败定位与修复闭环

- 日期：2026-09-22
- 状态：Closed
- 路线图工作包：Phase B 第 7 步
- 类型：Repair Job / Provenance / Budget / API / UI

## 目标

在 B4 执行失败后，提供一个独立、持久化且受预算约束的 Repair Job。Repair Job
只读取执行步骤的安全摘要，使用确定性的修复规划器生成白名单补丁，在新的
workspace 中应用并启动新的验证 Execution Job；原始生成 workspace 和失败执行
revision 保持不可变。每次修复尝试、补丁、输入 revision 和成本都必须可恢复。

## 非目标

- 不接入真实模型、远程代码代理或任意框架代码生成；
- 不保存原始命令输出、Secret 或未经筛选的日志；
- 不允许修改测试、依赖锁、脚本或 manifest 来“刷绿”；
- 不把软件验证成功升级为真实用户结果或 Outcome Evidence；
- 不在本批次解决容器/远程多租户隔离和自动部署。

## 暂定实现边界

- Repair Job pin 一个失败的 B4 Execution Job revision；输入变化进入 `stale_input`；
- planner 只接收步骤名、错误码和安全摘要，输出 `search/replace` 补丁；路径、原文
  hash、文件数量、字节和单次成本均受预算限制；
- 补丁写入新的 repair workspace，并注册为带父 generation lineage 的不可变生成
  revision，再由独立 Execution Job 验证；原 workspace 不会被覆盖；
- 默认 deterministic planner 只处理模板中已知的无障碍状态播报修复；其他失败返回
  `unsupported_failure`，保留诊断但不猜测性修改源码；planner 可注入以测试其他
  明确、可审查的修复规则；
- Repair Job 使用显式单步 `run`，重试仍受 attempt/cost 上限约束；每次失败的补丁
  和对应验证 Job 引用都会保留。

## 验收条件

- InMemory/SQLite 均能保存 Repair Job revision、尝试记录和重启后的当前状态；
- 同一失败执行 revision 与预算的重复创建幂等；上游 revision 变化不会应用补丁；
- 路径穿越、符号链接、hash 不匹配、修改非白名单文件和超预算均被拒绝；
- 成功修复产生新的 generation revision 与 Execution Job，原 B3/B4 revision 不变；
- API 暴露创建、读取、列表、运行、重试、取消；工作台显示失败诊断、尝试成本和
  “自动修复”入口；
- Python、前端单测、OpenAPI drift 和生产构建通过。

## 验证结果

- `pytest -q`：477 passed、2 skipped、2 warnings；`tests/product/test_repair.py`：4 passed；
- `npm test`：11 passed；`npm run build` 成功；Chromium E2E：2 passed；OpenAPI/schema drift 重新生成并通过；
- 原始 B3/B4 workspace 与 revision 在成功修复后保持不变；未知失败保留安全诊断并停止，不猜测性改写源码。

## 遗留（不阻塞本批关闭）

- 真实模型/工具驱动的诊断和跨框架修复需先建立 provider、费用、输入保留与审查边界；
- 视觉回归基线、跨浏览器/移动验证和部署级隔离仍不在本批次；
- 预览反馈采集与用户同意仍对应 PS-O007，不能由本地 Repair Job 代替。
