# BNB-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`BNB-1H-Adaptive-Regime`
- Short id：`BNB-1H-AR`
- Market：Binance USD-M Futures `BNBUSDT` perpetual
- Timeframe：`1h`
- 机制：多指标 regime-adaptive long/short 搜索，next-open 执行，ATR 风险控制

## 当前状态

`NO-GO / not promoted / not live-ready`。

## 版本表

| Version | Status | Metrics | Evidence | Live readiness |
| --- | --- | --- | --- | --- |
| - | 未登记版本；1h family 已 NO-GO | `1,000,000` random + `500,000` neighbors 的 prefit hard-gate `0` 命中；冻结 primary full `4.20x / 73.53% / -31.90%`，locked OOS `0.28x / 42.86% / -31.90%` | `diagnostics/bnb-1h-adaptive-regime-search-2026-07-03.md` | hard gate 失败，不可实盘 |
| - | 2026-07-06 rerun；未登记版本；1h family 仍 NO-GO | `500,000` random + `250,000` neighbors，first/neighbors prefit hard-gate 均 `0`；冻结趋势+反转 ensemble `keltner_break+cci_reversal`，full `2.30x / 91.03% / -37.14%`，locked OOS `0.31x / 75.00% / -37.14%`，OOS trades `4` 低于最低 `12` | `diagnostics/bnb-1h-adaptive-regime-search-2026-07-06-rerun.md` | locked OOS 与 full hard gate 均失败，不可实盘 |
| - | 2026-07-06 rerun 3x cap 重放；未登记版本 | 将 rerun primary 的 `fixed_leverage/max_leverage` 约束到 `<=3.0` 后，full `1.95x / 91.03% / -28.30%`，locked OOS `0.44x / 75.00% / -28.30%`，仍超出 `20%` DD 上限 | `diagnostics/bnb-1h-ar-rerun-cap3-replay-2026-07-06.md` | 3x 仍未过 hard gate；后续 BNB 1h 搜索最大杠杆硬约束 `<=3x` |

两轮搜索均没有可登记版本。BNB 后续 15m 研究属于 `BNB-15M-Adaptive-Regime`，不能作为本 1h family 的版本延续。
