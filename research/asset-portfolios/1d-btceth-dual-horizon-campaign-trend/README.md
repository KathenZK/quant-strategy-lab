# Binance BTC/ETH 1D Dual-Horizon Campaign Trend

- family：`Binance-1D-BTCETH-Dual-Horizon-Campaign-Trend`
- short id：`BIN-1D-BE-DHCT`
- 状态：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 当前版本：无
- 机制：BTC/ETH 共同慢周期 regime state + 快周期单资产 Donchian breakout + 单仓 profit protection
- 目标：development 成本后 `>=20x`、ordered `1h` MDD `<=20%`

本 family 是 CBCT 关账后的 materially new successor。核心身份是经过确认、可进入 neutral 的双资产慢周期 campaign state；不是扩大 CBCT 的 EMA、giveback 或 chandelier 参数。

P0 `108/108` 已完成；growth/risk 为同一路径 `15.3468x/-35.23%`，base pass `0`，audit/prospective 未读取。

阅读顺序：[P0 冻结合同](specs/binance-1d-be-dhct-p0-contract-2026-08-12.md) → [P0 裁决](diagnostics/binance-1d-be-dhct-p0-search-2026-08-12.md) → [主账](binance-1d-be-dhct-core-ledger.md) → [决策日志](decision-log.md)。
