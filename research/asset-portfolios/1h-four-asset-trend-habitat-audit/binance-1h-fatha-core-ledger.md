# Binance-1H-Four-Asset-Trend-Habitat-Audit Core Ledger

## Family Identity

- Full family：`Binance-1H-Four-Asset-Trend-Habitat-Audit`
- Alias：`BIN-1H-FATHA`
- 市场：Binance USD-M perpetual；`HYPE/BTC/ETH/SOL`
- 周期：完整 `1h` 路径、日频锚点、未来 `3d/7d/14d`
- 机制：事后趋势 habitat + 事前 `7d/28d` 对齐 admission + 延迟捕获/回吐/成本诊断
- 边界：不产生订单，不继承任何单资产或组合策略的版本、参数、绩效和状态

## Current State

- 当前版本：无；只有预先冻结的跨资产趋势生态诊断。
- 状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 数据状态：四币 normalized/raw parity、连续性、关键空值、OHLCV、完整 `1h` 聚合与 funding 审计均通过。
- 证据状态：共同窗口、全历史、Long/Short、三 horizon、状态 episode、14 日块 bootstrap 和揭示后 onset-followthrough 均已完成。
- 研究结论：四币都有强趋势 habitat；HYPE 只在绝对振幅领先，归一化效率不领先，`7d/28d` admission 和早期价格位移延续均失败。BTC/ETH 存在资产/方向依赖的候选证据，但无策略版本。
- 下一门：如继续，另立分资产 admission family 并锁新 prospective OOS；不从本轮已揭示的 habitat 排名直接创建或 promotion Trend Campaign Engine。

## Version Rules

- Habitat 统计与 observation 不构成 registered strategy version。
- 改变强趋势定义、anchor、horizon、方向先验、成本、延迟或回吐规则都属于新冻结轮次。
- 只有后续独立策略合同、prospective OOS 与执行门禁通过后，才允许在新的策略家族登记 `V1`。

## Version Table

当前无 registered version。

## Shared Assumptions

- 源数据：标准数据湖 Binance `15m` OHLCV/funding，聚合完整 `1h`；源和聚合均 fail-closed。
- 比较：共同窗口为横向主证据；各资产全历史不得用于挑选共同阈值。
- 路径：UTC 每日 `00:00` anchor，未来 `72/168/336h`；过去 `7d/28d` 只使用 anchor 当时可见价格。
- 成本 hurdle：假设一次进出，fee `10bps/fill` + adverse slippage `4bps/fill`，另计实际 funding。
- 本轮无仓位、杠杆、策略收益或 promotion 结论。

## Evidence Map

- Spec：[初始研究合同](specs/binance-1h-fatha-initial-research-contract-2026-08-03.md)
- Diagnostics：[趋势生态丈量报告](diagnostics/binance-1h-fatha-trend-ecology-report-2026-08-03.md)
- Scripts / artifacts：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
