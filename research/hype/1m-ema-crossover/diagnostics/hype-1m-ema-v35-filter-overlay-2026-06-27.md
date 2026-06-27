# HYPE 1m EMA V35 filter overlay diagnostic 2026-06-27

Family id: `HYPE-1M-EMA-Crossover`

Reference family: `HYPE-EMA-Trend-Breakout-V35` (`15m-ema-trend-breakout`). This is a transfer diagnostic, not a relabeling of V35.

## 数据质量

- Normalized OHLCV: `94` 个日分区，`134184` 根 K。
- Raw OHLCV: `94` 个日分区，`134184` 根 K。
- 时间范围：`2026-03-25 00:00:00+00:00` 到 `2026-06-26 04:23:00+00:00`。
- 连续性：expected `134184`，missing `0`，duplicate `0`。
- OHLC/VWAP/volume hard violations：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'negative_trade_count': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。

## 迁移规则

- 1m 入场仍然是快 EMA 上穿慢 EMA 下一根 open 做多、下穿下一根 open 做空。
- V35 overlay 使用已闭合的 15m/1h 数据，不使用当前未收完的 15m 或 1h K。
- `v35_full`：15m EMA96/384 同向、15m ADX28 多头 >= 28 / 空头 >= 36、15m volume_surge 多头 >= 0.25 / 空头 >= 0.50、1h 确认同向。
- `v35_no_volume`、`v35_relaxed_adx_volume`、`v35_early_adx14_di` 用来检查是否是 V35 门槛过严导致样本不足。
- 出场沿用上一轮偏离止盈状态机：fast-EMA 偏离 arm，然后用高低点回撤、快线失守或分批止盈退出。

## 搜索规模

- EMA pairs: `8:21,13:48,21:55,21:72,21:96,30:120`。
- Exposures: `1,2,3`。
- Config rows including overlay filters and exposure: `432`。
- Paper gate: trades >= `20`，PF >= `1.1`，win >= `48%`，maxDD >= `-20%`，validation/forward/recent slices 不得亏损。
- 通过 paper gate：`0`。

没有配置通过完整 paper gate；下面列出的是最接近的诊断配置，不能升级为 paper-live 或 live。

## Top rows

| name | exposure | full_trades | full_total_return | full_annualized_multiple | full_max_dd | full_win_rate | full_profit_factor | fwd_last_20pct_total_return | recent_30d_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_devtrail_arm2p2_dd1p8_sl1p5` | `3.000` | `63` | `-0.05%` | `1.00x` | `-10.59%` | `38.10%` | `1.029` | `-1.53%` | `-5.36%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_exhaust_arm2p2_dd1p8_sl1p5` | `3.000` | `63` | `-0.05%` | `1.00x` | `-10.59%` | `38.10%` | `1.029` | `-1.53%` | `-5.36%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST30_SLOW120_v35_relaxed_adx_volume_devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `20` | `0.43%` | `1.02x` | `-2.29%` | `45.00%` | `1.098` | `-1.20%` | `-2.29%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST30_SLOW120_v35_relaxed_adx_volume_exhaust_arm2p2_dd1p8_sl1p5` | `1.000` | `20` | `0.43%` | `1.02x` | `-2.29%` | `45.00%` | `1.098` | `-1.20%` | `-2.29%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_devtrail_arm2p2_dd1p8_sl1p5` | `2.000` | `63` | `0.30%` | `1.01x` | `-7.17%` | `38.10%` | `1.029` | `-0.90%` | `-3.47%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_exhaust_arm2p2_dd1p8_sl1p5` | `2.000` | `63` | `0.30%` | `1.01x` | `-7.17%` | `38.10%` | `1.029` | `-0.90%` | `-3.47%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST30_SLOW120_v35_relaxed_adx_volume_devtrail_arm2p2_dd1p8_sl1p5` | `2.000` | `20` | `0.78%` | `1.03x` | `-4.53%` | `45.00%` | `1.098` | `-2.38%` | `-4.53%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST30_SLOW120_v35_relaxed_adx_volume_exhaust_arm2p2_dd1p8_sl1p5` | `2.000` | `20` | `0.78%` | `1.03x` | `-4.53%` | `45.00%` | `1.098` | `-2.38%` | `-4.53%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `63` | `0.32%` | `1.01x` | `-3.64%` | `38.10%` | `1.029` | `-0.39%` | `-1.68%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_exhaust_arm2p2_dd1p8_sl1p5` | `1.000` | `63` | `0.32%` | `1.01x` | `-3.64%` | `38.10%` | `1.029` | `-0.39%` | `-1.68%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST30_SLOW120_v35_relaxed_adx_volume_devtrail_arm2p2_dd1p8_sl1p5` | `3.000` | `20` | `1.05%` | `1.04x` | `-6.74%` | `45.00%` | `1.098` | `-3.56%` | `-6.74%` |
| `HYPE_1M_EMA_V35_OVERLAY_FAST30_SLOW120_v35_relaxed_adx_volume_exhaust_arm2p2_dd1p8_sl1p5` | `3.000` | `20` | `1.05%` | `1.04x` | `-6.74%` | `45.00%` | `1.098` | `-3.56%` | `-6.74%` |

## EMA21/96 focus

| fast_ema | slow_ema | overlay_filter | exit_model | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `21` | `96` | `v35_early_adx14_di` | `devtrail_arm2p2_dd1p8_sl1p5` | `3.000` | `2` | `0.74%` | `-2.44%` | `1.470` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `exhaust_arm2p2_dd1p8_sl1p5` | `3.000` | `2` | `0.74%` | `-2.44%` | `1.470` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `devtrail_arm2p2_dd1p8_sl1p5` | `2.000` | `2` | `0.50%` | `-1.63%` | `1.470` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `exhaust_arm2p2_dd1p8_sl1p5` | `2.000` | `2` | `0.50%` | `-1.63%` | `1.470` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `exhaust_arm2p2_dd1p8_sl1p5` | `1.000` | `2` | `0.26%` | `-0.82%` | `1.470` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `2` | `0.26%` | `-0.82%` | `1.470` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `staged_p2p2_dd1p5_sl1p5` | `1.000` | `2` | `-0.44%` | `-0.82%` | `0.200` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `devtrail_arm2_dd1p5_sl1p5` | `1.000` | `2` | `-0.61%` | `-0.82%` | `0.000` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `staged_p2p2_dd1p5_sl1p5` | `2.000` | `2` | `-0.89%` | `-1.63%` | `0.200` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `devtrail_arm2_dd1p5_sl1p5` | `2.000` | `2` | `-1.22%` | `-1.63%` | `0.000` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `staged_p2p2_dd1p5_sl1p5` | `3.000` | `2` | `-1.33%` | `-2.44%` | `0.200` | `0.00%` |
| `21` | `96` | `v35_early_adx14_di` | `devtrail_arm2_dd1p5_sl1p5` | `3.000` | `2` | `-1.83%` | `-2.44%` | `0.000` | `0.00%` |

## EMA pair surface

| fast_ema | slow_ema | overlay_filter | exit_model | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `21` | `72` | `v35_no_volume` | `devtrail_arm2p2_dd1p8_sl1p5` | `3.000` | `63` | `-0.05%` | `-10.59%` | `1.029` | `-1.53%` |
| `30` | `120` | `v35_relaxed_adx_volume` | `devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `20` | `0.43%` | `-2.29%` | `1.098` | `-1.20%` |
| `21` | `55` | `v35_no_volume` | `devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `82` | `-3.89%` | `-5.14%` | `0.823` | `-1.79%` |
| `21` | `96` | `v35_relaxed_adx_volume` | `devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `30` | `-2.94%` | `-3.68%` | `0.684` | `-1.17%` |
| `8` | `21` | `v35_early_adx14_di` | `exhaust_arm2p2_dd1p8_sl1p5` | `1.000` | `63` | `-6.71%` | `-10.41%` | `0.657` | `0.18%` |
| `13` | `48` | `v35_early_adx14_di` | `staged_p2p2_dd1p5_sl1p5` | `1.000` | `26` | `-5.32%` | `-6.36%` | `0.379` | `0.44%` |

## Overlay filter surface

| fast_ema | slow_ema | overlay_filter | exit_model | exposure | full_trades | full_total_return | full_max_dd | full_profit_factor | fwd_last_20pct_total_return |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `21` | `72` | `v35_no_volume` | `devtrail_arm2p2_dd1p8_sl1p5` | `3.000` | `63` | `-0.05%` | `-10.59%` | `1.029` | `-1.53%` |
| `30` | `120` | `v35_relaxed_adx_volume` | `devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `20` | `0.43%` | `-2.29%` | `1.098` | `-1.20%` |
| `8` | `21` | `v35_early_adx14_di` | `exhaust_arm2p2_dd1p8_sl1p5` | `1.000` | `63` | `-6.71%` | `-10.41%` | `0.657` | `0.18%` |
| `21` | `72` | `v35_full` | `staged_p2p2_dd1p5_sl1p5` | `1.000` | `20` | `-2.95%` | `-3.44%` | `0.464` | `-2.40%` |
| `21` | `72` | `v35_full_plus_1m_adx20` | `staged_p2p2_dd1p5_sl1p5` | `1.000` | `11` | `-0.57%` | `-1.32%` | `0.762` | `-1.29%` |
| `30` | `120` | `none_reference` | `devtrail_arm2p2_dd1p8_sl1p5` | `1.000` | `1399` | `-83.65%` | `-83.95%` | `0.429` | `-35.71%` |

## 月度提示

- top score `HYPE_1M_EMA_V35_OVERLAY_FAST21_SLOW72_v35_no_volume_devtrail_arm2p2_dd1p8_sl1p5` 的负收益月份数：`6`。
- 最差月份 `2026-04`：return `-6.70%`，PF `0.437`，trades `19`。

## 结论

V35 的强趋势过滤确实能显著减少 1m EMA 交叉噪声，但本轮没有把短周期金叉/死叉追单变成可用候选。
核心差异仍然是机制：V35 原策略不是在交叉瞬间追单，而是用 15m 趋势突破 + 1h 确认 + ATR bracket 抓慢趋势段；把它当作 1m 交叉过滤器只是在过滤噪声，不能自动生成同等 edge。

## 产物

- 脚本：`research/hype/1m-ema-crossover/scripts/research_hype_1m_ema_v35_filter_overlay.py`
- JSON：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_v35_filter_overlay_2026-06-27.json`
- Summary CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_v35_filter_overlay_summary_2026-06-27.csv`
- Slices CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_v35_filter_overlay_slices_2026-06-27.csv`
- Monthly CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_v35_filter_overlay_monthly_2026-06-27.csv`
- Top trades CSV：`research/hype/1m-ema-crossover/artifacts/hype_1m_ema_v35_filter_overlay_top_trades_2026-06-27.csv`
