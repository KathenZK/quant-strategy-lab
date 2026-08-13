# Binance BTC/ETH 1D Cross-Breadth Channel Trend

- family：`Binance-1D-BTCETH-Cross-Breadth-Channel-Trend`
- short id：`BIN-1D-BE-CBCT`
- 状态：`research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`
- 当前版本：无
- 机制：候选资产 Donchian 突破 + 另一资产 EMA breadth 同向确认 + 单仓 chandelier/channel exit
- 仓位：初始 `1x` 固定数量，不做 risk scaling
- 目标：development `>=20x`、ordered `1h` MDD `<=20%`

P0 `2,808/2,808` 已完成，growth `13.2404x/-48.00%`，risk `1.6607x/-27.88%`。P1 `18/18` 浮盈保护中，growth 达 `21.2707x/-37.20%`、risk `4.4107x/-34.20%`，但 `0` soft-continue；research line 按冻结合同关闭，audit/prospective 未读取。

阅读顺序：[P0 合同](specs/binance-1d-be-cbct-p0-contract-2026-08-12.md) → [P0 裁决](diagnostics/binance-1d-be-cbct-p0-search-2026-08-12.md) → [P1 浮盈保护合同](specs/binance-1d-be-cbct-p1-profit-protection-contract-2026-08-12.md) → [P1 裁决](diagnostics/binance-1d-be-cbct-p1-profit-protection-2026-08-12.md) → [主账](binance-1d-be-cbct-core-ledger.md) → [决策日志](decision-log.md)。

本家族不是 Turtle 扩参、MA7/RCR/LRMR/CILL 的版本；cross-asset breadth 与真实小时 chandelier 是身份的一部分。
