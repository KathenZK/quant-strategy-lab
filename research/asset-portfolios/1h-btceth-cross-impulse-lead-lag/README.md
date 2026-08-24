# Binance BTC/ETH 1H Cross-Impulse Lead-Lag

- family：`Binance-1H-BTCETH-Cross-Impulse-Lead-Lag`
- short id：`BIN-1H-BE-CILL`
- 状态：`explore / research line closed / HARD-GATE-FAILED / not promoted / not live-ready`
- 当前版本：无
- 机制：一币出现波动归一化小时冲击时，以另一币为 follower 做同向 catch-up
- 风险：任一时点仅一个 `1x` 固定数量仓位；不做风险缩放
- 目标：development `>=20x`、ordered `1h` MDD `<=20%`，再进入唯一候选审计

阅读顺序：[P0 合同](specs/binance-1h-be-cill-p0-contract-2026-08-12.md) → [主账](binance-1h-be-cill-core-ledger.md) → [决策日志](decision-log.md)。

本家族不是 MA7/RCR/LRMR 的版本；它测试跨资产信息传导而非日线趋势或价差均值回归。P0 最高仅 `1.2920x/-21.78%`，zero-cost gross `1.4943x`，当前研究线已关闭。
