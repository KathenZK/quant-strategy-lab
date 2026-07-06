# ETH-1H-Adaptive-Regime-V2 消融引导高胜率微调 - 2026-07-06

## 结论

本轮基于 V2 全参数消融后的 29 参数 clean 面重新搜索；选择过程只使用 train/validation/prefit，不读取 reused holdout 或近期分片。

- V2 单字段消融 high-win gate 命中：`0`。
- 组合搜索 pair：`202500`；可评分：`148346`；满足 train/validation/prefit `win>=80%`、DD `<20%`、prefit annual 高于 V2 的候选：`65`。
- 选中观察值：`ETH-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06`；后续按用户要求登记为 `ETH-1H-Adaptive-Regime-V2.1`；selection reason `prefit_train_validation_high_win_hard_gate_then_robust_score`。
- prefit gate pass：`True`；冻结后 current full gate pass：`True`；reused holdout gate pass：`False`。

## V2 vs 微调观察

| Window | V2 annual / return / DD / win / trades | Tune annual / return / DD / win / trades |
| --- | --- | --- |
| `train` | `3.8425x` / `314.94%` / `-15.02%` / `72.60%` / `73` | `3.7405x` / `303.31%` / `-14.98%` / `88.00%` / `25` |
| `validation` | `2.7855x` / `79.16%` / `-10.56%` / `75.00%` / `32` | `3.8699x` / `116.03%` / `-8.78%` / `100.00%` / `11` |
| `prefit` | `3.4333x` / `643.41%` / `-15.02%` / `73.33%` / `105` | `3.7853x` / `771.27%` / `-14.98%` / `91.67%` / `36` |
| `reused_holdout` | `0.4323x` / `-18.86%` / `-18.93%` / `50.00%` / `10` | `0.7048x` / `-8.35%` / `-19.55%` / `50.00%` / `4` |
| `current_full` | `2.6071x` / `503.24%` / `-18.93%` / `71.30%` / `115` | `3.0277x` / `698.55%` / `-19.55%` / `87.50%` / `40` |

## 冻结参数

### BB breakout clean

- `ema_htf` = `55`
- `indicator_window` = `32`
- `band_k` = `2.0`
- `roc_window` = `12`
- `min_adx` = `36.0`
- `min_rvol` = `3.0`
- `min_atr_bps` = `50.0`
- `min_dir_roc_bps` = `100.0`
- `max_dist_ema_bps` = `10000.0`
- `max_aligned_funding_bps` = `8.0`
- `tp_atr` = `3.0`
- `sl_atr` = `5.0`
- `max_hold_bars` = `48`
- `fixed_leverage` = `3.0`

### RSI clean

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
| `last_7d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `2.1132x` / `6.34%` / `-1.47%` / `100.00%` / `1` |
| `last_3m` | `0.7048x` / `-8.35%` / `-19.55%` / `50.00%` / `4` |
| `last_6m` | `1.2291x` / `10.76%` / `-19.55%` / `71.43%` / `7` |
| `last_1y` | `2.7494x` / `174.75%` / `-19.55%` / `85.71%` / `21` |

## 延迟与成本审计

| Scenario | Prefit annual / DD / win | Holdout annual / DD / win | Full annual / DD / win |
| --- | --- | --- | --- |
| `base_k1` | `3.7853x` / `-14.98%` / `91.67%` | `0.7048x` / `-19.55%` / `50.00%` | `3.0277x` / `-19.55%` / `87.50%` |
| `delay_k2` | `3.2052x` / `-20.34%` / `88.57%` | `0.8001x` / `-17.04%` / `40.00%` | `2.6656x` / `-20.34%` / `82.50%` |
| `delay_k3` | `2.2708x` / `-19.53%` / `74.29%` | `0.3496x` / `-23.40%` / `20.00%` | `1.7711x` / `-24.21%` / `67.50%` |
| `slip_8bps` | `3.3023x` / `-15.37%` / `88.89%` | `0.6876x` / `-19.86%` / `50.00%` | `2.6810x` / `-19.86%` / `85.00%` |
| `slip_12bps` | `3.1632x` / `-15.48%` / `88.89%` | `0.6709x` / `-20.16%` / `50.00%` | `2.5743x` / `-20.16%` / `85.00%` |
| `fee12_slip8` | `3.2285x` / `-15.49%` / `88.89%` | `0.6742x` / `-20.16%` / `50.00%` | `2.6220x` / `-20.16%` / `85.00%` |
| `double_cost` | `2.9486x` / `-16.21%` / `88.89%` | `0.6229x` / `-21.40%` / `50.00%` | `2.3984x` / `-21.40%` / `85.00%` |

## 近期表现糟糕的原因

- 最近三个月只有 `4` 笔交易，样本极薄，胜率从 prefit 的 `91.67%` 退化到 `50.00%`。
- 这 `4` 笔全部是 `BB_BREAK` 多头，没有 RSI reversal 和空头交易分散风险。
- 两笔亏损分别是 `2026-04-11` stop-market `-11.65%` equity 和 `2026-05-23` timeout `-6.26%` equity；两笔盈利只有 `+4.07%` 和 `+6.34%` equity。
- V2.1 为了满足高胜率目标牺牲了交易频率，并把 BB leg 杠杆提高到 `3.0`；近期只要少数突破失败，就会吞掉多个月收益。
- K+2 和成本压力也显示边缘很薄：K+2 prefit DD `-20.34%`，double-cost full DD `-21.40%`。

## 研究边界

- 这是 V2 的消融引导微调观察值，已按用户要求登记为 `ETH-1H-Adaptive-Regime-V2.1`；登记不等于 promotion。
- reused holdout 已在 V1/V2 阶段揭盲，只能做冻结后失败/边界审计，不能作为 fresh OOS。
- 若 current full 或 reused holdout 不满足 80% 胜率目标，应视为失败诊断，而不是候选策略。

## 机器证据

- `artifacts/eth_1h_ar_v2_ablation_guided_tune_2026-07-06.json`
- `artifacts/eth_1h_ar_v2_tune_bb_break_pool_2026-07-06.csv`
- `artifacts/eth_1h_ar_v2_tune_rsi_pool_2026-07-06.csv`
- `artifacts/eth_1h_ar_v2_ablation_guided_tune_candidates_2026-07-06.csv`
- `artifacts/eth_1h_ar_v2_ablation_guided_tune_trades_2026-07-06.csv`
- `artifacts/eth_1h_ar_v2_ablation_guided_tune_slices_2026-07-06.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v2_ablation_guided_tune.py
```
