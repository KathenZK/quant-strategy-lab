# ETH-1H-Adaptive-Regime-V3 高胜率频率优化 - 2026-07-13

## 结论

本轮接受“增加有效交易数，但不能让胜率下降太多”的约束，在 V3 的 27 参数 clean surface 上重新搜索。选择只使用 train/validation/prefit；reused holdout 与近期分片在候选冻结后才读取。

- 硬门槛：prefit trades `>= 60`、validation trades `>= 12`、train/prefit win `>= 85%`、validation win `>= 80%`、各窗口 DD `<20%`。
- K+2 与 8 bps 压力门槛：train/validation/prefit win `>= 80%` 且 DD `<20%`。
- 每腿随机 `120000` 组；组合评估 `250000`，硬门槛命中 `37750`，压力门槛命中 `33`。

## V3 与选中观察值

| Window | V3 annual / return / DD / win / trades | High-win frequency observation |
| --- | --- | --- |
| `train` | `4.9760x` / `445.34%` / `-12.15%` / `100.00%` / `32` | `7.2738x` / `714.62%` / `-17.71%` / `90.00%` / `40` |
| `validation` | `2.7808x` / `78.99%` / `-8.78%` / `100.00%` / `10` | `9.6144x` / `262.64%` / `-8.78%` / `95.00%` / `20` |
| `prefit` | `4.0591x` / `876.08%` / `-12.15%` / `100.00%` / `42` | `8.0199x` / `2854.16%` / `-17.71%` / `91.67%` / `60` |
| `reused_holdout` | `0.8706x` / `-3.39%` / `-15.70%` / `50.00%` / `4` | `1.0329x` / `0.81%` / `-22.55%` / `66.67%` / `9` |
| `current_full` | `3.3084x` / `842.97%` / `-15.70%` / `95.65%` / `46` | `6.1083x` / `2878.06%` / `-22.55%` / `88.41%` / `69` |

## 选中参数

### BB breakout

- `indicator_window` = `72`
- `band_k` = `2.5`
- `roc_window` = `12`
- `min_adx` = `16.0`
- `min_rvol` = `3.5`
- `min_atr_bps` = `0.0`
- `min_dir_roc_bps` = `200.0`
- `max_dist_ema_bps` = `2500.0`
- `tp_atr` = `3.0`
- `sl_atr` = `5.0`
- `max_hold_bars` = `96`
- `fixed_leverage` = `2.0`

- 硬编码：`ema_htf=55`；`max_aligned_funding_bps=8.0`。

### RSI reversal

- `ema_htf` = `144`
- `indicator_window` = `7`
- `threshold_low` = `10.0`
- `threshold_high` = `75.0`
- `roc_window` = `12`
- `min_adx` = `12.0`
- `max_adx` = `55.0`
- `min_atr_bps` = `125.0`
- `min_dir_roc_bps` = `-500.0`
- `max_dist_ema_bps` = `1500.0`
- `tp_atr` = `2.5`
- `sl_atr` = `2.5`
- `max_hold_bars` = `36`
- `cooldown_bars` = `36`
- `fixed_leverage` = `2.5`

## 标准近期分片

| Slice | Annual / Return / DD / Win / Trades |
| --- | --- |
| `last_1d` | `1.0000x` / `0.00%` / `0.00%` / `0.00%` / `0` |
| `last_7d` | `26.4053x` / `6.47%` / `-10.09%` / `100.00%` / `1` |
| `last_1m` | `4.3329x` / `12.80%` / `-10.09%` / `100.00%` / `3` |
| `last_3m` | `1.0329x` / `0.81%` / `-22.55%` / `66.67%` / `9` |
| `last_6m` | `2.7590x` / `65.36%` / `-22.55%` / `76.47%` / `17` |
| `last_1y` | `4.9163x` / `391.10%` / `-22.55%` / `84.21%` / `38` |

## 延迟与成本审计

| Scenario | Prefit annual / DD / win / trades | Holdout annual / DD / win / trades |
| --- | --- | --- |
| `base_k1` | `8.0199x` / `-17.71%` / `91.67%` / `60` | `1.0329x` / `-22.55%` / `66.67%` / `9` |
| `delay_k2` | `5.0830x` / `-17.45%` / `86.44%` / `59` | `1.1383x` / `-22.96%` / `66.67%` / `9` |
| `delay_k3` | `5.0212x` / `-24.47%` / `85.00%` / `60` | `1.1716x` / `-23.50%` / `66.67%` / `9` |
| `slip_8bps` | `6.7730x` / `-17.90%` / `90.00%` / `60` | `0.9988x` / `-23.07%` / `66.67%` / `9` |
| `slip_12bps` | `4.9586x` / `-25.87%` / `86.67%` / `60` | `0.9658x` / `-23.60%` / `66.67%` / `9` |
| `fee12_slip8` | `6.5621x` / `-18.08%` / `90.00%` / `60` | `0.9695x` / `-23.53%` / `66.67%` / `9` |
| `double_cost` | `5.7808x` / `-18.81%` / `90.00%` / `60` | `0.8606x` / `-25.35%` / `66.67%` / `9` |

## 稳健性补充

- one-at-a-time 邻域 `41` 行，其中继续通过 prefit 高胜率频率门槛 `19` 行。
- prefit bootstrap `10000` 次：正权益比例 `100.00%`，胜率 `>=80%` 比例 `99.87%`。

## 研究边界

- 本轮观察值未登记为 V4；需要用户明确要求后才更新主账和 canonical spec。
- reused holdout 已多次揭盲，只能作冻结后失败边界，不能替代 fresh forward。
- 当前数据截止 `2026-07-03T05:00:00+00:00`；该时间之后的新增数据尚未进入本次回测。
- 即使历史审计改善，仍需至少 `20-30` 笔 fresh forward 或 `2-3` 个月，且通过 live-executable 审计后才能 promotion。

## 机器证据

- `artifacts/eth_1h_ar_v3_high_win_frequency_tune_2026-07-13.json`
- `artifacts/eth_1h_ar_v3_high_win_frequency_bb_pool_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_frequency_rsi_pool_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_frequency_candidates_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_frequency_trades_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_frequency_slices_2026-07-13.csv`
- `artifacts/eth_1h_ar_v3_high_win_frequency_neighborhood_2026-07-13.csv`

复现：

```bash
uv run python research/eth/1h-adaptive-regime/scripts/research_eth_1h_ar_v3_high_win_frequency_tune.py
```
