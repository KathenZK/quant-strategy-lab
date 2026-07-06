# SOL-1H-Adaptive-Regime-V1 Clean Interface 等价报告 - 2026-07-03

## 结论

V1 clean interface 已通过逐笔交易路径等价校验：clean 配置生成的交易签名与 V1 原始 `StrategyConfig` 完全一致。

- 原始字段槽：`78`。
- clean tunable 字段槽：`40`。
- 删除或硬编码字段槽：`38`。
- 状态：`diagnostic_baseline_not_promoted_not_live_ready`。
- reused holdout 已在 V1 冻结揭盲时使用，clean interface 只做等价收敛，不构成新版本或 promotion。

## V1 / Clean 等价指标

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `2.4859x` | `161.85%` | `-17.90%` | `78.43%` | `51` | `5.297` |
| `validation` | `2.7805x` | `78.97%` | `-10.31%` | `80.00%` | `35` | `4.393` |
| `prefit` | `2.5852x` | `368.64%` | `-18.86%` | `79.07%` | `86` | `4.906` |
| `reused_holdout` | `0.7129x` | `-8.09%` | `-16.19%` | `50.00%` | `8` | `0.608` |
| `current_full` | `2.1786x` | `330.75%` | `-18.86%` | `76.60%` | `94` | `3.536` |

## Clean 参数面

### Leg 1

- `cooldown_bars` = `12`
- `ema_htf` = `377`
- `fixed_leverage` = `1.5`
- `htf_mode` = `none`
- `indicator_window` = `12`
- `macd_fast` = `21`
- `macd_signal` = `9`
- `macd_slow` = `55`
- `max_adx` = `100.0`
- `max_aligned_funding_bps` = `1.0`
- `max_atr_bps` = `10000.0`
- `max_dist_ema_bps` = `10000.0`
- `max_hold_bars` = `6`
- `min_adx` = `36.0`
- `min_atr_bps` = `100.0`
- `min_dir_roc_bps` = `50.0`
- `min_rvol` = `1.0`
- `require_macd_turn` = `True`
- `roc_window` = `3`
- `sl_atr` = `5.0`
- `tp_atr` = `3.0`

### Leg 2

- `band_k` = `2.0`
- `cooldown_bars` = `24`
- `ema_htf` = `89`
- `fixed_leverage` = `2.5`
- `htf_mode` = `none`
- `indicator_window` = `72`
- `max_adx` = `24.0`
- `max_aligned_funding_bps` = `1.0`
- `max_atr_bps` = `200.0`
- `max_dist_ema_bps` = `750.0`
- `max_hold_bars` = `96`
- `min_adx` = `16.0`
- `min_atr_bps` = `0.0`
- `min_dir_roc_bps` = `-10000.0`
- `min_rvol` = `1.0`
- `require_macd_turn` = `False`
- `sl_atr` = `2.5`
- `trail_activation_atr` = `1.0`
- `trail_atr` = `0.75`

## 机器证据

- `artifacts/sol_1h_ar_v1_clean_config_2026-07-03.json`
- clean 字段面由 `artifacts/sol_1h_ar_v1_full_ablation_2026-07-03.json` 的 `clean_surface` 派生；对应人工可读消融报告为 `ablations/sol-1h-ar-v1-full-parameter-ablation-2026-07-03.md`。

复现：

```bash
uv run python research/sol/1h-adaptive-regime/scripts/sol_1h_ar_v1_clean.py
```
