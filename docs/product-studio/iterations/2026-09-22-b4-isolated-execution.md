# Iteration：B4 受隔离执行的构建、运行与浏览器验证

- 日期：2026-09-22
- 状态：Closed（本地执行切片）
- 路线图工作包：Phase B 第 5–6 步
- 类型：Execution / Sandbox / API / UI / Validation

## 目标

为 B3 已成功生成的 workspace 增加一个独立的、显式授权的 Execution Job，按
`install → build → loopback preview → Playwright/axe/visual` 顺序推进，并持久化每一步
的安全摘要、预算消耗和可恢复状态。B3 的源码生成 Job 不获得执行权限。

## 决策与边界

- Execution Job 必须 pin 成功的 `ProductGenerationJob` revision；workspace manifest、源文件
  hash、固定 package 依赖和 allowlisted scripts 在执行前复核。
- 只使用参数数组启动 `npm`/`npx`，不使用 shell；环境只保留运行 Node 所需的最小系统变量，
  不注入 Secret。安装允许固定模板依赖，运行时仅 loopback；本地 runner 不是容器或远程
  多租户隔离，CPU/内存/网络强隔离仍是后续部署决策。
- 默认一次尝试、180 秒、256 KiB 输出、4 成本单位；失败只持久化固定错误码/摘要，不保存
  任意命令输出。执行 Job 与生成 Job 分开持久化、幂等和重试。
- 生成模板补齐固定版本的 TypeScript 类型、axe、preview script 和 Playwright config；浏览器
  用例覆盖启动、Continue、Stop/error 状态、critical/serious axe 和截图产物。截图是可审查产物，
  不是已批准的视觉基线回归；截图/构建目录
  仍是软件验证材料，不是现实用户结果证据。

## 验收证据

- `ProductExecutionJob`、预算/沙箱/步骤模型、SQLite/InMemory adapter 和 `/execution-jobs` API。
- B4 fake-runner 测试覆盖独立执行权限、四步顺序、幂等、安全错误摘要、输出上限和 workspace
  篡改拒绝；B3 生成测试继续证明源码生成本身不执行代码。
- `pytest -q`、前端 Vitest、TypeScript/Vite build 和 OpenAPI drift 通过。

## 遗留项

- 当前 runner 是本机 allowlisted subprocess；真正的 OS/container CPU、内存、磁盘与网络隔离、
  多租户 Secret 策略和远程 worker 尚未批准。
- 浏览器二进制安装由环境 Gate 负责，Job 不自动下载浏览器；跨浏览器、移动和视觉基线比较仍待
  真实任务反馈后决定。
- 构建/浏览器成功只表示软件验证通过，不提升 Outcome Contract 的现实证据等级。
