# Binance BTC/ETH 1D Crisis Profit-Exit Handoff Continuity

- family：`Binance-1D-BTCETH-Crisis-Profit-Exit-Handoff-Continuity`
- short id：`BIN-1D-BE-CPEHC`
- 状态：`explore / not promoted / not live-ready`
- 当前版本：无
- 机制：固定 crisis override + early full profit exit + 单次同方向 continuation handoff
- 目标：development 成本后 `>=20x`、ordered `1h` MDD `<=20%`

本 family 学习 HYPE 的“利润退出后状态连续性”方法，但不复制HYPE参数：退出阈值来自BTC/ETH P1风险前沿，handoff仅以该笔冻结favorable extreme为门槛。

阅读顺序：[P0冻结合同](specs/binance-1d-be-cpehc-p0-contract-2026-08-13.md) → [主账](binance-1d-be-cpehc-core-ledger.md) → [决策日志](decision-log.md)。
