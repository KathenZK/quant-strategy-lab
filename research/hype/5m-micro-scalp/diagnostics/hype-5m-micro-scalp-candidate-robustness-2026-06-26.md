# HYPE 5m Micro-Scalp candidate robustness 2026-06-26

Family id: `HYPE-5M-Micro-Scalp`

目标：围绕 relaxed-rounds 里交易数相对足够的候选做参数邻域复核，判断是否只是单点碰巧。

## 固定执行口径

- 闭合 K 信号；下一根 open 入场。
- 入场即固定 TP/SL bracket；同 K 同时触及按止损先成交。
- stop/target open 穿越按 open 市价成交；timeout 下一根 open 退出。
- 成本：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 数据

- `2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`，missing `0`，OHLC/VWAP/volume hard violations `{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。

## 邻域结果

- 测试邻域配置：`749`。
- robust gate 通过：`407`。
- robust + monthly gate 通过：`396`。

### R1_relax_frequency_R01242

- configs `190`；robust gate `130`；monthly pass `129`。

| base | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__tp_sl_0011` | `vwap_revert` | `both` | `0.48` | `188` | `1.32x` | `85.11%` | `1.468` | `16.67 bps` | `-8.16%` | `5.445` | `3.550` | `10.46%` | `3` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__regime_0179` | `vwap_revert` | `both` | `0.14` | `55` | `1.04x` | `76.36%` | `1.178` | `7.82 bps` | `-9.27%` | `8.080` | `inf` | `2.80%` | `6` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__regime_0178` | `vwap_revert` | `both` | `0.09` | `37` | `1.01x` | `72.97%` | `1.078` | `3.68 bps` | `-7.97%` | `6.926` | `inf` | `1.39%` | `7` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__regime_0173` | `vwap_revert` | `both` | `0.13` | `50` | `1.01x` | `74.00%` | `1.063` | `3.05 bps` | `-10.37%` | `8.080` | `inf` | `2.09%` | `6` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__regime_0159` | `vwap_revert` | `both` | `0.13` | `52` | `1.00x` | `73.08%` | `0.999` | `-0.07 bps` | `-12.14%` | `8.080` | `inf` | `2.09%` | `5` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__regime_0169` | `vwap_revert` | `both` | `0.13` | `52` | `1.00x` | `73.08%` | `0.999` | `-0.07 bps` | `-12.14%` | `8.080` | `inf` | `2.09%` | `5` |

### R1_relax_frequency_R03831

- configs `180`；robust gate `55`；monthly pass `52`。

| base | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R1_relax_frequency_R03831` | `R1_relax_frequency_R03831__regime_0163` | `bb_revert` | `both` | `0.10` | `41` | `1.18x` | `70.73%` | `1.820` | `45.44 bps` | `-8.55%` | `1.724` | `inf` | `3.11%` | `4` |
| `R1_relax_frequency_R03831` | `R1_relax_frequency_R03831__regime_0159` | `bb_revert` | `both` | `0.10` | `41` | `1.18x` | `70.73%` | `1.820` | `45.44 bps` | `-8.55%` | `1.724` | `inf` | `3.11%` | `4` |
| `R1_relax_frequency_R03831` | `R1_relax_frequency_R03831__regime_0168` | `bb_revert` | `both` | `0.10` | `41` | `1.18x` | `70.73%` | `1.820` | `45.44 bps` | `-8.55%` | `1.724` | `inf` | `3.11%` | `4` |
| `R1_relax_frequency_R03831` | `R1_relax_frequency_R03831__ema_0070` | `bb_revert` | `both` | `0.06` | `22` | `1.17x` | `77.27%` | `2.866` | `77.64 bps` | `-5.76%` | `1.293` | `0.684` | `-0.75%` | `-` |
| `R1_relax_frequency_R03831` | `R1_relax_frequency_R03831__trigger_0154` | `bb_revert` | `both` | `0.31` | `121` | `1.17x` | `61.98%` | `1.209` | `15.81 bps` | `-20.59%` | `1.794` | `2.052` | `6.35%` | `-` |
| `R1_relax_frequency_R03831` | `R1_relax_frequency_R03831__trigger_0151` | `bb_revert` | `both` | `0.47` | `185` | `1.33x` | `61.62%` | `1.248` | `18.01 bps` | `-13.37%` | `1.383` | `1.824` | `8.84%` | `6` |

### R2_relax_winrate_payoff_R04600

- configs `187`；robust gate `133`；monthly pass `130`。

| base | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R2_relax_winrate_payoff_R04600` | `R2_relax_winrate_payoff_R04600__tp_sl_0035` | `bb_revert` | `long` | `0.30` | `117` | `1.57x` | `57.26%` | `1.488` | `45.24 bps` | `-19.53%` | `1.929` | `3.368` | `20.15%` | `4` |
| `R2_relax_winrate_payoff_R04600` | `R2_relax_winrate_payoff_R04600__tp_sl_0029` | `bb_revert` | `long` | `0.30` | `117` | `1.54x` | `58.12%` | `1.474` | `43.33 bps` | `-19.53%` | `1.929` | `3.316` | `19.67%` | `4` |
| `R2_relax_winrate_payoff_R04600` | `R2_relax_winrate_payoff_R04600__tp_sl_0023` | `bb_revert` | `long` | `0.30` | `117` | `1.57x` | `58.97%` | `1.489` | `44.65 bps` | `-18.61%` | `1.929` | `3.205` | `18.67%` | `4` |
| `R2_relax_winrate_payoff_R04600` | `R2_relax_winrate_payoff_R04600__tp_sl_0017` | `bb_revert` | `long` | `0.30` | `117` | `1.63x` | `59.83%` | `1.531` | `48.15 bps` | `-18.92%` | `1.929` | `3.008` | `16.88%` | `4` |
| `R2_relax_winrate_payoff_R04600` | `R2_relax_winrate_payoff_R04600__tp_sl_0005` | `bb_revert` | `long` | `0.30` | `118` | `1.45x` | `59.32%` | `1.441` | `36.63 bps` | `-13.22%` | `2.204` | `2.772` | `12.69%` | `5` |
| `R2_relax_winrate_payoff_R04600` | `R2_relax_winrate_payoff_R04600__tp_sl_0012` | `bb_revert` | `long` | `0.30` | `117` | `1.49x` | `59.83%` | `1.442` | `40.06 bps` | `-19.23%` | `2.200` | `2.762` | `14.67%` | `5` |

### R3_live_candidate_gate_R03979

- configs `192`；robust gate `89`；monthly pass `85`。

| base | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0005` | `vwap_revert` | `both` | `0.45` | `175` | `1.27x` | `86.86%` | `1.538` | `15.38 bps` | `-9.16%` | `3.325` | `9.568` | `3.79%` | `5` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__bool_0189` | `vwap_revert` | `both` | `0.02` | `7` | `1.05x` | `100.00%` | `inf` | `69.34 bps` | `-1.77%` | `inf` | `0.000` | `0.00%` | `0` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__dist_0136` | `vwap_revert` | `both` | `0.16` | `64` | `1.18x` | `85.94%` | `1.930` | `28.71 bps` | `-5.31%` | `2.724` | `inf` | `2.80%` | `3` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0006` | `vwap_revert` | `both` | `0.45` | `175` | `1.25x` | `86.86%` | `1.479` | `14.24 bps` | `-10.12%` | `3.325` | `9.568` | `3.79%` | `5` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__dist_0135` | `vwap_revert` | `both` | `0.16` | `63` | `1.17x` | `85.71%` | `1.895` | `28.07 bps` | `-5.31%` | `2.724` | `inf` | `2.80%` | `3` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__dist_0134` | `vwap_revert` | `both` | `0.16` | `63` | `1.17x` | `85.71%` | `1.895` | `28.07 bps` | `-5.31%` | `2.724` | `inf` | `2.80%` | `3` |

## Robust Monthly Pass Top

| base | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 | neg months |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__tp_sl_0011` | `vwap_revert` | `both` | `0.48` | `188` | `1.32x` | `85.11%` | `1.468` | `16.67 bps` | `-8.16%` | `5.445` | `3.550` | `10.46%` | `3` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0005` | `vwap_revert` | `both` | `0.45` | `175` | `1.27x` | `86.86%` | `1.538` | `15.38 bps` | `-9.16%` | `3.325` | `9.568` | `3.79%` | `5` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0006` | `vwap_revert` | `both` | `0.45` | `175` | `1.25x` | `86.86%` | `1.479` | `14.24 bps` | `-10.12%` | `3.325` | `9.568` | `3.79%` | `5` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0004` | `vwap_revert` | `both` | `0.45` | `175` | `1.21x` | `86.86%` | `1.382` | `12.14 bps` | `-10.69%` | `3.325` | `9.568` | `3.79%` | `4` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__tp_sl_0012` | `vwap_revert` | `both` | `0.48` | `188` | `1.32x` | `86.70%` | `1.461` | `16.81 bps` | `-8.27%` | `4.688` | `2.994` | `9.83%` | `4` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__tp_sl_0005` | `vwap_revert` | `both` | `0.48` | `188` | `1.26x` | `87.77%` | `1.451` | `13.80 bps` | `-7.28%` | `4.454` | `2.904` | `7.89%` | `2` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0027` | `vwap_revert` | `both` | `0.43` | `168` | `1.37x` | `78.57%` | `1.447` | `21.37 bps` | `-12.00%` | `2.724` | `16.660` | `6.93%` | `3` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0028` | `vwap_revert` | `both` | `0.43` | `168` | `1.42x` | `78.57%` | `1.520` | `23.67 bps` | `-11.43%` | `2.565` | `16.660` | `6.93%` | `2` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0022` | `vwap_revert` | `both` | `0.43` | `170` | `1.42x` | `81.76%` | `1.585` | `23.19 bps` | `-7.82%` | `2.400` | `14.533` | `5.98%` | `3` |
| `R1_relax_frequency_R01242` | `R1_relax_frequency_R01242__bool_0183` | `vwap_revert` | `both` | `0.34` | `133` | `1.19x` | `78.95%` | `1.365` | `14.49 bps` | `-10.36%` | `4.368` | `2.877` | `6.03%` | `5` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0021` | `vwap_revert` | `both` | `0.43` | `170` | `1.36x` | `81.76%` | `1.487` | `20.56 bps` | `-8.99%` | `2.554` | `14.533` | `5.98%` | `3` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0016` | `vwap_revert` | `both` | `0.44` | `172` | `1.35x` | `83.14%` | `1.518` | `19.63 bps` | `-7.89%` | `2.166` | `13.114` | `5.35%` | `2` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0029` | `vwap_revert` | `both` | `0.43` | `168` | `1.36x` | `78.57%` | `1.427` | `20.70 bps` | `-13.29%` | `2.338` | `16.660` | `6.93%` | `2` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0023` | `vwap_revert` | `both` | `0.43` | `170` | `1.37x` | `81.76%` | `1.496` | `20.84 bps` | `-8.79%` | `2.180` | `14.533` | `5.98%` | `3` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0015` | `vwap_revert` | `both` | `0.44` | `172` | `1.30x` | `83.14%` | `1.421` | `17.03 bps` | `-9.06%` | `2.305` | `13.114` | `5.35%` | `4` |
| `R3_live_candidate_gate_R03979` | `R3_live_candidate_gate_R03979__tp_sl_0033` | `vwap_revert` | `both` | `0.43` | `168` | `1.43x` | `74.40%` | `1.436` | `24.04 bps` | `-13.89%` | `2.188` | `20.206` | `8.53%` | `3` |

## 结论

邻域复核留下多个可推进候选；下一步应针对最稳的 1-2 个生成逐笔路径图、audit runner 和 live spec 草案。

## 产物

- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_candidate_robustness_2026-06-26.json`
- Summary CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_candidate_robustness_summary_2026-06-26.csv`
- Monthly CSV：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_candidate_robustness_monthly_2026-06-26.csv`
