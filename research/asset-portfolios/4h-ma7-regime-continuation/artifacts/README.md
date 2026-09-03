# Artifacts — Binance-4H-MA7-Regime-Continuation

本目录保存 `BIN-4H-MA7-RC` P0 无条件延续性 kill test 的可复现机器证据。P0 是 diagnostic-only observation，不登记版本、不生成 runner / live spec。

## Frozen Inputs

- [binance_4h_ma7_rc_p0_dataset_manifest_2026-09-02.json](binance_4h_ma7_rc_p0_dataset_manifest_2026-09-02.json)：pre-outcome 输入数据 manifest，SHA256 `c11074a7a064db42c0a53214e0756f106388c14e683376bc0fcdfb56d94ffd7e`。
- [../configs/binance-4h-ma7-regime-continuation-p0.json](../configs/binance-4h-ma7-regime-continuation-p0.json)：P0R2 冻结配置，SHA256 `eb62108271cf1d22992fb53c0c1a7438d605581d96cb079d75b0579143c84642`；P0R1 hash `afdac0134562709dd52b1951c4b91f1d36e185028db3f0a328e18d4f2997da0d` 在读取 outcome 前因 funding 名义时间归一语义修订而 superseded。

## P0 Outputs

以下产物由 [../scripts/research_binance_4h_ma7_regime_continuation_p0.py](../scripts/research_binance_4h_ma7_regime_continuation_p0.py) 按冻结配置生成，并各自带 `.sha256` sidecar：

- [binance_4h_ma7_rc_p0_data_audit_2026-09-02.json](binance_4h_ma7_rc_p0_data_audit_2026-09-02.json)
- [binance_4h_ma7_rc_p0_universe_summary_2026-09-02.csv](binance_4h_ma7_rc_p0_universe_summary_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_events_2026-09-02.parquet](binance_4h_ma7_rc_p0_events_2026-09-02.parquet)
- [binance_4h_ma7_rc_p0_metrics_2026-09-02.csv](binance_4h_ma7_rc_p0_metrics_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_first_hit_2026-09-02.csv](binance_4h_ma7_rc_p0_first_hit_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_horizon_returns_2026-09-02.csv](binance_4h_ma7_rc_p0_horizon_returns_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_survival_2026-09-02.csv](binance_4h_ma7_rc_p0_survival_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_yearly_2026-09-02.csv](binance_4h_ma7_rc_p0_yearly_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_symbol_concentration_2026-09-02.csv](binance_4h_ma7_rc_p0_symbol_concentration_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_phase_2026-09-02.csv](binance_4h_ma7_rc_p0_phase_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_controls_2026-09-02.csv](binance_4h_ma7_rc_p0_controls_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_recent_slices_2026-09-02.csv](binance_4h_ma7_rc_p0_recent_slices_2026-09-02.csv)
- [binance_4h_ma7_rc_p0_summary_2026-09-02.json](binance_4h_ma7_rc_p0_summary_2026-09-02.json)
