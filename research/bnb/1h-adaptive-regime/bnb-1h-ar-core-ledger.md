# BNB-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`BNB-1H-Adaptive-Regime`
- Short id：`BNB-1H-AR`
- Market：Binance USD-M Futures `BNBUSDT` perpetual
- Timeframe：`1h`
- 机制：多指标 regime-adaptive long/short 搜索，next-open 执行，ATR 风险控制

## 当前状态

`NO-GO / not promoted / not live-ready`。

`BNB-1H-Adaptive-Regime-V1` 已登记为 diagnostic observation baseline；`BNB-1H-Adaptive-Regime-V2` 已登记为 V1 的 clean-equivalent 版本（交易路径与 V1 完全一致）；`BNB-1H-Adaptive-Regime-V3` 已登记为 V2 消融引导微调版本。三者都不是 candidate、paper-live、dry-run、handoff 或 live 版本。

## 版本规则

- `V1` 只代表 `<=3x` 高胜率趋势/反转搜索中冻结的 `ema_pullback + wick_reject` 观察形态。
- `V2` 是 V1 的 clean 参数版本：no-op 字段固定为消融验证的 neutral 值，逐笔重放确认交易路径与 V1 相等；指标原样继承。
- `V3` 是 V2 的微调版本：保留 `ema_pullback + wick_reject` ensemble，但登记微调后的参数、指标和当前实际最大杠杆 `2.5x`；其 OOS 指标是 reused observation，不可作为 promotion 依据。
- 版本登记不改变 promotion 状态；locked OOS 未通过前不得标记为 candidate 或 live-ready。
- 后续如删除无用参数，只能基于交易路径完全不变的 no-op 参数，或另行登记 clean diagnostic version；不得用 OOS 后验优化替代重新冻结。

## 版本表

| Version | Status | Metrics | Evidence | Live readiness |
| --- | --- | --- | --- | --- |
| - | 未登记版本；1h family 已 NO-GO | `1,000,000` random + `500,000` neighbors 的 prefit hard-gate `0` 命中；冻结 primary full `4.20x / 73.53% / -31.90%`，locked OOS `0.28x / 42.86% / -31.90%` | `diagnostics/bnb-1h-adaptive-regime-search-2026-07-03.md` | hard gate 失败，不可实盘 |
| - | 2026-07-06 rerun；未登记版本；1h family 仍 NO-GO | `500,000` random + `250,000` neighbors，first/neighbors prefit hard-gate 均 `0`；冻结趋势+反转 ensemble `keltner_break+cci_reversal`，full `2.30x / 91.03% / -37.14%`，locked OOS `0.31x / 75.00% / -37.14%`，OOS trades `4` 低于最低 `12` | `diagnostics/bnb-1h-adaptive-regime-search-2026-07-06-rerun.md` | locked OOS 与 full hard gate 均失败，不可实盘 |
| - | 2026-07-06 rerun 3x cap 重放；未登记版本 | 将 rerun primary 的 `fixed_leverage/max_leverage` 约束到 `<=3.0` 后，full `1.95x / 91.03% / -28.30%`，locked OOS `0.44x / 75.00% / -28.30%`，仍超出 `20%` DD 上限 | `diagnostics/bnb-1h-ar-rerun-cap3-replay-2026-07-06.md` | 3x 仍未过 hard gate；后续 BNB 1h 搜索最大杠杆硬约束 `<=3x` |
| `BNB-1H-Adaptive-Regime-V1` | diagnostic observation baseline；not promoted | 冻结 `ema_pullback+wick_reject` ensemble，实际最大暴露 `2x`；prefit `2.20x / 87.04% / -18.66%`，但 locked OOS `0.64x / 68.42% / -22.86%`，full `1.87x / 84.25% / -22.86%`；全参数消融识别 `32` 个 no-op 字段并生成等价 clean spec | `specs/bnb-1h-ar-v1-parameter-spec-2026-07-06.md`；`specs/bnb-1h-ar-v1-clean-parameter-spec-2026-07-06.md`；`ablations/bnb-1h-ar-v1-full-parameter-ablation-2026-07-06.md`；`diagnostics/bnb-1h-ar-cap3-highwin-search-2026-07-06-cap3-highwin.md` | 样本内形态接近目标，但 OOS 胜率和回撤失败；clean spec 不改变不可实盘结论 |
| `BNB-1H-Adaptive-Regime-V2` | clean-equivalent diagnostic observation；not promoted | V1 clean 参数可执行版本；逐笔重放 trade signature 与 V1 相等（full `133` 笔含 warmup 段）；指标继承 V1：prefit `2.20x / 87.04% / -18.66%`，locked OOS `0.64x / 68.42% / -22.86%`，full `1.87x / 84.25% / -22.86%`；多窗口分片已落盘；V2 全参数消融 `122` rows：`27` 活动字段、`0` 可再删 | `specs/bnb-1h-ar-v2-parameter-spec-2026-07-07.md`；`notes/bnb-1h-ar-v2-multiwindow-backtest-2026-07-07.md`；`ablations/bnb-1h-ar-v2-full-parameter-ablation-2026-07-07.md`；`scripts/bnb_1h_ar_v2.py` | 与 V1 同路径，locked OOS 失败结论继承；不可实盘 |
| `BNB-1H-Adaptive-Regime-V3` | tuned diagnostic observation；not promoted | V2 消融引导微调登记版本；实际最大暴露 `2.5x`；prefit `3.37x / 89.42% / -18.24%`，reused locked OOS `1.22x / 81.25% / -15.53%`，full `2.94x / 88.33% / -18.24%`；主要变更：`ema_pullback` 改 `144` 慢 EMA、启用 trailing exit、杠杆 `2.5x`；`wick_reject` 提高 ADX/量价过滤并使用 `1.0x` | `specs/bnb-1h-ar-v3-parameter-spec-2026-07-07.md`；`notes/bnb-1h-ar-v2-micro-tune-2026-07-07.md` | OOS 属于 reused observation；未经过未读 forward 验证，不可 candidate / paper-live / dry-run / handoff / live |

当前没有 promotion 版本。BNB 后续 15m 研究属于 `BNB-15M-Adaptive-Regime`，不能作为本 1h family 的版本延续。
