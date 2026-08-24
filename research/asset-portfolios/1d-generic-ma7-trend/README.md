# Binance-1D-Generic-MA7-Trend

- Full family name：`Binance-1D-Generic-MA7-Trend`
- Alias：`BIN-1D-GMA7T`
- 市场/周期：Binance USD-M crypto perpetual，UTC `1d` 信号 + 真实 `1h` 风险回放。
- 机制：从 HYPE V7.1 拆出的对称 `SMA7/ATR7 reclaim + slope + hysteresis + ATR protection`，统一参数、零单币调参；OAPP/RSI/PEHC/forced reversal 已移除。
- 防串线：这是跨资产独立家族，不是 `HYPE-1D-MA7-ABT-V7.2`，也不修改原 V7.1。
- 状态：`v0 explore / frozen research contract / not promoted / not live-ready`。
- 2026-08-18 裁决：最终 22 币中 `12/22` 净 Sharpe > 0，横截面中位 Sharpe `0.239`；equal-risk 组合净 Sharpe `0.582`、MDD `-25.11%`。存在弱迁移 core，但时间稳定性、short 与 stop 敏感性不支持 promotion。

入口：[主账](binance-1d-gma7t-core-ledger.md) · [决策记录](decision-log.md) · [v0规格](specs/binance-1d-generic-ma7-trend-v0-spec.md) · [Genericization audit](diagnostics/binance-1d-generic-ma7-trend-v0-genericization-audit-2026-08-18.md) · [最终报告](diagnostics/binance-1d-generic-ma7-trend-v0-top30-market-cap-backtest-2026-08-18.md) · [产物索引](artifacts/README.md)
