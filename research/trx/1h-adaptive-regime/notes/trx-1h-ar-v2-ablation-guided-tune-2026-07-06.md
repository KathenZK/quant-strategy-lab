# TRX-1H-Adaptive-Regime-V2 消融引导微调 - 2026-07-06

## 结论

本轮基于 V2 clean 参数面和 V2 全参数消融后的可调字段做微调；选择过程只使用 train/validation/prefit，不读取 reused holdout 或近期分片。

- pair pool：`500`；满足 train/validation/prefit `win>=80%`、DD `<20%`、prefit annual 高于 V2 的候选：`41`。
- 选中观察值：`TRX-1H-AR-V2-ABLATION-GUIDED-TUNE-2026-07-06`，source row `43`；后续按用户明确指令正式登记为 `TRX-1H-Adaptive-Regime-V3`。
- prefit gate pass：`True`；冻结后 current full gate pass：`True`；reused holdout gate pass：`False`。

## V2 vs V3

| Window | V2 annual / return / DD / win / trades | V3 annual / return / DD / win / trades |
| --- | --- | --- |
| `train` | `9.1982x` / `944.03%` / `-16.34%` / `90.77%` / `65` | `8.1557x` / `819.38%` / `-17.17%` / `90.91%` / `55` |
| `validation` | `1.7925x` / `39.40%` / `-19.84%` / `80.65%` / `31` | `6.0130x` / `177.62%` / `-11.17%` / `100.00%` / `29` |
| `prefit` | `5.1894x` / `1355.40%` / `-19.84%` / `87.50%` / `96` | `7.3305x` / `2452.42%` / `-17.17%` / `94.05%` / `84` |
| `reused_holdout` | `0.8445x` / `-4.12%` / `-11.42%` / `75.00%` / `8` | `1.0834x` / `2.02%` / `-15.23%` / `77.78%` / `9` |
| `current_full` | `4.0772x` / `1295.38%` / `-19.84%` / `86.54%` / `104` | `5.6863x` / `2503.89%` / `-17.17%` / `92.47%` / `93` |

## 冻结参数

### MACD V3 登记参数

- `ema_htf` = `89`
- `roc_window` = `6`
- `macd_fast` = `34`
- `macd_slow` = `89`
- `macd_signal` = `13`
- `min_adx` = `20.0`
- `max_adx` = `24.0`
- `min_rvol` = `0.0`
- `max_atr_bps` = `150.0`
- `min_dir_roc_bps` = `-100.0`
- `max_dist_ema_bps` = `10000.0`
- `htf_mode` = `h12`
- `require_macd_turn` = `False`
- `tp_atr` = `2.0`
- `sl_atr` = `5.0`
- `max_hold_bars` = `120`
- `cooldown_bars` = `3`
- `entry_delay_bars` = `1`
- `fixed_leverage` = `5.0`

### Stochastic V3 登记参数

- `side_mode` = `both`
- `ema_htf` = `233`
- `indicator_window` = `21`
- `threshold_low` = `25.0`
- `threshold_high` = `90.0`
- `roc_window` = `3`
- `max_adx` = `24.0`
- `min_rvol` = `1.0`
- `min_dir_roc_bps` = `-300.0`
- `require_body_dir` = `True`
- `sl_atr` = `6.0`
- `trail_activation_atr` = `3.0`
- `trail_atr` = `2.0`
- `max_hold_bars` = `120`
- `cooldown_bars` = `6`
- `entry_delay_bars` = `2`
- `fixed_leverage` = `3.5`

## 标准近期分片

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `1.5230x` / `3.52%` / `-1.56%` / `100.00%` / `2` |
| `last_3m` | `1.0834x` / `2.02%` / `-15.23%` / `77.78%` / `9` |
| `last_6m` | `3.2850x` / `80.29%` / `-15.23%` / `91.30%` / `23` |
| `last_1y` | `2.9135x` / `191.14%` / `-15.71%` / `91.84%` / `49` |

## 执行可行性复核

- 逐笔重放违规：`0`；merged 违规：`0`。
- stop gap/open 按 open 成交：`10` 次。
- target gap 以 target 价保守记账：`0` 次。
- 所有组件 `entry_delay_bars>=1`：`True`。

## 研究边界

- 这是 `TRX-1H-Adaptive-Regime-V2` 的微调观察值，已按后续用户明确指令登记为 `TRX-1H-Adaptive-Regime-V3`；登记不等于 promotion。
- reused holdout 已在初始研究中揭盲，只能做冻结后失败/边界审计，不能作为 fresh OOS。
- 虽然 full 收益、胜率和回撤满足本次目标，但 reused holdout 胜率未达 80%，且没有新增 forward trades 和 TRX production runner，因此 V3 仍不得 promotion。

## 机器证据

- `artifacts/trx_1h_ar_v2_ablation_guided_tune_2026-07-06.json`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_candidates_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_trades_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_slices_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_ablation_guided_tune_execution_audit_2026-07-06.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v2_ablation_guided_tune.py
```
