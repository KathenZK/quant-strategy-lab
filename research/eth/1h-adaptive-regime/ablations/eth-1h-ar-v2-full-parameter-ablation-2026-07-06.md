# ETH-1H-Adaptive-Regime-V2 全参数消融 - 2026-07-06

## 结论

`ETH-1H-Adaptive-Regime-V2` 已覆盖两条腿全部 `29/29` 个 clean 参数槽，完成 one-at-a-time 全参数消融。reused holdout 与近期分片只作冻结后审计，不参与选参。

本轮 one-at-a-time 行数（含 baseline）为 `140`；prefit 严格改善行数 `2`；满足 train/validation/prefit `win>=80%`、DD `<20%` 且 prefit annual 高于 V2 的单字段行数 `0`。

## V2 基线

| Window | Annual / Return / DD / Win / Trades |
| --- | --- |
| `train` | `3.8425x` / `314.94%` / `-15.02%` / `72.60%` / `73` |
| `validation` | `2.7855x` / `79.16%` / `-10.56%` / `75.00%` / `32` |
| `prefit` | `3.4333x` / `643.41%` / `-15.02%` / `73.33%` / `105` |
| `reused_holdout` | `0.4323x` / `-18.86%` / `-18.93%` / `50.00%` / `10` |
| `current_full` | `2.6071x` / `503.24%` / `-18.93%` / `71.30%` / `115` |

## 标准近期分片

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `0.0007x` / `-12.88%` / `-12.97%` / `0.00%` / `2` |
| `last_1m` | `0.3923x` / `-7.40%` / `-12.97%` / `60.00%` / `5` |
| `last_3m` | `0.4323x` / `-18.86%` / `-18.93%` / `50.00%` / `10` |
| `last_6m` | `1.1874x` / `8.88%` / `-18.93%` / `65.22%` / `23` |
| `last_1y` | `1.9568x` / `95.59%` / `-18.93%` / `70.37%` / `54` |

## 字段覆盖

| Component | Field | Baseline | Variants | Component Equal | Merged Equal | Strict Improve | High-Win Gate |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `bb_break` | `ema_htf` | `89.0` | `4` | `3` | `3` | `0` | `0` |
| `bb_break` | `indicator_window` | `32.0` | `5` | `0` | `0` | `0` | `0` |
| `bb_break` | `band_k` | `2.0` | `5` | `0` | `0` | `0` | `0` |
| `bb_break` | `roc_window` | `48.0` | `4` | `0` | `0` | `0` | `0` |
| `bb_break` | `min_adx` | `28.0` | `6` | `0` | `0` | `0` | `0` |
| `bb_break` | `min_rvol` | `2.5` | `5` | `0` | `0` | `0` | `0` |
| `bb_break` | `min_atr_bps` | `50.0` | `4` | `0` | `0` | `0` | `0` |
| `bb_break` | `min_dir_roc_bps` | `-200.0` | `6` | `1` | `1` | `0` | `0` |
| `bb_break` | `max_dist_ema_bps` | `10000.0` | `5` | `1` | `1` | `0` | `0` |
| `bb_break` | `max_aligned_funding_bps` | `10000.0` | `4` | `4` | `4` | `0` | `0` |
| `bb_break` | `tp_atr` | `3.0` | `5` | `0` | `0` | `0` | `0` |
| `bb_break` | `sl_atr` | `4.0` | `6` | `0` | `0` | `2` | `0` |
| `bb_break` | `max_hold_bars` | `48.0` | `5` | `0` | `0` | `0` | `0` |
| `bb_break` | `fixed_leverage` | `2.0` | `5` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `ema_htf` | `377.0` | `3` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `indicator_window` | `14.0` | `4` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `threshold_low` | `10.0` | `5` | `1` | `1` | `0` | `0` |
| `rsi_reversal` | `threshold_high` | `65.0` | `5` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `roc_window` | `6.0` | `4` | `4` | `4` | `0` | `0` |
| `rsi_reversal` | `min_adx` | `16.0` | `6` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `max_adx` | `100.0` | `4` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `min_atr_bps` | `100.0` | `5` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `min_dir_roc_bps` | `-10000.0` | `6` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `max_dist_ema_bps` | `1000.0` | `5` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `tp_atr` | `2.5` | `6` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `sl_atr` | `2.0` | `4` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `max_hold_bars` | `24.0` | `5` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `cooldown_bars` | `0.0` | `4` | `0` | `0` | `0` | `0` |
| `rsi_reversal` | `fixed_leverage` | `1.5` | `4` | `0` | `0` | `0` | `0` |

## 机器证据

- `artifacts/eth_1h_ar_v2_full_ablation_2026-07-06.json`
- `artifacts/eth_1h_ar_v2_full_ablation_rows_2026-07-06.csv`
- `artifacts/eth_1h_ar_v2_full_ablation_fields_2026-07-06.csv`
- `artifacts/eth_1h_ar_v2_slices_2026-07-06.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_full_ablation.py
```
