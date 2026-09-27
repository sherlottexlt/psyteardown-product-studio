# Iteration：最近工作包记录格式与状态语义校正

- 日期：2026-09-26
- 状态：Closed
- 路线图工作包：Product Studio 台账治理
- 类型：Documentation / Governance

> 后续范围校正：2026-09-26 的 [`C1 负责人自试与非参与者演练 Gate 范围校正`](2026-09-26-c1-self-pilot-scope-correction.md) 已替代本记录中“人工演练与负责人发布 Gate”的下一步措辞；当前以自主持 N=1 真实试用为下一步。

## 目标

复核最近 C0、C1、C2、C3 和 Phase B Exit 记录，消除生命周期状态、验证结果和历史“下一步”文字混用造成的歧义；不改写已经发生的实现、测试或真实运行事实。

## 基线

- `templates/iteration-record.md` 已规定 `Planned | Active | Paused | Closed | Superseded`，但 C0/C2/C3 使用了 `done`，C3 正文还保留了 R1/R2/R3 阶段性结论，Phase B Exit 的顶部状态曾为 `in progress`，与入口文档的关闭结论冲突。
- 当前代码已经包含 C1 Product-side backend/API、主持面板和确定性 UI 测试；C1 没有真实参与者数据。
- `CURRENT_STATE.md` 与 `ROADMAP.md` 是项目当前事实入口，不能由历史 iteration 中较早的“下一步”覆盖。

## 范围

- 在 `README.md` 增加工作包记录的统一阅读和新增规则。
- 在入口文档中明确当前统一状态：Phase B、C0、C2、C3 已关闭；C1 Active，软件边界已实现但真实试用尚未开始。
- 保留关闭记录中的原始阶段性文字，通过本记录解释其适用范围，而不是静默删除历史。
- 将 C1 当前记录补充为 backend/API/UI 已实现，并把下一步收敛为 C1 主持面板之后的首位负责人自试与 review Gate。

## 非目标

- 不把 C1 确定性测试升级为真实结果证据。
- 不重新判定 C3 的 R1/R2/R3 失败样本，也不把 R4 10/10 扩大解释为生产级稳定性。
- 不修改旧 ADR 的适用范围，不新增跨域存储或治理决策。
- 不为了格式统一重写所有早期 iteration 的正文。

## 变更清单

| 区域 | 变更 | 证据 |
|---|---|---|
| 台账入口 | 增加统一状态语义、历史纠错和当前状态解释 | `docs/product-studio/README.md` |
| 当前事实 | 将 C1 从“仅 backend/待主持面板”同步为 backend/API/UI 已实现，保留未招募边界 | `docs/product-studio/CURRENT_STATE.md` |
| 路线图 | 将 C1 下一步改为负责人自试、reviewer 分离和文案/访问者/外部备份审阅；C3 描述明确为已关闭 | `docs/product-studio/ROADMAP.md` |
| C1 记录 | 补充主持面板、非成功路径输入、单条 review 与 UI 验证 | `iterations/2026-09-26-c1-outcome-observation-intake.md`、`studio/src/views/C1Panel.test.tsx` |

## 决策与偏差

- 旧记录顶部的 `done`、`verified`、`blocked`、`decision required` 不追溯替换，以免把历史阶段混成新的事实；新记录顶部只使用模板生命周期状态。
- `CURRENT_STATE.md`/`ROADMAP.md` 当前统一解释优先于已关闭记录的旧“下一步”段落；每次历史纠错必须单独留痕。
- 本批没有改变 PS-O022、PS-O023 或 PS-O024，也没有提升任何 Evidence 等级。

## 验证

- `git diff --check` → passed。
- `npm test -- --run src/views/C1Panel.test.tsx` → 2 passed。
- `npm run build` → passed；OpenAPI/generated frontend types remain generated from the current API.
- 现实证据边界：本批只校正台账和软件准备状态，不能证明真实参与者试用、同意签批或现实结果。

## 遗留项与风险

- Phase B Exit 原记录的历史“下一步”文字仍保留；顶部生命周期已校正为 `Closed`，具名审查附件缺口在记录中明确，不再把它当作未关闭的 Phase B 工作包。
- C0/C2/C3 历史记录中仍有多个阶段性 `状态` 行；后续新记录不得继续复制该写法。
- C1 不需要独立非参与者演练；下一步是负责人本地自试、具名且与 host 分离的 reviewer，以及对实际同意/数据处理说明的确认。

## 收尾同步

- [x] `CURRENT_STATE.md`
- [x] `ROADMAP.md`
- [x] `DECISION_REGISTER.md`（无新增决策）
- [x] `EVOLUTION_LOG.md`（追加本次校正摘要）
- [x] `README.md`

## 下一最小工作包

`C1 负责人本地自试与独立人工 review`：负责人直接完成一次 N=1 真实任务观察；随后由分离的 reviewer 审阅，或明确保留为未 review observation。
