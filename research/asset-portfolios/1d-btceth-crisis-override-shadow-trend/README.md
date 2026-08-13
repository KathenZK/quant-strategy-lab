# Binance BTC/ETH 1D Crisis Override Shadow Trend

- family：`Binance-1D-BTCETH-Crisis-Override-Shadow-Trend`
- short id：`BIN-1D-BE-COST`
- 状态：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 当前版本：无
- 机制：冻结 CBCT-P1 shadow + 双资产慢周期危机状态 + 总 gross `1x` 等权 short basket override
- 目标：development 成本后 `>=20x`、ordered `1h` MDD `<=20%`

本 family 不扩 CBCT entry/exit 参数。危机状态是账户级互斥 override：暂停 shadow 单仓并替换为双 short basket；解除后只等待 fresh shadow entry。

P0 最佳 `EMA200/slope60/confirm3` 为 `23.1321x/-35.22%`，收益提高但风险、delay和集中度失败；audit/prospective未读取。

阅读顺序：[P0 冻结合同](specs/binance-1d-be-cost-p0-contract-2026-08-12.md) → [P0裁决](diagnostics/binance-1d-be-cost-p0-2026-08-12.md) → [主账](binance-1d-be-cost-core-ledger.md) → [决策日志](decision-log.md)。
