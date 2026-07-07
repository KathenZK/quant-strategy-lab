# 策略状态术语表与状态机

本文件是全仓库策略版本状态词的唯一定义来源。core ledger、README、diagnostics、live specs 引用状态词时必须使用本表中的标签；发明新状态词前先更新本文件。

## 状态机总览

```text
探索搜索（无版本号）
  │ 用户要求登记 Vx
  ▼
registered diagnostic（diagnostic baseline / diagnostic observation）
  │ 满足 paper-audit 准入
  ▼
paper-audit observation
  │ 写出 runner 交接规格（live-specs/，遵守 lab-runner-handoff 规则）
  ▼
runner implementation target
  │ quant-runner 实现完成 + 指标对拍通过 + live-executable 审计通过
  ▼
dry-run（forward-tracking 开始）
  │ forward 证据达标
  ▼
小额 live
  │ forward 证据持续达标 + 运维审计完成
  ▼
live

任何阶段都可以终结为：NO-GO（终态，可因新证据重开）
```

`candidate`、`dry-run`、`handoff`、`live` 属于 promotion 状态；进入任何 promotion 状态前必须完成 live-executable 审计（见 `.cursor/rules/live-executable-strategy-research.mdc` 与 `.cursor/rules/lab-runner-handoff.mdc`）。本仓库不再定义额外的模拟盘阶段；模拟盘/仿真观察统一称为 `dry-run`，真实下单但小额运行归入 `live` 并在证据中注明 notional。

## 研究侧状态（未 promotion）

| 状态标签 | 含义 | 准入条件 | 不代表什么 |
| --- | --- | --- | --- |
| `exploratory / no version` | 搜索、诊断进行中，未登记任何版本 | 无 | 不可被引用为"策略" |
| `diagnostic baseline` | 用户要求登记的冻结基线版本，作为后续对比锚点 | 用户明确要求登记；core ledger 已更新版本表、参数、证据链接 | 不代表策略可行，NO-GO 家族也可以有 baseline |
| `diagnostic observation` | 基线之外登记的观察版本（微调、clean 化、缩放等） | 同上；须写明与 parent 版本的关系 | 同上 |
| `clean-equivalent observation` | 与 parent 版本逐笔等价、只精简参数面的登记版本 | 逐笔等价证据（trade signature 一致） | 不提供任何新增收益证据 |
| `paper-audit observation` / `paper-audit candidate` | 允许进入逐笔路径、订单维护、restart 等 paper 审计的观察版本 | 全参数消融或邻域稳健性完成；分片回测无执行不可能性；成本口径明确 | 不是 candidate，不可写 runner 规格前跳过审计 |
| `forward-test required` | 版本状态依赖尚不存在的 forward 证据 | 出现在 core ledger 中时，必须由 `forward-tracking/` 下的报告满足，口头描述不算 | 不代表已批准 dry-run |
| `NO-GO` | 该版本或家族在当前证据下不可行（终态） | 记录否决证据与原因 | 不可被重新包装为 candidate，除非有新证据并在 decision log 说明 |

通用后缀 `not promoted / not live-ready` 可以附加在任何研究侧状态后，表示未进入 promotion 序列。

## Promotion 侧状态

| 状态标签 | 含义 | 准入条件 |
| --- | --- | --- |
| `runner implementation target` | 已写出 runner 交接规格，等待/正在 quant-runner 实现；策略未启用 | 满足 `lab-runner-handoff.mdc` 的交接规格必备字段；core ledger 链接该规格 |
| `dry-run` | 在 quant-runner 以 dry-run 模式运行，不下真实订单 | live-executable 审计通过；指标对拍通过；`forward-tracking/` 目录建立 |
| `handoff` / `交接版本` | 规格与实现移交给人/其他系统维护 | 双向链接的 SPEC 齐备；参数一致性验证记录在案 |
| `live` | 真实资金运行（含小额） | dry-run forward 证据达标；资金费、盘口滑点、订单失败处理已审计；decision log 记录批准；小额运行必须注明 notional 与风险上限 |

## 使用规则

- 状态词必须与完整 family name + 版本号一起出现，例如 `HYPE-15M-MII-V1.3：runner implementation target / not live-ready`。
- 一个版本同一时刻只有一个主状态；可以叠加说明性后缀（如 `not live-ready`），不可同时挂两个主状态。
- 状态迁移（升级或降级）必须写入家族 `decision-log.md`，并同步更新 core ledger 与 asset/顶层索引中的状态标签。
- 回测再漂亮，跳过中间状态直接标记 promotion 状态属于违规；发现即降级并记录。
