# Binance BTC/ETH 1D Crisis Partial-Profit Runner

- family：`Binance-1D-BTCETH-Crisis-Partial-Profit-Runner`
- short id：`BIN-1D-BE-CPPR`
- 状态：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 当前版本：无
- 机制：冻结 COST control + 早期单次 partial profit bank + 剩余 runner
- 目标：development 成本后 `>=20x`、ordered `1h` MDD `<=20%`

本 family 只改变一个机制：`1ATR/20%/1d` 信号次日open部分平仓一次，剩余数量继续原shadow/crisis状态机。fraction以外不搜索。

P0 growth `25%`为`16.4626x/-31.87%`，risk `75%`为`6.6693x/-29.25%`；三fraction均失败，audit/prospective未读取。

阅读顺序：[P0冻结合同](specs/binance-1d-be-cppr-p0-contract-2026-08-12.md) → [P0裁决](diagnostics/binance-1d-be-cppr-p0-2026-08-12.md) → [主账](binance-1d-be-cppr-core-ledger.md) → [决策日志](decision-log.md)。
