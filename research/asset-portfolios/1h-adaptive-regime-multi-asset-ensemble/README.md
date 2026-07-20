# Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble

- Full family name：`Binance-1H-Adaptive-Regime-Multi-Asset-Ensemble`
- Short id：`BIN-1H-AR-MAE`
- Market：Binance USD-M Futures perpetual，六个 symbol：`TRXUSDT`、`SOLUSDT`、`HYPEUSDT`、`ETHUSDT`、`BTCUSDT`、`BNBUSDT`
- Timeframe：`1h`

## 家族定义

本家族研究把六个单资产 `1h` adaptive-regime 家族的最新登记版本组合成跨资产组合：

- `TRX-1H-Adaptive-Regime-V3`
- `SOL-1H-Adaptive-Regime-V2`
- `HYPE-1H-Adaptive-Regime-V4`
- `ETH-1H-Adaptive-Regime-V3`
- `BTC-1H-Adaptive-Regime-V4`
- `BNB-1H-Adaptive-Regime-V3`

每个 sleeve 保持其家族冻结交易路径（信号、执行契约、成本、funding 全部不变）；组合层只做账户级持仓/资金规则，不做信号融合。这是跨资产组合研究线，隶属 `research/asset-portfolios/`，不改变任何成分家族的版本身份。

## 当前状态

- 当前版本：`BIN-1H-AR-MAE-V1`。
- 当前状态：`dry-run / not live-ready`；manifest 中 `six-asset-ensemble-dry-run` 已启用，live disabled。
- Runner：strict replay `371/371` parity PASS；持续 dry-run 与 strict replay 的 mark-price、cooldown 和 timeout 语义差异已登记，不能混作同一口径。
- 历史 pre-dry-run 研究发现：原始 V1 full DD `-21.43%` 穿破 `<20%` 门槛，账户 overlay 在成本压力下仍失败。这些是风险证据，不是当前 `NO-GO` 或禁止 dry-run 声明。
- 下一决策门：持续积累 runner-tracking 证据并完成 online open/close reconciliation；当前不得启用 live。

## 入口

- 主账：[binance-1h-ar-mae-core-ledger.md](binance-1h-ar-mae-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- V1 完整复现规格（给同事/AI）：[binance-1h-ar-mae-v1-full-reproduction-spec-2026-07-07.md](specs/binance-1h-ar-mae-v1-full-reproduction-spec-2026-07-07.md)
- V1 简版规格：[binance-1h-ar-mae-v1-single-position-spec-2026-07-07.md](specs/binance-1h-ar-mae-v1-single-position-spec-2026-07-07.md)
- 首次组合回测（等权 `1/6`）：[binance-1h-ar-mae-first-combination-backtest-2026-07-07.md](notes/binance-1h-ar-mae-first-combination-backtest-2026-07-07.md)
- V1 单仓先到先得回测：[binance-1h-ar-mae-single-position-backtest-2026-07-07.md](notes/binance-1h-ar-mae-single-position-backtest-2026-07-07.md)
- V1 风险覆盖层诊断：[binance-1h-ar-mae-v1-risk-overlay-diagnostics-2026-07-09.md](notes/binance-1h-ar-mae-v1-risk-overlay-diagnostics-2026-07-09.md)
- TRX MACD 尾部风险根因与全局 overlay：[binance-1h-ar-mae-v1-trx-tail-risk-optimization-2026-07-10.md](notes/binance-1h-ar-mae-v1-trx-tail-risk-optimization-2026-07-10.md)
- TRX MACD 定向尾部覆盖层：[binance-1h-ar-mae-v1-trx-targeted-tail-overlay-2026-07-10.md](notes/binance-1h-ar-mae-v1-trx-targeted-tail-overlay-2026-07-10.md)
- V1 每周交易统计：[binance-1h-ar-mae-v1-weekly-stats-2026-07-09.md](notes/binance-1h-ar-mae-v1-weekly-stats-2026-07-09.md)
- 复现脚本：`scripts/research_binance_1h_ar_multi_asset_ensemble_backtest.py`、`scripts/research_binance_1h_ar_mae_single_position_backtest.py`
- 产物：`artifacts/`
