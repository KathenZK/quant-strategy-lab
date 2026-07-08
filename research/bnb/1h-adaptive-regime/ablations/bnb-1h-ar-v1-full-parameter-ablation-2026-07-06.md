# BNB-1H-Adaptive-Regime-V1 全参数消融 - 2026-07-06

## 结论

`BNB-1H-Adaptive-Regime-V1` 的全参数消融完成。V1 仍是 `diagnostic observation / not promoted / not live-ready`；本报告只用于识别 no-op 参数和机制敏感参数，不用于 OOS 后验选参。

- Baseline prefit：`2.20x` / `261.15%` / `-18.66%` / `87.04%` / `108`。
- Baseline locked OOS：`0.64x` / `-10.67%` / `-22.86%` / `68.42%` / `19`。
- Baseline full：`1.87x` / `222.63%` / `-22.86%` / `84.25%` / `127`。
- Field ablation rows：`60`；可安全删除 no-op 参数：`32`。
- Clean spec：`specs/bnb-1h-ar-v1-clean-parameter-spec-2026-07-06.md`。该规格删除 no-op 参数但不改变交易路径，也不改变 `not promoted / not live-ready` 状态。

## 可从 clean spec 删除的 no-op 参数

- `ema_pullback`：`band_k`, `indicator_window`, `macd_fast`, `macd_signal`, `macd_slow`, `max_adx`, `max_aligned_funding_bps`, `max_atr_bps`, `max_leverage`, `risk_fraction`, `roc_threshold_bps`, `roc_window`, `threshold_high`, `threshold_low`, `trail_activation_atr`, `trail_atr`。
- `wick_reject`：`ema_fast`, `ema_htf`, `ema_slow`, `indicator_window`, `macd_fast`, `macd_signal`, `macd_slow`, `max_atr_bps`, `max_dist_ema_bps`, `max_leverage`, `pullback_atr`, `risk_fraction`, `roc_threshold_bps`, `roc_window`, `trail_activation_atr`, `trail_atr`。

## 改变交易路径但样本内不差的参数

这些变体不能直接作为 clean 版本采用，因为它们改变了交易路径；若要继续，应作为新搜索/新冻结版本处理，而不是用 OOS 后验选择。
- `ema_pullback.ema_slow`：prefit `2.30x / -14.87% / 87.16%`；full `2.03x / -14.87% / 85.16%`。
- `wick_reject.sl_atr`：prefit `2.24x / -18.21% / 87.96%`；full `1.88x / -24.08% / 84.92%`。

## Component removal

| Removed component | Prefit | Locked OOS | Full |
| --- | --- | --- | --- |
| `ema_pullback` | `1.13x / -6.64% / 92.73%` | `0.99x / -4.00% / 80.00%` | `1.11x / -6.64% / 90.77%` |
| `wick_reject` | `1.85x / -19.50% / 78.95%` | `0.72x / -18.23% / 60.00%` | `1.63x / -19.50% / 76.12%` |

## Clean spec 边界

可以删除的只包括交易路径完全不变的 no-op 字段。`entry_delay_bars`、执行成本、next-open 入场、stop-first 和 funding 口径不是可删参数。

## 产物

- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v1_full_ablation_2026-07-06.json`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v1_full_ablation_rows_2026-07-06.csv`
- `research/bnb/1h-adaptive-regime/artifacts/bnb_1h_ar_v1_full_ablation_fields_2026-07-06.csv`
