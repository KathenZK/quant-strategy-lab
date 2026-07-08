# ETH-1H-Adaptive-Regime-V2.1 Clean 参数微调 - 2026-07-07

## 结论

本轮在 V2.1 全参数消融后的 `27` 个 active clean 参数上做搜索（`bb_break.ema_htf` 与 `bb_break.max_aligned_funding_bps` 判定为 merged-path inert，已硬编码为 V2.1 冻结值）。选择只使用 train/validation/prefit；reused holdout 与近期分片只作冻结后审计。

- 每腿随机样本：`100000`；保留 BB breakout/RSI：`400` / `400`。
- 组合评估：`160000`；可评分：`128759`；相对 V2.1“收益更高、胜率更高、回撤更小”的严格改善组合：`5`。
- 选中观察值：`ETH-1H-AR-V2-1-CLEAN-TUNE-2026-07-07`；后续按用户要求登记为 `ETH-1H-Adaptive-Regime-V3`；selection reason `strict_improvement_vs_v2_1_then_robust_score`。
- strict gate pass：`True`；冻结后 current full 三项同时改善：`True`；reused holdout gate pass：`False`。

## V2.1 vs 微调观察

| Window | V2.1 annual / return / DD / win / trades | Tune annual / return / DD / win / trades |
| --- | --- | --- |
| `train` | `3.7405x` / `303.31%` / `-14.98%` / `88.00%` / `25` | `4.9760x` / `445.34%` / `-12.15%` / `100.00%` / `32` |
| `validation` | `3.8699x` / `116.03%` / `-8.78%` / `100.00%` / `11` | `2.7808x` / `78.99%` / `-8.78%` / `100.00%` / `10` |
| `prefit` | `3.7853x` / `771.27%` / `-14.98%` / `91.67%` / `36` | `4.0591x` / `876.08%` / `-12.15%` / `100.00%` / `42` |
| `reused_holdout` | `0.7048x` / `-8.35%` / `-19.55%` / `50.00%` / `4` | `0.8706x` / `-3.39%` / `-15.70%` / `50.00%` / `4` |
| `current_full` | `3.0277x` / `698.55%` / `-19.55%` / `87.50%` / `40` | `3.3084x` / `842.97%` / `-15.70%` / `95.65%` / `46` |

## 冻结参数

### BB breakout clean（12 参数）

- `indicator_window` = `72`
- `band_k` = `2.5`
- `roc_window` = `24`
- `min_adx` = `16.0`
- `min_rvol` = `3.5`
- `min_atr_bps` = `75.0`
- `min_dir_roc_bps` = `200.0`
- `max_dist_ema_bps` = `750.0`
- `tp_atr` = `3.0`
- `sl_atr` = `5.0`
- `max_hold_bars` = `72`
- `fixed_leverage` = `1.5`

- 硬编码：`ema_htf` = `55`；`max_aligned_funding_bps` = `8.0`。

### RSI clean（15 参数）

- `ema_htf` = `233`
- `indicator_window` = `7`
- `threshold_low` = `5.0`
- `threshold_high` = `75.0`
- `roc_window` = `6`
- `min_adx` = `20.0`
- `max_adx` = `45.0`
- `min_atr_bps` = `125.0`
- `min_dir_roc_bps` = `-300.0`
- `max_dist_ema_bps` = `750.0`
- `tp_atr` = `2.0`
- `sl_atr` = `3.0`
- `max_hold_bars` = `48`
- `cooldown_bars` = `24`
- `fixed_leverage` = `2.5`

## 标准近期分片

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `11.8725x` / `4.86%` / `-7.57%` / `100.00%` / `1` |
| `last_1m` | `1.7813x` / `4.86%` / `-7.57%` / `100.00%` / `1` |
| `last_3m` | `0.8706x` / `-3.39%` / `-15.70%` / `50.00%` / `4` |
| `last_6m` | `1.4349x` / `19.59%` / `-15.70%` / `75.00%` / `8` |
| `last_1y` | `2.2425x` / `124.13%` / `-15.70%` / `90.48%` / `21` |

## 延迟与成本审计

| Scenario | Prefit annual / DD / win | Holdout annual / DD / win | Full annual / DD / win |
| --- | --- | --- | --- |
| `base_k1` | `4.0591x` / `-12.15%` / `100.00%` | `0.8706x` / `-15.70%` / `50.00%` | `3.3084x` / `-15.70%` / `95.65%` |
| `delay_k2` | `2.7964x` / `-16.66%` / `90.24%` | `0.8090x` / `-15.85%` / `25.00%` | `2.3716x` / `-16.66%` / `84.44%` |
| `delay_k3` | `2.5454x` / `-19.53%` / `88.10%` | `0.8138x` / `-16.06%` / `25.00%` | `2.1876x` / `-19.53%` / `82.61%` |
| `slip_8bps` | `3.9825x` / `-12.26%` / `100.00%` | `0.8581x` / `-15.90%` / `50.00%` | `3.2479x` / `-15.90%` / `95.65%` |
| `slip_12bps` | `3.4127x` / `-19.75%` / `97.62%` | `0.8458x` / `-16.11%` / `50.00%` | `2.8354x` / `-19.75%` / `93.48%` |
| `fee12_slip8` | `3.9066x` / `-12.36%` / `100.00%` | `0.8499x` / `-16.06%` / `50.00%` | `3.1900x` / `-16.06%` / `95.65%` |
| `double_cost` | `3.6167x` / `-12.76%` / `100.00%` | `0.8174x` / `-16.70%` / `50.00%` | `2.9683x` / `-16.70%` / `95.65%` |

## 研究边界

- 这是 V2.1 clean 参数面的微调观察值，已按用户要求登记为 `ETH-1H-Adaptive-Regime-V3`；登记不等于 promotion。
- reused holdout 已在 V1/V2/V2.1 阶段揭盲，只能做冻结后失败/边界审计，不能作为 fresh OOS。
- 若 reused holdout 或近期分片失败，应视为失败诊断而不是候选策略。

## 机器证据

- `artifacts/eth_1h_ar_v2_1_clean_tune_2026-07-07.json`
- `artifacts/eth_1h_ar_v2_1_tune_bb_break_pool_2026-07-07.csv`
- `artifacts/eth_1h_ar_v2_1_tune_rsi_pool_2026-07-07.csv`
- `artifacts/eth_1h_ar_v2_1_clean_tune_candidates_2026-07-07.csv`
- `artifacts/eth_1h_ar_v2_1_clean_tune_trades_2026-07-07.csv`
- `artifacts/eth_1h_ar_v2_1_clean_tune_slices_2026-07-07.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_1_clean_tune.py
```
