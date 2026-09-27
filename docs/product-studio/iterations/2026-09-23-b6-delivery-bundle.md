# Iteration：B6 可追溯导出交付包

- 日期：2026-09-23
- 状态：Closed
- 路线图工作包：Phase B 第 9 步（导出与交付）
- 类型：Domain / Persistence / API / UI

## 目标

让一个已通过 B4 本地执行验证（含 B5 修复后重新验证）的 Web 产品，可以被导出为
内容寻址、字节确定的 zip 交付包：源码、构建物、验证产物、交付说明和未验证声明
都在包内，且交付记录不可变、可追溯到 execution / generation / contract revision。

## 基线

- B1–B5 已实现并验证；`ad22cd6` 提交了 B4/B5 代码；
- `pytest -q` 477 passed、2 skipped；前端 `npm test` 11 passed；`npm run build` 成功；
- North Star §8：交付成熟度与证据边界必须显式；CURRENT_STATE 中“导出与交付”为 `existing lower-level export only`。

## 范围

- 新增不可变 `ProductDeliveryBundle`（单 revision，创建后不再修改）与 `DeliveryBundleFile`；
- `ProductDeliveryBundleService`：同步创建（PS-H012），只接受当前 revision 为 `succeeded`
  且四个步骤均成功的 Execution Job；复核其 pin 的 generation 仍为同一 revision 且源码
  与 manifest 一致（复用 B4 完整性检查）；
- zip 布局：`source/`（manifest 声明文件）、`build/`（`dist/`）、`verification/`（`test-results/`
  与 `execution-summary.json`）、`DELIVERY.md`、`bundle-manifest.json`；固定时间戳、排序、权限；
- 同一 (project, execution revision, format) 幂等返回既有交付包；
- 预算：最多 256 文件、8 MiB；拒绝符号链接、路径穿越和凭据类文件名；
- InMemory/SQLite 持久化；`/delivery-bundles` 创建、列表、读取与 archive 下载（下载前复核 hash）；
- 工作台在最近执行成功时提供“导出交付包”入口，显示包 hash、文件数与未验证声明。

## 非目标

- 不做预览反馈（PS-O007）、部署、发布或签名；
- 不包含 `node_modules/`、`package-lock.json`（不在 generation manifest 中，无法复核）；
- 不把软件验证提升为 Outcome Evidence；包内 `outcome_evidence_level` 固定为 `none`；
- 不做视觉基线、跨浏览器或容器隔离。

## 验收条件

- Given 成功执行，When 导出，Then 产生 zip，其 sha256 与记录一致，包内文件与 `files` 清单一致；
- 重复导出返回同一 bundle；重新打包得到相同字节；
- 失败/排队执行、generation revision 变化、源码被篡改、缺少 `dist/index.html`、符号链接、超预算均被拒绝且不写记录；
- 修复 lineage 的交付包记录 `materialization_kind=repair`、父 generation 和 repair job；
- archive 被篡改后下载被拒绝；SQLite 重启可恢复记录；
- API/OpenAPI drift、前端单测与生产构建通过。

## 实施记录

1. 领域：`ProductDeliveryBundle`/`DeliveryBundleFile`（单 revision、insert-only）；B4 的 workspace 完整性检查抽成共享的 `validate_generated_workspace`，B4/B5/B6 使用同一规则。
2. 服务：`ProductDeliveryBundleService` 同步创建；确定性 zip（排序、1980-01-01 时间戳、0644）按 `<sha256>.zip` 原子写入 `exports/`；`DELIVERY.md` 不含 actor/时间/bundle id，保证同输入同字节。
3. 持久化与 API：SQLite `product_delivery_bundles`（PK + `(project_id, fingerprint)` 唯一约束）；`/delivery-bundles` 创建/列表/读取/`archive` 下载，下载前复核 hash，响应带 `X-Content-SHA256`。
4. UI：工作台在最近执行成功时显示“导出交付包”；仅当包 pin 的 execution revision 与当前执行一致时才展示下载链接、hash、来源与未验证声明。
5. **真实端到端验证暴露并修复了 3 个 B4 缺陷**（此前测试全部用 fake runner，从未真实跑通）：
   - `_safe_environment` 在 Windows 上按大小写敏感匹配 `SystemRoot`，而 `os.environ` 键为大写，导致 Node 无法初始化 CSPRNG、每次 install 崩溃 → 改为大小写不敏感；
   - user/global npm config 共用 `NUL`，npm 报 double-loading → 改为临时目录中两个独立空文件；
   - 预览只 `terminate()` 了 `npm.cmd` 包装进程，`node vite` 成为孤儿并占住 4173，下一次执行会**验证旧 workspace** → 独立进程组 + Windows `taskkill /T /F`、POSIX `killpg`；启动前若 4173 已被占用则返回 `preview_port_busy`，不再验证他人进程；
6. 同时发现完整性检查不容忍真实构建副产物：`tsc -b` 写入的 `tsconfig.tsbuildinfo` 使 B4 重试、B5 build 失败修复与 B6 导出全部判为篡改；POSIX 上 `node_modules/.bin` 符号链接同样会被拒 → 只对源码范围做清单/符号链接检查，执行输出根目录由消费方（B6）各自复核。
7. 安装了 Playwright 1.55.1 对应的 Chromium headless shell（用户确认）；执行器本身仍不自动下载浏览器。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain | `ProductDeliveryBundle`、`DeliveryBundleFile`、B6 常量与固定未验证声明 | `src/psyteardown/product/models.py` |
| service | 导出、幂等、预算、凭据/符号链接拒绝、hash 复核下载 | `src/psyteardown/product/delivery.py`、`tests/product/test_delivery.py` |
| B4 修复 | Windows 环境、npm config、预览进程树、端口占用、构建副产物 | `src/psyteardown/product/execution.py`、`tests/product/test_execution.py`（新增 4 个回归测试） |
| persistence | `product_delivery_bundles` insert-only 表 | `src/psyteardown/product/sqlite.py` |
| api | `/delivery-bundles` 四个端点 + OpenAPI | `src/psyteardown/api/delivery_bundles.py`、`tests/api/test_delivery_bundles.py`、`studio/openapi.json` |
| ui | 导出入口、下载、未验证声明 | `studio/src/views/{WorkbenchView,ProjectStudio}.tsx`、`studio/src/views/WorkbenchView.test.tsx` |

## 决策与偏差

- 新增 PS-H012（同步不可变交付记录，而非 Job）；只允许已成功执行导出（用户选择）；不含 `package-lock.json`（不在 manifest 内，无法复核）。
- 偏差：本批原定不改 B4，但真实验证证明 B4 此前无法在本机跑通，属于必须修复的缺陷，已纳入并补测试。
- 包内 `DELIVERY.md` 的运行说明已按真实包解压后 `npm install` + `npm run build` 验证。

## 验证

- `pytest -q`：490 passed、3 skipped、2 warnings（新增 `test_delivery.py` 7、`test_delivery_bundles.py` 2、`test_execution.py` +4；Windows 上符号链接用例 skip）；
- `npm test`：15 passed；`npm run build` 成功（含 OpenAPI 重新生成）；Chromium E2E：2 passed；
- 真实链路（无 fake runner）：B3 生成 → B4 install 9.0s / build 4.2s / preview 13.2s / Playwright+axe 11.6s 全部成功 → B6 导出 19 文件、78,510 bytes（source 10、build 4、verification 3、notes 2）；执行后 4173 端口已释放；解压包后按 `DELIVERY.md` 在 `source/` 安装并构建成功。
- 证据边界：以上只证明本机覆盖范围内的软件行为；`outcome_evidence_level` 固定为 `none`。

## 数据与迁移

- 新表 `CREATE TABLE IF NOT EXISTS`，旧库打开即升级；无既有数据变更。archive 丢失时下载返回 409，可对同一执行重新导出（内容寻址、字节相同）。

## 遗留项与风险

- 预览端口固定为 4173，本机同时只能跑一个执行；并发执行需要动态端口；
- Windows 上若包装进程先于子进程退出，`taskkill /T` 无法按 PID 回收孤儿（当前 npm 包装会一直存活，未观察到）；
- 部署级 OS/container 隔离、视觉基线、跨浏览器、预览反馈（PS-O007）仍未做；交付包未签名。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`
- [x] `EVOLUTION_LOG.md`

## 下一最小工作包

B7 预览与反馈锚点：先关闭 PS-O007（反馈粒度与同意），再基于已导出的 build 提供工作台内嵌预览与页面/任务级反馈锚点。
