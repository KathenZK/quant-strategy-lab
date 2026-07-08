# HYPE-5M-Micro-Scalp-V1 full parameter ablation 2026-06-29

Family id: `HYPE-5M-Micro-Scalp`

本报告由脚本逐项改变 `HYPE-5M-Micro-Scalp-V1` 的每一个策略参数生成。每个变体只改变一个字段，其余字段保持 V1 基线不变。

## 执行口径

- 闭合 K 信号，下一根 open 入场。
- 入场立即挂固定 TP/SL bracket；同 K 同时触及按 stop-first。
- stop/target 被 open 穿越时按 open 市价成交；timeout 下一根 open 退出。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 数据

- 覆盖：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`，`112822` 根 K。
- 缺口：`0`；OHLCV 硬违规：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。

## V1 基线

- trades `188`，trades/day `0.48`，ann `1.32x`。
- win `85.11%`，PF `1.468`，avg trade `16.67 bps`，maxDD `-8.16%`。
- VAL PF `5.445`，FWD PF `3.550`，recent30 `10.46%`。

## 结论

- V1 的核心不是通用 micro-scalp，而是 `vwap_revert + require_trend=true + EMA21/96 trend gate + 75 bps VWAP deviation` 的低频均值回归。
- 最脆弱参数是 `entry_style`、`require_trend`、`ema_slow` 和 `vwap_dev_bps`：改变这些参数会明显抬高频率、恶化 PF 或直接把策略打成亏损。
- `bb_z`、`rsi_*`、`donchian`、`wick_atr`、`pullback_bps`、`breakout_bps`、`min_dir_roc_bps`、`max_counter_roc_bps` 等字段在当前 `vwap_revert` 风格下大多是 dormant 参数；它们只有切换 entry style 后才真正参与信号。
- `sl_bps=400`、`max_dist_ema_bps=130`、较短 `max_hold_bars`、较低 `max_atr_pct_bps` 等变体在本轮更好，但这些是后续 V1.1 候选，不应在逐笔路径、订单维护、重启恢复和 paper/live reconciliation 前替代 V1。
- 结论状态维持 `audit candidate only / not live-ready`。

## 参数组摘要

| parameter | variants | robust-like | best ann | best PF | worst ann |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cooldown_bars` | `5` | `5` | `1.31x` | `1.449` | `1.21x` |
| `sl_bps` | `4` | `4` | `1.50x` | `1.785` | `1.16x` |
| `max_dist_ema_bps` | `4` | `4` | `1.40x` | `1.705` | `1.30x` |
| `max_hold_bars` | `4` | `4` | `1.36x` | `1.566` | `1.34x` |
| `min_adx` | `5` | `4` | `1.35x` | `1.648` | `1.04x` |
| `close_pos` | `4` | `4` | `1.33x` | `1.526` | `1.09x` |
| `bb_z` | `4` | `4` | `1.32x` | `1.468` | `1.32x` |
| `breakout_bps` | `4` | `4` | `1.32x` | `1.468` | `1.32x` |
| `min_dir_roc_bps` | `4` | `4` | `1.32x` | `1.468` | `1.32x` |
| `min_atr_pct_bps` | `4` | `4` | `1.32x` | `1.625` | `1.27x` |
| `min_rvol` | `4` | `4` | `1.32x` | `2.028` | `1.30x` |
| `tp_bps` | `5` | `4` | `1.30x` | `1.517` | `1.26x` |
| `max_atr_pct_bps` | `3` | `3` | `1.36x` | `1.532` | `1.35x` |
| `max_counter_roc_bps` | `3` | `3` | `1.32x` | `1.468` | `1.32x` |
| `pullback_bps` | `3` | `3` | `1.32x` | `1.468` | `1.32x` |
| `rsi_high` | `3` | `3` | `1.32x` | `1.468` | `1.32x` |
| `rsi_low` | `3` | `3` | `1.32x` | `1.468` | `1.32x` |
| `ema_htf` | `2` | `2` | `1.33x` | `1.477` | `1.33x` |
| `donchian` | `2` | `2` | `1.32x` | `1.468` | `1.32x` |
| `rsi_window` | `2` | `2` | `1.32x` | `1.468` | `1.32x` |
| `wick_atr` | `2` | `2` | `1.32x` | `1.468` | `1.32x` |
| `side_mode` | `2` | `2` | `1.19x` | `1.580` | `1.10x` |
| `require_macd_turn` | `1` | `1` | `1.31x` | `1.716` | `1.31x` |
| `require_htf` | `1` | `1` | `1.30x` | `1.713` | `1.30x` |
| `max_chop` | `4` | `1` | `1.13x` | `1.257` | `1.07x` |
| `require_body_dir` | `1` | `1` | `1.11x` | `1.139` | `1.11x` |
| `vwap_dev_bps` | `5` | `1` | `1.09x` | `1.347` | `0.91x` |
| `ema_fast` | `3` | `1` | `1.06x` | `1.222` | `1.00x` |
| `ema_slow` | `3` | `0` | `1.10x` | `1.098` | `0.89x` |
| `entry_style` | `7` | `0` | `0.99x` | `0.929` | `0.08x` |
| `require_trend` | `1` | `0` | `0.29x` | `0.799` | `0.29x` |

## Top Variants

| name | parameter | value | trades/day | ann | PF | win | maxDD | recent30 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1__sl_bps__400.0` | `sl_bps` | `400.0` | `0.48` | `1.50x` | `1.785` | `88.24%` | `-9.95%` | `9.04%` |
| `V1__max_dist_ema_bps__130.0` | `max_dist_ema_bps` | `130.0` | `0.43` | `1.40x` | `1.705` | `86.47%` | `-6.69%` | `9.78%` |
| `V1__max_hold_bars__36` | `max_hold_bars` | `36` | `0.48` | `1.36x` | `1.566` | `82.45%` | `-8.16%` | `10.46%` |
| `V1__max_atr_pct_bps__220.0` | `max_atr_pct_bps` | `220.0` | `0.48` | `1.36x` | `1.532` | `85.56%` | `-8.16%` | `10.46%` |
| `V1__max_atr_pct_bps__350.0` | `max_atr_pct_bps` | `350.0` | `0.48` | `1.36x` | `1.532` | `85.56%` | `-8.16%` | `10.46%` |
| `V1__max_hold_bars__48` | `max_hold_bars` | `48` | `0.48` | `1.35x` | `1.529` | `83.51%` | `-8.16%` | `10.46%` |
| `V1__max_hold_bars__144` | `max_hold_bars` | `144` | `0.48` | `1.35x` | `1.510` | `85.64%` | `-8.16%` | `10.46%` |
| `V1__max_atr_pct_bps__160.0` | `max_atr_pct_bps` | `160.0` | `0.47` | `1.35x` | `1.522` | `85.48%` | `-8.16%` | `10.46%` |
| `V1__min_adx__18.0` | `min_adx` | `18.0` | `0.41` | `1.35x` | `1.637` | `86.88%` | `-8.17%` | `7.77%` |
| `V1__max_dist_ema_bps__180.0` | `max_dist_ema_bps` | `180.0` | `0.46` | `1.35x` | `1.542` | `85.56%` | `-6.69%` | `9.78%` |
| `V1__sl_bps__300.0` | `sl_bps` | `300.0` | `0.48` | `1.34x` | `1.494` | `86.17%` | `-8.31%` | `10.17%` |
| `V1__max_hold_bars__72` | `max_hold_bars` | `72` | `0.48` | `1.34x` | `1.499` | `84.57%` | `-8.16%` | `10.46%` |
| `V1__min_adx__0.0` | `min_adx` | `0.0` | `0.49` | `1.34x` | `1.486` | `85.26%` | `-8.11%` | `10.46%` |
| `V1__min_adx__10.0` | `min_adx` | `10.0` | `0.49` | `1.34x` | `1.486` | `85.26%` | `-8.11%` | `10.46%` |
| `V1__ema_htf__192` | `ema_htf` | `192` | `0.48` | `1.33x` | `1.477` | `85.19%` | `-8.16%` | `10.46%` |

## Fragile Variants

| name | parameter | value | trades/day | ann | PF | win | maxDD | recent30 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1__entry_style__ema_reclaim` | `entry_style` | `ema_reclaim` | `2.54` | `0.08x` | `0.629` | `72.03%` | `-93.41%` | `-32.35%` |
| `V1__entry_style__momentum_pause` | `entry_style` | `momentum_pause` | `2.40` | `0.15x` | `0.689` | `73.83%` | `-86.92%` | `-27.61%` |
| `V1__entry_style__micro_breakout` | `entry_style` | `micro_breakout` | `1.81` | `0.28x` | `0.714` | `74.44%` | `-76.92%` | `-14.40%` |
| `V1__require_trend__False` | `require_trend` | `False` | `2.64` | `0.29x` | `0.799` | `76.23%` | `-74.56%` | `-12.62%` |
| `V1__entry_style__trend_rsi_snapback` | `entry_style` | `trend_rsi_snapback` | `1.13` | `0.77x` | `0.899` | `78.91%` | `-53.09%` | `19.96%` |
| `V1__ema_slow__192` | `ema_slow` | `192` | `0.83` | `0.89x` | `0.941` | `78.70%` | `-31.39%` | `5.62%` |
| `V1__entry_style__macd_flip` | `entry_style` | `macd_flip` | `0.47` | `0.89x` | `0.896` | `79.03%` | `-25.03%` | `-0.29%` |
| `V1__ema_slow__55` | `ema_slow` | `55` | `0.32` | `0.90x` | `0.854` | `77.95%` | `-18.55%` | `1.56%` |
| `V1__vwap_dev_bps__50.0` | `vwap_dev_bps` | `50.0` | `0.71` | `0.91x` | `0.948` | `79.50%` | `-25.31%` | `-0.59%` |
| `V1__entry_style__bb_revert` | `entry_style` | `bb_revert` | `0.38` | `0.94x` | `0.929` | `80.00%` | `-22.98%` | `5.30%` |
| `V1__vwap_dev_bps__200.0` | `vwap_dev_bps` | `200.0` | `0.03` | `0.95x` | `0.496` | `69.23%` | `-7.04%` | `0.62%` |
| `V1__vwap_dev_bps__35.0` | `vwap_dev_bps` | `35.0` | `0.84` | `0.96x` | `0.987` | `80.36%` | `-28.88%` | `5.49%` |

## 产物

- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_full_ablation_summary_2026-06-29.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_full_ablation_monthly_2026-06-29.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_full_ablation_2026-06-29.json`
