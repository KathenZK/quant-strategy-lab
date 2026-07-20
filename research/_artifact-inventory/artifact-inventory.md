# Artifacts 全仓清单

- 生成时间（UTC）：`2026-07-20T04:19:04+00:00`
- 口径：只读取路径、文件元数据与 artifacts 目录外 Markdown 的引用目标；不读取 artifacts 文件内容，不跟随符号链接。
- artifacts 根目录：37 个；家族/主题：37 个；文件：41583 个。
- 总大小：86.18 GiB；被 Markdown 精确引用：797 个（1.92%）。
- 逐文件机器明细见 [`artifact-inventory.json`](artifact-inventory.json)；本页不展开逐文件列表。

## 家族/主题汇总

| 家族/主题路径 | 文件数 | 总大小 | 最大文件 | 引用覆盖率 | 预算级别 |
| --- | ---: | ---: | --- | ---: | --- |
| `archive/research/hype-transfer` | 19 | 13.2 MiB | `archive/research/hype-transfer/artifacts/xmr_binance_futures_15m_3y_trade_mark_funding.parquet` (5.0 MiB) | 19/19 (100.0%) | `A-normal` |
| `research/asset-portfolios/15m-asset-specific-six-strategy-selector` | 101 | 108.0 MiB | `research/asset-portfolios/15m-asset-specific-six-strategy-selector/artifacts/as6s_v5_runner_signal_parity_fixture_2026-07-15.json` (52.8 MiB) | 66/101 (65.35%) | `B-review` |
| `research/asset-portfolios/15m-multi-indicator-intraday` | 5 | 31.0 MiB | `research/asset-portfolios/15m-multi-indicator-intraday/artifacts/binance_15m_mii_btc_eth_constrained_search_ranking_2026-06-30.csv` (28.1 MiB) | 4/5 (80.0%) | `A-normal` |
| `research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble` | 19 | 4.5 MiB | `research/asset-portfolios/1h-adaptive-regime-multi-asset-ensemble/artifacts/binance_1h_ar_mae_equity_2026-07-07.csv` (2.6 MiB) | 15/19 (78.95%) | `A-normal` |
| `research/asset-portfolios/1h-cross-sectional-lightgbm-selector` | 17180 | 38.05 GiB | `research/asset-portfolios/1h-cross-sectional-lightgbm-selector/artifacts/prefit_model_matrix/year=2025/data_0.parquet` (494.6 MiB) | 5/17180 (0.03%) | `C-externalize` |
| `research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator` | 23141 | 46.23 GiB | `research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/artifacts/multihorizon_factor_dataset/liquid_monthly/year_month=2025-10/data_0.parquet` (308.0 MiB) | 10/23141 (0.04%) | `C-externalize` |
| `research/asset-portfolios/1h-multi-leg-six-asset-selector` | 7 | 1.9 MiB | `research/asset-portfolios/1h-multi-leg-six-asset-selector/artifacts/binance_1h_ml6as_route_surface_2026-07-14.csv` (1000.6 KiB) | 7/7 (100.0%) | `A-normal` |
| `research/asset-portfolios/hype-cross-strategy-account` | 5 | 301.3 KiB | `research/asset-portfolios/hype-cross-strategy-account/artifacts/hype_pbtr_v621_mii_v13_shared_account_trades_2026-07-02.csv` (278.6 KiB) | 5/5 (100.0%) | `A-normal` |
| `research/asset-portfolios/mk7-multi-strategy-account` | 14 | 194.5 KiB | `research/asset-portfolios/mk7-multi-strategy-account/artifacts/mk7_v8_selected_trades_2026-07-13.csv` (110.6 KiB) | 12/14 (85.71%) | `A-normal` |
| `research/bnb/15m-adaptive-regime` | 7 | 3.8 MiB | `research/bnb/15m-adaptive-regime/artifacts/bnb_binance_15m_closed_klines_2y.parquet` (3.6 MiB) | 3/7 (42.86%) | `A-normal` |
| `research/bnb/1h-adaptive-regime` | 39 | 18.2 MiB | `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v3_prefit_exit_filter_tune_ensembles_2026-07-10.csv` (3.0 MiB) | 36/39 (92.31%) | `A-normal` |
| `research/btc/15m-ema-trend-breakout` | 10 | 1.7 MiB | `research/btc/15m-ema-trend-breakout/artifacts/btc_15m_v40_holdout_equity_2026-07-17.csv` (1.2 MiB) | 10/10 (100.0%) | `A-normal` |
| `research/btc/1h-adaptive-regime` | 52 | 66.8 MiB | `research/btc/1h-adaptive-regime/artifacts/btc_1h_ar_v3_minimal_micro_tune_grid_2026-07-07.csv` (32.9 MiB) | 25/52 (48.08%) | `A-normal` |
| `research/eth/1h-adaptive-regime` | 66 | 20.7 MiB | `research/eth/1h-adaptive-regime/artifacts/eth_1h_ar_v2_ablation_guided_tune_candidates_2026-07-06.csv` (3.0 MiB) | 12/66 (18.18%) | `A-normal` |
| `research/hype/15m-candle-count-reversal` | 29 | 514.1 KiB | `research/hype/15m-candle-count-reversal/artifacts/hype_cc_v35_replace_24h_with_adx_di_selected_trades_2026-07-15.csv` (96.4 KiB) | 27/29 (93.1%) | `A-normal` |
| `research/hype/15m-ema-crossover` | 21 | 295.1 KiB | `research/hype/15m-ema-crossover/artifacts/hype_v17_1_full_ablation.json` (120.2 KiB) | 12/21 (57.14%) | `A-normal` |
| `research/hype/15m-ema-trend-breakout` | 139 | 381.5 MiB | `research/hype/15m-ema-trend-breakout/artifacts/hype_ema_tb_v35_staged_early_entry_equity_2026-07-17.csv` (60.1 MiB) | 131/139 (94.24%) | `B-review` |
| `research/hype/15m-factor-ml` | 188 | 132.1 MiB | `research/hype/15m-factor-ml/artifacts/hype_15m_factor_dataset.parquet` (58.9 MiB) | 21/188 (11.17%) | `B-review` |
| `research/hype/15m-multi-horizon-ema-forecast` | 4 | 53.2 MiB | `research/hype/15m-multi-horizon-ema-forecast/artifacts/hype-15m-mhef-baseline-2026-07-14-paths.csv` (47.2 MiB) | 4/4 (100.0%) | `A-normal` |
| `research/hype/15m-multi-indicator-intraday` | 108 | 27.1 MiB | `research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_clean_evolution_ranking_2026-06-29.csv` (10.1 MiB) | 107/108 (99.07%) | `A-normal` |
| `research/hype/15m-pullback-trail` | 13 | 43.7 MiB | `research/hype/15m-pullback-trail/artifacts/hype_15m_pbtr_bracket_search_prescreen_2026-06-30.csv` (10.5 MiB) | 12/13 (92.31%) | `A-normal` |
| `research/hype/15m-riptide` | 4 | 278.7 KiB | `research/hype/15m-riptide/artifacts/hype_15m_riptide_v13_cache_audit_trades_2026-06-30.csv` (252.2 KiB) | 3/4 (75.0%) | `A-normal` |
| `research/hype/15m-trend-breakout-multi-indicator-ensemble` | 17 | 27.9 MiB | `research/hype/15m-trend-breakout-multi-indicator-ensemble/artifacts/hype_15m_tb_mii_ensemble_backtest_v39_2026-07-08_equity.csv` (8.8 MiB) | 16/17 (94.12%) | `A-normal` |
| `research/hype/1d-multi-horizon-ema-forecast` | 4 | 279.7 KiB | `research/hype/1d-multi-horizon-ema-forecast/artifacts/hype-1d-mhef-classic-ewmac-2026-07-14-paths.csv` (224.2 KiB) | 4/4 (100.0%) | `A-normal` |
| `research/hype/1h-adaptive-regime` | 64 | 147.1 MiB | `research/hype/1h-adaptive-regime/artifacts/hype_1h_ar_v2_di_coordinate_2026-07-02.csv` (57.3 MiB) | 12/64 (18.75%) | `B-review` |
| `research/hype/1h-multi-horizon-ema-forecast` | 4 | 13.0 MiB | `research/hype/1h-multi-horizon-ema-forecast/artifacts/hype-1h-mhef-baseline-2026-07-14-paths.csv` (11.5 MiB) | 4/4 (100.0%) | `A-normal` |
| `research/hype/30m-keltner-breakout-retest` | 10 | 696.5 KiB | `research/hype/30m-keltner-breakout-retest/artifacts/hype_30m_keltner_breakout_retest_search_2026-07-17.csv` (376.8 KiB) | 10/10 (100.0%) | `A-normal` |
| `research/hype/30m-keltner-trend-breakout` | 68 | 10.7 MiB | `research/hype/30m-keltner-trend-breakout/artifacts/hype_30m_keltner_trend_breakout_v3_trade_paths_2026-07-13.html` (4.0 MiB) | 61/68 (89.71%) | `A-normal` |
| `research/hype/5m-micro-scalp` | 44 | 245.5 MiB | `research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_simplified_combo_summary_2026-06-30.csv` (109.0 MiB) | 36/44 (81.82%) | `B-review` |
| `research/hype/5m-pullback-trail` | 52 | 555.0 MiB | `research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_short_search_summary_2026-06-27.csv` (335.0 MiB) | 50/52 (96.15%) | `C-externalize` |
| `research/hype/6h-rs4-regime-switch` | 8 | 1010.9 KiB | `research/hype/6h-rs4-regime-switch/artifacts/hype_6h_rs4_parameter_slices_2026-06-28.csv` (438.3 KiB) | 8/8 (100.0%) | `A-normal` |
| `research/mu` | 17 | 1.6 MiB | `research/mu/artifacts/mu_binance_polygon_15m_aligned.csv` (720.9 KiB) | 16/17 (94.12%) | `A-normal` |
| `research/sol/1h-adaptive-regime` | 36 | 9.3 MiB | `research/sol/1h-adaptive-regime/artifacts/sol_1h_ar_v1_tune_strategies_2026-07-03.csv` (1.4 MiB) | 12/36 (33.33%) | `A-normal` |
| `research/sol/1h-pullback-bracket` | 5 | 276.6 KiB | `research/sol/1h-pullback-bracket/artifacts/sol_1h_pullback_bracket_search_2026-07-13.json` (163.9 KiB) | 1/5 (20.0%) | `A-normal` |
| `research/sol/1h-volatility-compression-breakout` | 8 | 3.2 MiB | `research/sol/1h-volatility-compression-breakout/artifacts/sol_1h_vcb_search_ranking_2026-07-13.csv` (1.9 MiB) | 2/8 (25.0%) | `A-normal` |
| `research/sol/4h-rs4-regime-switch` | 7 | 854.3 KiB | `research/sol/4h-rs4-regime-switch/artifacts/sol_4h_rs4_search_ranking_2026-07-13.csv` (433.5 KiB) | 1/7 (14.29%) | `A-normal` |
| `research/trx/1h-adaptive-regime` | 68 | 16.8 MiB | `research/trx/1h-adaptive-regime/artifacts/trx_1h_ar_v3_clean_tune_candidates_2026-07-07.csv` (3.2 MiB) | 18/68 (26.47%) | `A-normal` |

## 解释限制

- “被引用”仅表示 artifacts 目录外 Markdown 对具体文件的精确链接或路径引用；目录级链接、代码中的读取、动态拼接路径不计入。
- 保留类别是基于路径、后缀、大小与引用状态的治理提示，不是删除授权。
- 本清单不证明产物正确、可复现或仍被运行时代码使用。
