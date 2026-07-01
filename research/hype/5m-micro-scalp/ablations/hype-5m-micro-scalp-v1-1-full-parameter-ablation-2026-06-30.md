# HYPE-5M-Micro-Scalp-V1.1 全参数消融 2026-06-30

Family id：`HYPE-5M-Micro-Scalp`

本报告将 `V1S_rand_016782__N00596` 正式记录为 `HYPE-5M-Micro-Scalp-V1.1` 后，对 `ScalpConfig` 的全部字段做 one-at-a-time 消融。状态仍为 `paper-audit observation / not live-ready`。

## 数据与执行

- 数据：Binance HYPEUSDT perpetual `5m`，`2025-05-30 10:30:00+00:00` 到 `2026-06-30 06:15:00+00:00`，`113998` 根 K。
- 缺口 `0`；OHLC/VWAP/volume 硬违规：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。
- raw/normalized 对齐：`{'raw_files': 397, 'normalized_rows': 113998, 'raw_rows': 113998, 'merged_rows': 113998, 'timestamp_mismatch': 0, 'field_mismatches': {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'quote_volume': 0, 'trade_count': 0, 'vwap': 0, 'is_closed': 0}, 'max_abs_diff': {'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0, 'is_closed': 0.0}}`。
- 信号闭合 K，下一根 open 入场；入场即固定 TP/SL bracket；同 K 同时触及按 stop-first；timeout 下一根 open。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## V1.1 基线

- trades `182`，trades/day `0.46`，ann `2.13x`。
- win `87.91%`，PF `2.660`，avg `45.88 bps`，maxDD `-8.06%`。
- VAL PF `2.441`，FWD PF `5.739`，recent30 `11.86%`。

## 无效或 dormant 参数

- 完全无影响参数组：`bb_z, breakout_bps, min_dir_roc_bps, max_counter_roc_bps, pullback_bps, rsi_high, rsi_low, donchian, rsi_window, wick_atr`。
- 解释：V1.1 固定 `entry_style=vwap_revert`，所以上述 RSI/Bollinger/Donchian/wick/pullback/breakout/momentum-pause 相关字段不参与当前信号；它们只有切换入场风格后才有效。

## 参数组摘要

| parameter | variants | identical | best ann | best PF | best DD | worst ann |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bb_z` | `4` | `4` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `breakout_bps` | `4` | `4` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `min_dir_roc_bps` | `4` | `4` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `max_counter_roc_bps` | `3` | `3` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `pullback_bps` | `3` | `3` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `rsi_high` | `3` | `3` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `rsi_low` | `3` | `3` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `donchian` | `2` | `2` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `max_atr_pct_bps` | `3` | `2` | `2.13x` | `2.660` | `-8.06%` | `2.12x` |
| `rsi_window` | `2` | `2` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `wick_atr` | `2` | `2` | `2.13x` | `2.660` | `-8.06%` | `2.13x` |
| `min_adx` | `4` | `1` | `2.13x` | `2.660` | `-8.06%` | `1.65x` |
| `ema_slow` | `3` | `0` | `2.28x` | `2.824` | `-7.22%` | `1.38x` |
| `tp_bps` | `4` | `0` | `2.22x` | `2.315` | `-7.37%` | `1.70x` |
| `max_hold_bars` | `4` | `0` | `2.17x` | `2.625` | `-6.99%` | `1.45x` |
| `require_body_dir` | `1` | `0` | `2.16x` | `2.485` | `-12.79%` | `2.16x` |
| `sl_bps` | `3` | `0` | `2.14x` | `2.628` | `-8.43%` | `1.53x` |
| `cooldown_bars` | `5` | `0` | `2.12x` | `2.576` | `-8.06%` | `1.72x` |
| `ema_fast` | `3` | `0` | `2.12x` | `2.671` | `-9.39%` | `1.59x` |
| `max_dist_ema_bps` | `5` | `0` | `2.10x` | `2.478` | `-8.62%` | `1.83x` |
| `ema_htf` | `2` | `0` | `2.09x` | `2.797` | `-7.82%` | `1.58x` |
| `max_chop` | `5` | `0` | `2.09x` | `2.636` | `-8.06%` | `1.43x` |
| `min_rvol` | `4` | `0` | `2.09x` | `2.032` | `-11.04%` | `1.33x` |
| `require_trend` | `1` | `0` | `2.08x` | `1.777` | `-19.48%` | `2.08x` |
| `min_atr_pct_bps` | `4` | `0` | `2.07x` | `2.566` | `-8.43%` | `1.61x` |
| `require_htf` | `1` | `0` | `2.06x` | `2.078` | `-14.24%` | `2.06x` |
| `vwap_dev_bps` | `6` | `0` | `2.01x` | `3.123` | `-7.40%` | `1.21x` |
| `require_macd_turn` | `1` | `0` | `1.97x` | `1.957` | `-10.75%` | `1.97x` |
| `close_pos` | `4` | `0` | `1.83x` | `2.438` | `-10.28%` | `1.38x` |
| `side_mode` | `2` | `0` | `1.60x` | `4.285` | `-4.89%` | `1.36x` |
| `entry_style` | `7` | `0` | `1.05x` | `inf` | `-3.15%` | `0.38x` |

## Top One-At-A-Time Variants

| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.1__ema_slow__288` | `ema_slow=288` | `0.60` | `237` | `2.28x` | `2.172` | `85.65%` | `38.56 bps` | `-15.19%` | `2.988` | `4.339` | `13.96%` |
| `V1.1__tp_bps__110.0` | `tp_bps=110.0` | `0.46` | `181` | `2.22x` | `2.315` | `83.43%` | `48.75 bps` | `-12.50%` | `2.519` | `3.035` | `10.52%` |
| `V1.1__max_hold_bars__144` | `max_hold_bars=144` | `0.46` | `182` | `2.17x` | `2.625` | `90.11%` | `47.05 bps` | `-7.99%` | `2.262` | `3.804` | `10.58%` |
| `V1.1__require_body_dir__False` | `require_body_dir=False` | `0.49` | `194` | `2.16x` | `2.485` | `87.63%` | `43.82 bps` | `-12.79%` | `2.629` | `6.122` | `12.81%` |
| `V1.1__max_hold_bars__192` | `max_hold_bars=192` | `0.46` | `182` | `2.16x` | `2.555` | `91.21%` | `46.83 bps` | `-6.99%` | `1.661` | `4.209` | `10.95%` |
| `V1.1__sl_bps__400.0` | `sl_bps=400.0` | `0.46` | `184` | `2.14x` | `2.628` | `88.04%` | `45.62 bps` | `-9.06%` | `2.747` | `5.739` | `11.86%` |
| `V1.1__cooldown_bars__36` | `cooldown_bars=36` | `0.47` | `187` | `2.12x` | `2.554` | `87.17%` | `44.36 bps` | `-8.06%` | `2.441` | `5.739` | `11.86%` |
| `V1.1__max_atr_pct_bps__140.0` | `max_atr_pct_bps=140.0` | `0.46` | `181` | `2.12x` | `2.643` | `87.85%` | `45.67 bps` | `-8.06%` | `2.441` | `5.739` | `11.86%` |
| `V1.1__ema_fast__34` | `ema_fast=34` | `0.53` | `208` | `2.12x` | `2.237` | `86.06%` | `39.84 bps` | `-15.61%` | `2.745` | `6.122` | `12.81%` |
| `V1.1__min_adx__14.0` | `min_adx=14.0` | `0.45` | `180` | `2.10x` | `2.626` | `87.78%` | `45.46 bps` | `-8.06%` | `2.441` | `5.739` | `11.86%` |
| `V1.1__tp_bps__130.0` | `tp_bps=130.0` | `0.45` | `179` | `2.10x` | `1.997` | `76.54%` | `46.19 bps` | `-12.33%` | `2.785` | `2.418` | `9.35%` |
| `V1.1__max_dist_ema_bps__260.0` | `max_dist_ema_bps=260.0` | `0.47` | `187` | `2.10x` | `2.478` | `87.70%` | `43.76 bps` | `-8.62%` | `2.441` | `5.739` | `11.86%` |
| `V1.1__max_dist_ema_bps__400.0` | `max_dist_ema_bps=400.0` | `0.47` | `187` | `2.10x` | `2.478` | `87.70%` | `43.76 bps` | `-8.62%` | `2.441` | `5.739` | `11.86%` |
| `V1.1__max_dist_ema_bps__9999.0` | `max_dist_ema_bps=9999.0` | `0.47` | `187` | `2.10x` | `2.478` | `87.70%` | `43.76 bps` | `-8.62%` | `2.441` | `5.739` | `11.86%` |
| `V1.1__ema_htf__288` | `ema_htf=288` | `0.43` | `170` | `2.09x` | `2.797` | `88.82%` | `47.71 bps` | `-7.99%` | `2.936` | `4.974` | `10.00%` |

## Fragile One-At-A-Time Variants

| name | changed params | trades/day | trades | ann | PF | win | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V1.1__entry_style__momentum_pause` | `entry_style=momentum_pause` | `1.65` | `653` | `0.38x` | `0.814` | `74.58%` | `-14.17 bps` | `-66.01%` | `0.923` | `0.714` | `-14.22%` |
| `V1.1__entry_style__macd_flip` | `entry_style=macd_flip` | `0.79` | `311` | `0.51x` | `0.744` | `73.95%` | `-21.22 bps` | `-52.39%` | `0.746` | `0.967` | `-1.17%` |
| `V1.1__entry_style__micro_breakout` | `entry_style=micro_breakout` | `0.99` | `391` | `0.71x` | `0.886` | `73.91%` | `-7.99 bps` | `-37.64%` | `1.134` | `0.542` | `-14.48%` |
| `V1.1__entry_style__ema_reclaim` | `entry_style=ema_reclaim` | `1.97` | `779` | `0.77x` | `0.969` | `77.02%` | `-2.05 bps` | `-36.93%` | `1.002` | `0.753` | `-12.77%` |
| `V1.1__entry_style__trend_rsi_snapback` | `entry_style=trend_rsi_snapback` | `0.79` | `314` | `0.94x` | `0.991` | `76.75%` | `-0.59 bps` | `-25.87%` | `1.383` | `0.554` | `-11.97%` |
| `V1.1__entry_style__wick_reject` | `entry_style=wick_reject` | `0.01` | `5` | `1.04x` | `inf` | `100.00%` | `84.34 bps` | `-3.15%` | `0.000` | `0.000` | `0.00%` |
| `V1.1__entry_style__bb_revert` | `entry_style=bb_revert` | `0.03` | `13` | `1.05x` | `2.121` | `84.62%` | `37.72 bps` | `-4.97%` | `inf` | `inf` | `1.69%` |
| `V1.1__vwap_dev_bps__140.0` | `vwap_dev_bps=140.0` | `0.10` | `40` | `1.21x` | `3.123` | `92.50%` | `53.04 bps` | `-10.00%` | `inf` | `inf` | `2.55%` |
| `V1.1__min_rvol__1.5` | `min_rvol=1.5` | `0.24` | `94` | `1.33x` | `1.904` | `85.11%` | `33.52 bps` | `-11.04%` | `4.211` | `2.678` | `3.72%` |
| `V1.1__vwap_dev_bps__120.0` | `vwap_dev_bps=120.0` | `0.16` | `65` | `1.36x` | `3.102` | `90.77%` | `51.88 bps` | `-7.40%` | `inf` | `inf` | `4.29%` |
| `V1.1__side_mode__long` | `side_mode=long` | `0.24` | `95` | `1.36x` | `1.997` | `86.32%` | `36.34 bps` | `-11.10%` | `2.035` | `inf` | `6.95%` |
| `V1.1__close_pos__0.58` | `close_pos=0.58` | `0.61` | `241` | `1.38x` | `1.296` | `82.57%` | `15.75 bps` | `-25.30%` | `1.418` | `1.870` | `9.66%` |

## 结论

- V1.1 的有效核心是 `vwap_revert + require_trend=true + EMA21/192/384 + HTF/MACD/body filters + 65 bps VWAP deviation + TP/SL 90/500 bps`。
- 当前消融可直接确认一批 dormant 字段；后续调参应集中在 EMA slow/HTF、VWAP 偏离、ADX/chop/rvol/ATR、EMA 距离、close position、HTF/MACD/body、TP/SL、hold/cooldown。
- 本报告只说明参数敏感性，不构成 live-ready 证明。

## 产物

- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_v1_1_ablation_and_tuning.py`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_full_ablation_summary_2026-06-30.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_full_ablation_monthly_2026-06-30.csv`
- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_v1_1_full_ablation_2026-06-30.json`
