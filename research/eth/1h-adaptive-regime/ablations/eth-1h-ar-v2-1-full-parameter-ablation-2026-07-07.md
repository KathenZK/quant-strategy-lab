# ETH-1H-Adaptive-Regime-V2.1 全参数消融 - 2026-07-07

## 结论

本轮覆盖 `ETH-1H-Adaptive-Regime-V2.1` 两条腿全部 `29/29` 个 clean 参数槽，完成 one-at-a-time 全参数消融。判定规则：domain 内所有变体的 merged 逐笔路径都与 V2.1 完全相同的字段，视为无意义参数（`merged_path_inert_remove`），从后续 clean tuning surface 删除或硬编码；其余保留为 `active_tunable`。

分类结果：active tunable `27` 个（bb_break `12`、rsi_reversal `15`）；merged-path inert `2` 个。one-at-a-time 行数（含 baseline）`140`；相对 V2.1“收益更高、胜率更高、回撤更小”的严格改善行 `0`。

reused holdout 与近期分片只作冻结后审计，不参与删参或选参。

## V2.1 基线

| Window | Annual / Return / DD / Win / Trades |
| --- | --- |
| `train` | `3.7405x` / `303.31%` / `-14.98%` / `88.00%` / `25` |
| `validation` | `3.8699x` / `116.03%` / `-8.78%` / `100.00%` / `11` |
| `prefit` | `3.7853x` / `771.27%` / `-14.98%` / `91.67%` / `36` |
| `reused_holdout` | `0.7048x` / `-8.35%` / `-19.55%` / `50.00%` / `4` |
| `current_full` | `3.0277x` / `698.55%` / `-19.55%` / `87.50%` / `40` |

## 标准近期分片

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `2.1132x` / `6.34%` / `-1.47%` / `100.00%` / `1` |
| `last_3m` | `0.7048x` / `-8.35%` / `-19.55%` / `50.00%` / `4` |
| `last_6m` | `1.2291x` / `10.76%` / `-19.55%` / `71.43%` / `7` |
| `last_1y` | `2.7494x` / `174.75%` / `-19.55%` / `85.71%` / `21` |

## 字段分类

| Component | Field | Baseline | Classification | Variants | Component Equal | Merged Equal | Strict Improve |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `bb_break` | `ema_htf` | `55.0` | `merged_path_inert_remove` | `4` | `4` | `4` | `0` |
| `bb_break` | `indicator_window` | `32.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `band_k` | `2.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `roc_window` | `12.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `min_adx` | `36.0` | `active_tunable` | `6` | `0` | `0` | `0` |
| `bb_break` | `min_rvol` | `3.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `min_atr_bps` | `50.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `bb_break` | `min_dir_roc_bps` | `100.0` | `active_tunable` | `6` | `5` | `5` | `0` |
| `bb_break` | `max_dist_ema_bps` | `10000.0` | `active_tunable` | `5` | `1` | `1` | `0` |
| `bb_break` | `max_aligned_funding_bps` | `8.0` | `merged_path_inert_remove` | `4` | `4` | `4` | `0` |
| `bb_break` | `tp_atr` | `3.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `sl_atr` | `5.0` | `active_tunable` | `6` | `0` | `0` | `0` |
| `bb_break` | `max_hold_bars` | `48.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `bb_break` | `fixed_leverage` | `3.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `rsi_reversal` | `ema_htf` | `233.0` | `active_tunable` | `3` | `0` | `0` | `0` |
| `rsi_reversal` | `indicator_window` | `7.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `threshold_low` | `5.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `rsi_reversal` | `threshold_high` | `75.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `rsi_reversal` | `roc_window` | `6.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `min_adx` | `20.0` | `active_tunable` | `6` | `0` | `0` | `0` |
| `rsi_reversal` | `max_adx` | `45.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `min_atr_bps` | `125.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `rsi_reversal` | `min_dir_roc_bps` | `-300.0` | `active_tunable` | `6` | `0` | `0` | `0` |
| `rsi_reversal` | `max_dist_ema_bps` | `750.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `rsi_reversal` | `tp_atr` | `2.0` | `active_tunable` | `6` | `0` | `0` | `0` |
| `rsi_reversal` | `sl_atr` | `3.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `max_hold_bars` | `48.0` | `active_tunable` | `5` | `0` | `0` | `0` |
| `rsi_reversal` | `cooldown_bars` | `24.0` | `active_tunable` | `4` | `0` | `0` | `0` |
| `rsi_reversal` | `fixed_leverage` | `2.5` | `active_tunable` | `4` | `0` | `0` | `0` |

## 删参结论

- bb_break inert 字段：`['ema_htf', 'max_aligned_funding_bps']`。
- rsi_reversal inert 字段：`无`。
- inert 字段在 V2.1 clean interface 中硬编码为 V2.1 冻结值，不进入后续微调搜索面。

## 机器证据

- `artifacts/eth_1h_ar_v2_1_full_ablation_2026-07-07.json`
- `artifacts/eth_1h_ar_v2_1_full_ablation_rows_2026-07-07.csv`
- `artifacts/eth_1h_ar_v2_1_full_ablation_fields_2026-07-07.csv`
- `artifacts/eth_1h_ar_v2_1_slices_2026-07-07.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_1_full_ablation.py
```
