# Iteration：Product Studio 开发台账初始化

- 日期：2026-09-20
- 状态：Closed
- 路线图工作包：A0
- 类型：Documentation / project governance

## 目标

为长期 Product Studio 实施建立一个独立、可持续维护的开发文档目录，使后续工作能够同时保存当前事实、未来计划、关键决策和逐步演变历史。

## 基线

- North Star 已定义产品方向、技术路线、第一条数字产品纵向切片和 Phase A–E。
- 仓库已有大量 ADR、旧实施计划、Python 领域内核、CLI/MCP 和 406 项通过测试。
- 原有文档没有一个面向新 Product Studio 主线的单一开发入口，也没有统一的批次记录协议。
- 工作树中 North Star 与 README 等已有用户改动；本次不覆盖这些文件。

## 范围

- 新建 `docs/product-studio/`；
- 建立目录入口和文档权威边界；
- 保存当前实现/证据快照；
- 将 Phase A–E 转成带依赖和退出门槛的路线图；
- 建立决策登记册、追加式演变日志和 Phase A 工作流；
- 提供后续 iteration 模板。

## 非目标

- 不修改 North Star、既有计划、ADR 或 README；
- 不新增领域模型、API、前端或依赖；
- 不选择第一条纵向切片的具体用户问题；
- 不提高任何现有案例的证据等级。

## 实施结果

新增以下项目记忆层：

1. `README.md`：入口、权威来源、维护协议和防漂移规则；
2. `CURRENT_STATE.md`：已验证能力、Product Studio 差距、证据边界与下一触发点；
3. `ROADMAP.md`：Phase A–E、A0–A5 工作包和明确退出门槛；
4. `DECISION_REGISTER.md`：已接受决策、相关 ADR 和 9 个待决问题；
5. `EVOLUTION_LOG.md`：从本次开始的追加式项目时间线；
6. `workstreams/phase-a-foundation.md`：Phase A 依赖、护栏、验收场景和完成定义；
7. `templates/iteration-record.md`：后续实现批次的统一记录格式。

## 验证

- 执行：`pytest -q`
- 结果：406 passed、2 skipped、1 warning
- 用时：20.16 秒
- warning：`ExperienceHypothesis.construct` 遮蔽父类 `FrozenModel` 属性；与本次文档改动无关，记录为已知基线。
- 文档检查：确认所有新增相对链接的目标存在，且本次只新增 `docs/product-studio/` 下文件。

## 决策与理由

- 使用“可变 CURRENT_STATE + 追加式 EVOLUTION_LOG + 关闭后稳定的 iteration”三层记录方式：既方便接手，又保留历史。
- 继续使用 `docs/adr/` 作为长期决策权威来源，避免新目录产生第二套 ADR。
- 不预建大量空目录；架构、运维等内容在出现首个真实文档时再创建。
- 路线图以退出门槛而非完成百分比推进，符合探索型产品研发的事实边界。

## 遗留项

- PS-O001：首条纵向切片的具体用户与现实问题未决定；Phase B 前必须关闭。
- PS-O002/PS-O003：上位四对象 schema 与人工确认边界未决定；是 A1 的核心工作。
- 既有 ADR 出现重复编号 `0059`；本次只记录，不重命名历史文件。
- Pydantic 字段遮蔽 warning 尚未处理。

## 下一最小工作包

A1：先写四个上位对象的领域 ADR 和状态转换，再以失败路径/不变量测试驱动最小 Pydantic 快照与命令。不要在 A1 同时引入 FastAPI 或 React。
