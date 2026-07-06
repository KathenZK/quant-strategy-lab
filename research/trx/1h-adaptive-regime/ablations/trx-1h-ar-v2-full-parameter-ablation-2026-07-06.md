# TRX-1H-Adaptive-Regime-V2 全参数消融、分片与执行审计 - 2026-07-06

## 结论

`TRX-1H-Adaptive-Regime-V2` 是 V1 clean-equivalent 参数面正式登记后的干净参数版本；本轮覆盖 V2 对外暴露的全部 clean 参数槽，完成 one-at-a-time 全参数消融、最近 `1d/7d/1m/3m/6m/1y` 分片和逐笔执行重放。

V2 与 V1 逐交易路径完全一致；执行审计覆盖 merged `107` 笔交易（full 指标窗口 `104` 笔）和组件交易；违规计数 `0`，merged 违规 `0`。stop gap 按 open 成交 `22` 次；有利 target gap 以 target 价保守记账 `0` 次。

消融发现若干 prefit 单字段严格改善，但这些只用于诊断，不使用 reused holdout 或近期分片选参。V2 仍因收益目标、reused holdout、近期分片和 production runner 失败保持 `NO-GO / not promoted / not live-ready`。

## V2 基线

| Window | Annual / Return / DD / Win / Trades |
| --- | --- |
| `train` | `9.1982x` / `944.03%` / `-16.34%` / `90.77%` / `65` |
| `validation` | `1.7925x` / `39.40%` / `-19.84%` / `80.65%` / `31` |
| `prefit` | `5.1894x` / `1355.40%` / `-19.84%` / `87.50%` / `96` |
| `holdout` | `0.8445x` / `-4.12%` / `-11.42%` / `75.00%` / `8` |
| `full` | `4.0772x` / `1295.38%` / `-19.84%` / `86.54%` / `104` |

## 严格近期分片

| Slice | UTC Start | Annual / Return / DD / Win / Trades |
| --- | --- | --- |
| `last_1d` | `2026-07-02 06:00:00+00:00` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `2026-06-26 06:00:00+00:00` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_1m` | `2026-06-03 06:00:00+00:00` | `0.2728x` / `-10.12%` / `-11.42%` / `50.00%` / `4` |
| `last_3m` | `2026-04-03 06:00:00+00:00` | `0.8445x` / `-4.12%` / `-11.42%` / `75.00%` / `8` |
| `last_6m` | `2026-01-03 06:00:00+00:00` | `1.2752x` / `12.80%` / `-11.42%` / `77.78%` / `18` |
| `last_1y` | `2025-07-03 06:00:00+00:00` | `1.4521x` / `45.18%` / `-19.84%` / `80.00%` / `50` |

## V2 参数消融

- V2 对外暴露 clean 字段槽：`36`；coverage missing：`{'macd_flip': [], 'stoch_reversal': []}`。
- one-at-a-time 行数（含 baseline）：`211`。
- prefit 严格改善行数：`8`；这些行未用于 holdout/近期分片选参。

| Component | Field | Baseline | Classification | Variants | Component Equal | Merged Equal | Prefit Strict Improve |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `macd_flip` | `ema_htf` | `377` | `v2_exposed_parameter` | `5` | `1` | `2` | `0` |
| `macd_flip` | `roc_window` | `12` | `v2_exposed_parameter` | `7` | `4` | `4` | `1` |
| `macd_flip` | `macd_fast` | `34` | `v2_exposed_parameter` | `4` | `1` | `1` | `0` |
| `macd_flip` | `macd_slow` | `89` | `v2_exposed_parameter` | `4` | `1` | `1` | `0` |
| `macd_flip` | `macd_signal` | `13` | `v2_exposed_parameter` | `4` | `1` | `1` | `0` |
| `macd_flip` | `min_adx` | `12.0` | `v2_exposed_parameter` | `6` | `3` | `3` | `0` |
| `macd_flip` | `max_adx` | `28.0` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `macd_flip` | `min_rvol` | `1.5` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `macd_flip` | `max_atr_bps` | `200.0` | `v2_exposed_parameter` | `8` | `8` | `8` | `0` |
| `macd_flip` | `min_dir_roc_bps` | `-100.0` | `v2_exposed_parameter` | `8` | `6` | `6` | `0` |
| `macd_flip` | `max_dist_ema_bps` | `1000.0` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `macd_flip` | `htf_mode` | `h12` | `v2_exposed_parameter` | `4` | `1` | `1` | `0` |
| `macd_flip` | `require_macd_turn` | `True` | `v2_exposed_parameter` | `2` | `2` | `2` | `0` |
| `macd_flip` | `tp_atr` | `2.0` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `macd_flip` | `sl_atr` | `4.0` | `v2_exposed_parameter` | `5` | `1` | `1` | `0` |
| `macd_flip` | `max_hold_bars` | `168` | `v2_exposed_parameter` | `7` | `5` | `5` | `0` |
| `macd_flip` | `cooldown_bars` | `3` | `v2_exposed_parameter` | `5` | `3` | `4` | `0` |
| `macd_flip` | `entry_delay_bars` | `1` | `execution_timing_parameter` | `2` | `1` | `1` | `0` |
| `macd_flip` | `fixed_leverage` | `4.0` | `v2_exposed_parameter` | `8` | `1` | `1` | `0` |
| `stoch_reversal` | `side_mode` | `long` | `v2_exposed_parameter` | `2` | `1` | `1` | `1` |
| `stoch_reversal` | `ema_htf` | `55` | `v2_exposed_parameter` | `5` | `5` | `5` | `0` |
| `stoch_reversal` | `indicator_window` | `21` | `v2_exposed_parameter` | `4` | `1` | `1` | `0` |
| `stoch_reversal` | `threshold_low` | `25.0` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `stoch_reversal` | `threshold_high` | `85.0` | `v2_exposed_parameter` | `7` | `7` | `7` | `0` |
| `stoch_reversal` | `roc_window` | `3` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `stoch_reversal` | `max_adx` | `30.0` | `v2_exposed_parameter` | `8` | `1` | `1` | `1` |
| `stoch_reversal` | `min_rvol` | `1.0` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `stoch_reversal` | `min_dir_roc_bps` | `-200.0` | `v2_exposed_parameter` | `8` | `2` | `2` | `0` |
| `stoch_reversal` | `require_body_dir` | `True` | `v2_exposed_parameter` | `2` | `1` | `1` | `0` |
| `stoch_reversal` | `sl_atr` | `5.0` | `v2_exposed_parameter` | `5` | `1` | `1` | `1` |
| `stoch_reversal` | `trail_activation_atr` | `3.0` | `v2_exposed_parameter` | `8` | `1` | `1` | `0` |
| `stoch_reversal` | `trail_atr` | `1.25` | `v2_exposed_parameter` | `8` | `1` | `1` | `1` |
| `stoch_reversal` | `max_hold_bars` | `168` | `v2_exposed_parameter` | `7` | `1` | `1` | `0` |
| `stoch_reversal` | `cooldown_bars` | `24` | `v2_exposed_parameter` | `7` | `1` | `1` | `2` |
| `stoch_reversal` | `entry_delay_bars` | `1` | `execution_timing_parameter` | `3` | `1` | `1` | `1` |
| `stoch_reversal` | `fixed_leverage` | `3.0` | `v2_exposed_parameter` | `8` | `1` | `1` | `0` |

## 不可实盘风险检查

- 入场时序：所有组件 `entry_delay_bars>=1`，信号闭合后下一根 open 入场：`True`。
- 逐笔重放：违规总数 `0`，merged 违规 `0`。
- stop 穿越：`stop_gap_open` 按 open 成交 `22` 次，未发现穿越 stop 后仍按旧 stop 价成交。
- target 穿越：有利 gap/open 以 target 价保守记账 `0` 次，不构成乐观穿越收益。
- 未来函数：信号使用闭合 `1h` K，`K+1 open` 入场；HTF/funding 特征按已知时间 `merge_asof` 对齐。未发现 OOS 排序或 K 内决策依赖。

## 机器证据

- `artifacts/trx_1h_ar_v2_full_ablation_2026-07-06.json`
- `artifacts/trx_1h_ar_v2_full_ablation_rows_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_full_ablation_fields_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_slices_2026-07-06.csv`
- `artifacts/trx_1h_ar_v2_trade_execution_audit_2026-07-06.csv`

复现：

```bash
uv run python research/trx/1h-adaptive-regime/scripts/research_trx_1h_ar_v2_full_ablation.py
```
