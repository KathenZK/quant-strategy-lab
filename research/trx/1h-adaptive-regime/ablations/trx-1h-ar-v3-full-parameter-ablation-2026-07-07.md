# TRX-1H-Adaptive-Regime-V3 全参数消融、分片与执行审计 - 2026-07-07

## 结论

`TRX-1H-Adaptive-Regime-V3` 是 V2 消融引导微调后的登记版本；本轮覆盖 V3 对外暴露的全部参数槽，完成 one-at-a-time 全参数消融、最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔执行重放，并按 merged 交易路径识别 dormant（无作用）字段，输出 V3 clean 参数面。

执行审计覆盖 merged `94` 笔交易（current full 指标窗口 `93` 笔）和组件交易；违规计数 `0`，merged 违规 `0`。stop gap 按 open 成交 `10` 次；有利 target gap 以 target 价保守记账 `0` 次。

消融发现的 prefit 单字段严格改善只作为诊断，不使用 reused holdout 或近期分片选参。V3 保持 `NO-GO / not promoted / not live-ready`。

## V3 基线

| Window | Annual / Return / DD / Win / Trades |
| --- | --- |
| `train` | `8.1557x` / `819.38%` / `-17.17%` / `90.91%` / `55` |
| `validation` | `6.0130x` / `177.62%` / `-11.17%` / `100.00%` / `29` |
| `prefit` | `7.3305x` / `2452.42%` / `-17.17%` / `94.05%` / `84` |
| `reused_holdout` | `1.0834x` / `2.02%` / `-15.23%` / `77.78%` / `9` |
| `current_full` | `5.6863x` / `2503.89%` / `-17.17%` / `92.47%` / `93` |

## 标准近期分片

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `1.5230x` / `3.52%` / `-1.56%` / `100.00%` / `2` |
| `last_3m` | `1.0834x` / `2.02%` / `-15.23%` / `77.78%` / `9` |
| `last_6m` | `3.2850x` / `80.29%` / `-15.23%` / `91.30%` / `23` |
| `last_1y` | `2.9135x` / `191.14%` / `-15.71%` / `91.84%` / `49` |

## V3 参数消融

- V3 对外暴露字段槽：`36`；coverage missing：`{'macd_flip': [], 'stoch_reversal': []}`。
- one-at-a-time 行数（含 baseline）：`215`。
- prefit 严格改善行数：`0`；这些行未用于 holdout/近期分片选参。

| Component | Field | Baseline | Variants | Merged Equal | Dormant | Prefit Strict Improve |
| --- | --- | --- | ---: | ---: | --- | ---: |
| `macd_flip` | `ema_htf` | `89` | `5` | `5` | `True` | `0` |
| `macd_flip` | `roc_window` | `6` | `7` | `4` | `False` | `0` |
| `macd_flip` | `macd_fast` | `(34, 89, 13)` | `4` | `1` | `False` | `0` |
| `macd_flip` | `macd_slow` | `(34, 89, 13)` | `4` | `1` | `False` | `0` |
| `macd_flip` | `macd_signal` | `(34, 89, 13)` | `4` | `1` | `False` | `0` |
| `macd_flip` | `min_adx` | `20.0` | `7` | `1` | `False` | `0` |
| `macd_flip` | `max_adx` | `24.0` | `8` | `1` | `False` | `0` |
| `macd_flip` | `min_rvol` | `0.0` | `7` | `1` | `False` | `0` |
| `macd_flip` | `max_atr_bps` | `150.0` | `8` | `8` | `True` | `0` |
| `macd_flip` | `min_dir_roc_bps` | `-100.0` | `8` | `5` | `False` | `0` |
| `macd_flip` | `max_dist_ema_bps` | `10000.0` | `7` | `5` | `False` | `0` |
| `macd_flip` | `htf_mode` | `h12` | `4` | `1` | `False` | `0` |
| `macd_flip` | `require_macd_turn` | `False` | `2` | `2` | `True` | `0` |
| `macd_flip` | `tp_atr` | `2.0` | `7` | `1` | `False` | `0` |
| `macd_flip` | `sl_atr` | `5.0` | `5` | `1` | `False` | `0` |
| `macd_flip` | `max_hold_bars` | `120` | `7` | `7` | `True` | `0` |
| `macd_flip` | `cooldown_bars` | `3` | `5` | `4` | `False` | `0` |
| `macd_flip` | `entry_delay_bars` | `1` | `2` | `1` | `False` | `0` |
| `macd_flip` | `fixed_leverage` | `5.0` | `8` | `1` | `False` | `0` |
| `stoch_reversal` | `side_mode` | `both` | `3` | `1` | `False` | `0` |
| `stoch_reversal` | `ema_htf` | `233` | `5` | `5` | `True` | `0` |
| `stoch_reversal` | `indicator_window` | `21` | `4` | `1` | `False` | `0` |
| `stoch_reversal` | `threshold_low` | `25.0` | `7` | `1` | `False` | `0` |
| `stoch_reversal` | `threshold_high` | `90.0` | `7` | `1` | `False` | `0` |
| `stoch_reversal` | `roc_window` | `3` | `7` | `2` | `False` | `0` |
| `stoch_reversal` | `max_adx` | `24.0` | `8` | `1` | `False` | `0` |
| `stoch_reversal` | `min_rvol` | `1.0` | `7` | `1` | `False` | `0` |
| `stoch_reversal` | `min_dir_roc_bps` | `-300.0` | `8` | `3` | `False` | `0` |
| `stoch_reversal` | `require_body_dir` | `True` | `2` | `1` | `False` | `0` |
| `stoch_reversal` | `sl_atr` | `6.0` | `5` | `1` | `False` | `0` |
| `stoch_reversal` | `trail_activation_atr` | `3.0` | `8` | `1` | `False` | `0` |
| `stoch_reversal` | `trail_atr` | `2.0` | `8` | `1` | `False` | `0` |
| `stoch_reversal` | `max_hold_bars` | `120` | `7` | `1` | `False` | `0` |
| `stoch_reversal` | `cooldown_bars` | `6` | `8` | `3` | `False` | `0` |
| `stoch_reversal` | `entry_delay_bars` | `2` | `3` | `1` | `False` | `0` |
| `stoch_reversal` | `fixed_leverage` | `3.5` | `8` | `1` | `False` | `0` |

## V3 clean 参数面

dormant 判定口径：该字段所有非基线取值都不改变 merged 逐交易路径。dormant 字段从可调参数面移除并固定为 V3 值；active 字段保留为可调面。

- `macd_flip` active：`['cooldown_bars', 'entry_delay_bars', 'fixed_leverage', 'htf_mode', 'macd_fast', 'macd_signal', 'macd_slow', 'max_adx', 'max_dist_ema_bps', 'min_adx', 'min_dir_roc_bps', 'min_rvol', 'roc_window', 'sl_atr', 'tp_atr']`。
- `macd_flip` dormant/fixed：`['ema_htf', 'max_atr_bps', 'max_hold_bars', 'require_macd_turn']`。
- `stoch_reversal` active：`['cooldown_bars', 'entry_delay_bars', 'fixed_leverage', 'indicator_window', 'max_adx', 'max_hold_bars', 'min_dir_roc_bps', 'min_rvol', 'require_body_dir', 'roc_window', 'side_mode', 'sl_atr', 'threshold_high', 'threshold_low', 'trail_activation_atr', 'trail_atr']`。
- `stoch_reversal` dormant/fixed：`['ema_htf']`。

## 不可实盘风险检查

- 入场时序：所有组件 `entry_delay_bars>=1`，信号闭合后按延迟根数用 open 入场：`True`。
- 逐笔重放：违规总数 `0`，merged 违规 `0`。
- stop 穿越：`stop_gap_open` 按 open 成交 `10` 次，未发现穿越 stop 后仍按旧 stop 价成交。
- target 穿越：有利 gap/open 以 target 价保守记账 `0` 次，不构成乐观穿越收益。
- 未来函数：信号使用闭合 `1h` K，延迟后 open 入场；HTF/funding 特征按已知时间 `merge_asof` 对齐。未发现 OOS 排序或 K 内决策依赖。

## 机器证据

- `artifacts/trx_1h_ar_v3_full_ablation_2026-07-07.json`
- `artifacts/trx_1h_ar_v3_full_ablation_rows_2026-07-07.csv`
- `artifacts/trx_1h_ar_v3_full_ablation_fields_2026-07-07.csv`
- `artifacts/trx_1h_ar_v3_slices_2026-07-07.csv`
- `artifacts/trx_1h_ar_v3_trade_execution_audit_2026-07-07.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v3_full_ablation.py
```
