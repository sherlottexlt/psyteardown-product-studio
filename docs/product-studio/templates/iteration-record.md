# Iteration：<可验证工作包名称>

- 日期：YYYY-MM-DD
- 状态：Planned | Active | Paused | Closed | Superseded
- 路线图工作包：<ID>
- 类型：<one or more tags: Domain | Persistence | API | UI | Workflow | Validation | Operations | Documentation | Governance | Decision | Provider | Execution>

> 顶部“状态”只表示 iteration 生命周期。不要在这里写 `done`、`verified`、`blocked` 或 `decision required`；这些是验证结果、失败边界或待决事项，应放入“验证”“决策与偏差”或“遗留项与风险”。继续一个尚未关闭的工作包时保留 `Active` 并追加本批记录；已关闭后再继续则新建日期 iteration。

## 目标

用一两句话描述本批次结束后真实新增的用户或系统能力。

## 基线

- 开始前已经实现并验证的相关事实；
- 当前测试/迁移/运行基线；
- 相关 North Star、工作流和代码链接；旧 ADR 必须说明原适用范围。

## 范围

- 本次会改变的内容。

## 非目标

- 明确不会顺手扩张的内容。

## 验收条件

- 使用 Given/When/Then 或其他可复核形式；
- 同时覆盖关键成功路径和失败路径；
- 说明需要什么测试或现实证据。

## 实施记录

按发生顺序记录重要发现、范围变化和修复；不要复制完整代码 diff。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| domain/api/ui/etc. | <内容> | <文件、测试、迁移或产物链接> |

## 决策与偏差

- 本次新增的待决假设或真正批准的 ADR；引用旧 ADR 时说明是否仅作历史参考；
- 与原计划不同的地方、原因和影响；
- 临时假设及其失效/复审条件。

## 验证

- 命令：`<command>`
- 结果：<passed/failed/skipped/warnings>
- 未运行项目及原因：<none 或说明>
- 现实证据边界：说明这些检查能证明什么、不能证明什么。

## 数据与迁移

- schema/API/asset 兼容性；
- upgrade、rollback 和失败恢复；
- 不适用时写 `N/A`。

## 遗留项与风险

- 尚未解决的问题；
- 是否更新 `DECISION_REGISTER.md`；
- 是否改变现有证据等级或声称边界。

## 收尾同步

- [ ] `CURRENT_STATE.md`
- [ ] `ROADMAP.md`
- [ ] `DECISION_REGISTER.md`（如适用）
- [ ] `EVOLUTION_LOG.md`
- [ ] 用户/开发者入口文档（如适用）

## 下一最小工作包

写出可以独立验证、不会无界扩张的下一步。
