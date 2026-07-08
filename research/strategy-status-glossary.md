# 策略状态术语表与状态机

本文件是全仓库策略版本状态词的唯一定义来源。core ledger、README、diagnostics、live specs 引用状态词时必须使用本表中的标签；发明新状态词前先更新本文件。

## 状态机总览

主状态只有下面这些；研究侧 3 个，promotion 侧 3 个，外加两个终态（`archived` 与 dry-run/live 后的 `NO-GO`）：

```text
explore（无版本号）
   │ 用户要求登记 Vx
   ▼
registered
   │ 消融/邻域稳健性完成，分片回测无执行不可能性，成本口径明确
   ▼
audit
   │ live-executable 审计通过 + 参数/状态机可被 runner 复现 + 写出交接规格
   ▼
live spec
   │ quant-runner 实现完成 + 指标对拍/smoke test 通过 + 进入 dry-run 时立即建立 forward-tracking/
   ▼
dry-run（模拟盘，forward-tracking 持续记录）
   │ forward 证据达标 + 运维审计（重启恢复、missing-bar fail-closed、kill switch）完成
   ▼
live（真实资金，小额起步，注明 notional 与风险上限）

dry-run 前任一阶段如果证据不足、回测失败、可执行性审计不通过，仍停留在当前主状态，并写 `not promoted / not live-ready`；
只有 dry-run 或 live 已运行并给出负面 forward/实盘证据后，才允许写 NO-GO。
研究线不再推进且无意重开时，任一阶段可以封存为 archived（终态，重开视同新研究线）。
```

promotion 状态只有 `live spec`、`dry-run`、`live` 三个；`handoff` 是可叠加在其上的移交标签，不是独立状态。进入任何 promotion 状态前必须完成 live-executable 审计（见 `.cursor/rules/live-executable-strategy-research.mdc` 与 `.cursor/rules/lab-runner-handoff.mdc`）。本仓库不定义额外的模拟盘阶段；模拟盘/仿真运行统一称为 `dry-run`，真实小额下单归入 `live`。

## 主状态定义

| 主状态 | 含义 | 准入条件 |
| --- | --- | --- |
| `explore` | 搜索、诊断进行中，未登记版本 | 无；不可被引用为"策略" |
| `registered` | 用户要求登记的冻结版本（基线或观察值），仅固定研究身份 | core ledger 已更新版本表、参数、证据链接；不代表策略可行 |
| `audit` | 研究侧审计策略是否可被真实订单时序和 runner 状态机复现 | 全参数消融或邻域稳健性完成；分片回测无执行不可能性；成本口径明确 |
| `live spec` | 已写出 runner 交接规格，等待/正在 quant-runner 实现；未启用 | live-executable 审计通过；参数/状态机可被 runner 复现；满足 `lab-runner-handoff.mdc` 交接规格必备字段；core ledger 链接该规格 |
| `dry-run` | 在 quant-runner 以 dry-run 模式运行（模拟盘，不下真实订单） | quant-runner 实现完成；指标对拍/smoke test 通过；进入 dry-run 的同一变更中建立 `forward-tracking/` |
| `live` | 真实资金运行（含小额） | dry-run forward 证据达标；资金费、盘口滑点、订单失败处理已审计；decision log 记录批准；小额运行注明 notional 与风险上限 |
| `NO-GO` | dry-run 或 live 后的最终否决状态 | 必须有 `forward-tracking/`、dry-run 对账或真实订单证据；记录否决原因，重开需新证据并写 decision log |
| `archived` | 研究线已封存：不再推进、不再复现，仅作历史证据保留 | decision log 记录封存原因；封存不需要负面 forward 证据；重开视同新研究线 |

`handoff` / "交接版本"：把规格与实现移交给人或其他系统维护的动作标签，可叠加在 `live spec` 及之后的主状态上；要求双向链接的 SPEC 齐备、参数一致性验证记录在案。`handoff` 不是独立主状态。

`candidate` 是已废弃的状态词：它曾同时被用于"研究候选"和"promotion 候选"，语义不清。现有文档遇到 `candidate` 时按上下文映射为 `registered`、`audit` 或 `live spec`；新文档一律不得使用。

## 修饰词（不是主状态）

以下词只能作为主状态的修饰或备注，单独出现不构成状态：

- `baseline` / `observation` / `clean-equivalent`：`registered` 的来源修饰——基线锚点、微调观察值、与 parent 逐笔等价的参数精简版（clean-equivalent 需 trade signature 一致证据，且不提供新增收益证据）。
- `forward-test required`：gate 备注，表示状态推进依赖 `forward-tracking/` 下尚不存在的报告；口头描述不算证据。
- `not promoted / not live-ready`：dry-run 前证据不足、回测失败、可执行性审计不通过、或暂不继续推进时使用的通用后缀；它不是最终否决，后续可以因新机制、新数据或新审计重开。

历史文档中的 `diagnostic baseline`、`diagnostic observation`、`clean-equivalent observation`、`audit observation`、`audit candidate` 等旧标签按上表映射理解（主状态 + 修饰词），不需要批量改写。历史文档中若在 dry-run 前使用了 `NO-GO`，按新口径理解为 `not promoted / not live-ready`，除非同一文档明确引用了 dry-run/live forward 证据。

## 使用规则

- 状态词必须与完整 family name + 版本号一起出现，例如 `HYPE-15M-MII-V1.3：dry-run / forward-test required`。
- 一个版本同一时刻只有一个主状态；可以叠加修饰词，不可同时挂两个主状态。
- 状态迁移（升级或降级）必须写入家族 `decision-log.md`，并同步更新 core ledger 与 asset/顶层索引中的状态标签。
- 回测再漂亮，跳过中间状态直接标记 promotion 状态属于违规；发现即降级并记录。
- dry-run 前不得给出 `NO-GO`；只能写 `not promoted / not live-ready`，并说明缺什么证据、什么新增证据可以重开。
