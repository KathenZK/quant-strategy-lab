# HYPE 5m Micro-Scalp relaxed rounds 2026-06-26

Family id: `HYPE-5M-Micro-Scalp`

目标：按用户要求逐步放松单个约束，寻找能够盈利且真实线上可跑的 Binance HYPEUSDT `5m` 策略候选。

## 固定不放松的部分

- 数据质量仍使用完整 Binance HYPEUSDT 永续 `5m` normalized OHLCV。
- 信号仍只使用已收盘 K，下一根 open 入场。
- 入场后仍立即有固定 TP/SL bracket。
- 同 K 同时触及 TP/SL 仍按止损先成交。
- stop/target 被 open 穿越仍按 open 市价成交。
- timeout 仍按下一根 open 退出。
- 成本仍扣 observed live cost：fee `4.1466 bps/fill`，entry slippage `10.73 bps`，exit slippage `-2.64 bps`。

## 数据质量

- 覆盖：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`，`112822` 根 K。
- 缺口：`0`；重复：`0`；OHLC/VWAP/volume 硬违规：`{'high_lt_max_open_close': 0, 'low_gt_min_open_close': 0, 'nonpositive_ohlc': 0, 'negative_volume': 0, 'negative_quote_volume': 0, 'vwap_outside_hilo_nonzero_vol': 0}`。

## 分轮结果

### R1_relax_frequency

只放松交易频率：从每天 3-5 笔降到每天 0.10-1.00 笔，保留正收益、较高胜率、低回撤和 VAL/FWD 要求。

- 搜索配置数：`7000`。
- round gate 通过数：`32`。

本轮 gate 通过配置：
| round | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R1_relax_frequency` | `R1_relax_frequency_R06679` | `vwap_revert` | `both` | `0.15` | `59` | `1.29x` | `91.53%` | `3.896` | `46.58 bps` | `-5.02%` | `inf` | `inf` | `4.96%` |
| `R1_relax_frequency` | `R1_relax_frequency_M00079` | `bb_revert` | `short` | `0.10` | `41` | `1.11x` | `85.37%` | `2.414` | `27.18 bps` | `-3.58%` | `39.403` | `inf` | `2.19%` |
| `R1_relax_frequency` | `R1_relax_frequency_R01159` | `bb_revert` | `both` | `0.16` | `64` | `1.40x` | `79.69%` | `2.082` | `57.77 bps` | `-10.81%` | `5.400` | `inf` | `7.92%` |
| `R1_relax_frequency` | `R1_relax_frequency_R06015` | `bb_revert` | `both` | `0.14` | `56` | `1.28x` | `80.36%` | `2.126` | `48.54 bps` | `-9.08%` | `inf` | `inf` | `7.06%` |
| `R1_relax_frequency` | `R1_relax_frequency_R04210` | `trend_rsi_snapback` | `short` | `0.19` | `73` | `1.04x` | `78.08%` | `1.169` | `6.13 bps` | `-11.42%` | `inf` | `inf` | `3.31%` |
| `R1_relax_frequency` | `R1_relax_frequency_R05680` | `vwap_revert` | `short` | `0.15` | `57` | `1.02x` | `87.72%` | `1.128` | `4.41 bps` | `-10.68%` | `4.274` | `inf` | `2.69%` |
| `R1_relax_frequency` | `R1_relax_frequency_R00952` | `bb_revert` | `short` | `0.19` | `74` | `1.14x` | `71.62%` | `1.704` | `19.82 bps` | `-6.37%` | `19.706` | `2.330` | `3.93%` |
| `R1_relax_frequency` | `R1_relax_frequency_R05368` | `bb_revert` | `both` | `0.13` | `50` | `1.11x` | `86.00%` | `1.612` | `22.63 bps` | `-8.12%` | `2.269` | `inf` | `2.80%` |
| `R1_relax_frequency` | `R1_relax_frequency_R03395` | `bb_revert` | `both` | `0.13` | `49` | `1.03x` | `75.51%` | `1.145` | `8.02 bps` | `-11.39%` | `2.617` | `inf` | `4.29%` |
| `R1_relax_frequency` | `R1_relax_frequency_R01499` | `wick_reject` | `long` | `0.27` | `107` | `1.21x` | `57.94%` | `1.308` | `19.88 bps` | `-17.73%` | `4.030` | `2.118` | `8.16%` |
| `R1_relax_frequency` | `R1_relax_frequency_R03235` | `vwap_revert` | `long` | `0.33` | `129` | `1.10x` | `63.57%` | `1.166` | `9.09 bps` | `-15.88%` | `4.339` | `2.181` | `4.05%` |
| `R1_relax_frequency` | `R1_relax_frequency_R02394` | `trend_rsi_snapback` | `long` | `0.30` | `118` | `1.16x` | `85.59%` | `1.573` | `13.76 bps` | `-6.99%` | `1.411` | `inf` | `4.06%` |

### R2_relax_winrate_payoff

在低频基础上放松胜率，允许 45%+ 胜率，但要求 PF/payoff 更高，尝试更宽 TP 捕捉较大单笔空间。

- 搜索配置数：`7000`。
- round gate 通过数：`20`。

本轮 gate 通过配置：
| round | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R00356` | `vwap_revert` | `both` | `0.13` | `50` | `1.25x` | `58.00%` | `1.762` | `49.29 bps` | `-5.76%` | `13.356` | `2.943` | `6.22%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R05981` | `vwap_revert` | `long` | `0.15` | `59` | `1.17x` | `61.02%` | `1.480` | `29.88 bps` | `-10.77%` | `3.035` | `inf` | `6.92%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R02890` | `macd_flip` | `both` | `0.17` | `67` | `1.49x` | `49.25%` | `1.733` | `68.50 bps` | `-14.02%` | `2.594` | `7.238` | `14.59%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R03992` | `vwap_revert` | `long` | `0.19` | `76` | `1.27x` | `59.21%` | `1.515` | `36.31 bps` | `-10.11%` | `10.321` | `2.128` | `6.09%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R05547` | `bb_revert` | `long` | `0.14` | `54` | `1.14x` | `59.26%` | `1.489` | `26.33 bps` | `-5.82%` | `3.730` | `2.025` | `2.76%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R06914` | `vwap_revert` | `short` | `0.16` | `61` | `1.23x` | `49.18%` | `1.309` | `41.88 bps` | `-17.39%` | `inf` | `2.063` | `6.30%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R06879` | `momentum_pause` | `short` | `0.29` | `112` | `1.13x` | `56.25%` | `1.272` | `12.51 bps` | `-10.85%` | `1.603` | `7.678` | `3.90%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R00322` | `vwap_revert` | `short` | `0.25` | `99` | `1.30x` | `58.59%` | `1.621` | `29.74 bps` | `-9.03%` | `6.966` | `1.013` | `0.92%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R05586` | `bb_revert` | `both` | `0.17` | `65` | `1.06x` | `46.15%` | `1.187` | `9.80 bps` | `-12.05%` | `1.202` | `14.931` | `7.51%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R00444` | `vwap_revert` | `short` | `0.23` | `91` | `1.24x` | `51.65%` | `1.310` | `28.46 bps` | `-15.90%` | `1.256` | `3.350` | `10.88%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R05814` | `vwap_revert` | `short` | `0.19` | `74` | `1.28x` | `60.81%` | `1.446` | `38.92 bps` | `-11.42%` | `2.183` | `1.730` | `4.84%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R02941` | `bb_revert` | `short` | `0.25` | `97` | `1.28x` | `51.55%` | `1.374` | `28.60 bps` | `-11.55%` | `2.718` | `1.078` | `2.74%` |

### R3_live_candidate_gate

以真实线上可跑为目标：不限高胜率和微利叙事，只要求可执行、正收益、VAL/FWD 不坏、近 30 天不明显失效。

- 搜索配置数：`7000`。
- round gate 通过数：`36`。

本轮 gate 通过配置：
| round | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R03936` | `trend_rsi_snapback` | `short` | `0.08` | `31` | `1.10x` | `96.77%` | `4.353` | `33.06 bps` | `-3.57%` | `inf` | `inf` | `1.34%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R04150` | `vwap_revert` | `both` | `0.12` | `46` | `1.12x` | `91.30%` | `2.811` | `26.09 bps` | `-2.41%` | `inf` | `inf` | `2.24%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R02591` | `vwap_revert` | `long` | `0.08` | `32` | `1.15x` | `90.62%` | `2.667` | `47.78 bps` | `-5.17%` | `inf` | `inf` | `4.29%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R05312` | `vwap_revert` | `short` | `0.09` | `34` | `1.06x` | `88.24%` | `1.496` | `20.30 bps` | `-8.34%` | `inf` | `inf` | `1.39%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R05841` | `vwap_revert` | `short` | `0.09` | `37` | `1.09x` | `56.76%` | `1.708` | `26.56 bps` | `-4.79%` | `23.067` | `3.826` | `2.67%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R02388` | `vwap_revert` | `short` | `0.15` | `60` | `1.05x` | `81.67%` | `1.305` | `8.47 bps` | `-8.06%` | `4.623` | `inf` | `1.79%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R06062` | `trend_rsi_snapback` | `long` | `0.11` | `42` | `1.07x` | `61.90%` | `1.460` | `17.18 bps` | `-7.79%` | `6.289` | `inf` | `3.94%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R00465` | `vwap_revert` | `both` | `0.13` | `51` | `1.07x` | `82.35%` | `1.305` | `16.25 bps` | `-12.69%` | `4.472` | `inf` | `4.29%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R03689` | `bb_revert` | `short` | `0.12` | `47` | `1.09x` | `51.06%` | `1.410` | `20.53 bps` | `-5.10%` | `3.750` | `4.383` | `3.60%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R00865` | `bb_revert` | `long` | `0.15` | `58` | `1.11x` | `63.79%` | `1.300` | `21.14 bps` | `-15.60%` | `3.416` | `inf` | `6.32%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R03904` | `vwap_revert` | `long` | `0.10` | `41` | `1.13x` | `73.17%` | `1.644` | `32.77 bps` | `-10.89%` | `2.907` | `inf` | `5.85%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R05626` | `bb_revert` | `both` | `0.44` | `171` | `1.07x` | `90.06%` | `1.175` | `4.60 bps` | `-10.36%` | `2.316` | `inf` | `4.92%` |

## 候选月度审计

- round-gate 候选数：`88`。
- live-candidate 初筛通过数：`81`。

| round | name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R03936` | `trend_rsi_snapback` | `short` | `0.08` | `31` | `1.10x` | `96.77%` | `4.353` | `33.06 bps` | `-3.57%` | `inf` | `inf` | `1.34%` |
| `R1_relax_frequency` | `R1_relax_frequency_R06679` | `vwap_revert` | `both` | `0.15` | `59` | `1.29x` | `91.53%` | `3.896` | `46.58 bps` | `-5.02%` | `inf` | `inf` | `4.96%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R04150` | `vwap_revert` | `both` | `0.12` | `46` | `1.12x` | `91.30%` | `2.811` | `26.09 bps` | `-2.41%` | `inf` | `inf` | `2.24%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R02591` | `vwap_revert` | `long` | `0.08` | `32` | `1.15x` | `90.62%` | `2.667` | `47.78 bps` | `-5.17%` | `inf` | `inf` | `4.29%` |
| `R1_relax_frequency` | `R1_relax_frequency_M00079` | `bb_revert` | `short` | `0.10` | `41` | `1.11x` | `85.37%` | `2.414` | `27.18 bps` | `-3.58%` | `39.403` | `inf` | `2.19%` |
| `R1_relax_frequency` | `R1_relax_frequency_R01159` | `bb_revert` | `both` | `0.16` | `64` | `1.40x` | `79.69%` | `2.082` | `57.77 bps` | `-10.81%` | `5.400` | `inf` | `7.92%` |
| `R1_relax_frequency` | `R1_relax_frequency_R06015` | `bb_revert` | `both` | `0.14` | `56` | `1.28x` | `80.36%` | `2.126` | `48.54 bps` | `-9.08%` | `inf` | `inf` | `7.06%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R05312` | `vwap_revert` | `short` | `0.09` | `34` | `1.06x` | `88.24%` | `1.496` | `20.30 bps` | `-8.34%` | `inf` | `inf` | `1.39%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R05841` | `vwap_revert` | `short` | `0.09` | `37` | `1.09x` | `56.76%` | `1.708` | `26.56 bps` | `-4.79%` | `23.067` | `3.826` | `2.67%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R02388` | `vwap_revert` | `short` | `0.15` | `60` | `1.05x` | `81.67%` | `1.305` | `8.47 bps` | `-8.06%` | `4.623` | `inf` | `1.79%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R06062` | `trend_rsi_snapback` | `long` | `0.11` | `42` | `1.07x` | `61.90%` | `1.460` | `17.18 bps` | `-7.79%` | `6.289` | `inf` | `3.94%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R00465` | `vwap_revert` | `both` | `0.13` | `51` | `1.07x` | `82.35%` | `1.305` | `16.25 bps` | `-12.69%` | `4.472` | `inf` | `4.29%` |
| `R1_relax_frequency` | `R1_relax_frequency_R04210` | `trend_rsi_snapback` | `short` | `0.19` | `73` | `1.04x` | `78.08%` | `1.169` | `6.13 bps` | `-11.42%` | `inf` | `inf` | `3.31%` |
| `R1_relax_frequency` | `R1_relax_frequency_R05680` | `vwap_revert` | `short` | `0.15` | `57` | `1.02x` | `87.72%` | `1.128` | `4.41 bps` | `-10.68%` | `4.274` | `inf` | `2.69%` |
| `R3_live_candidate_gate` | `R3_live_candidate_gate_R03689` | `bb_revert` | `short` | `0.12` | `47` | `1.09x` | `51.06%` | `1.410` | `20.53 bps` | `-5.10%` | `3.750` | `4.383` | `3.60%` |
| `R2_relax_winrate_payoff` | `R2_relax_winrate_payoff_R00356` | `vwap_revert` | `both` | `0.13` | `50` | `1.25x` | `58.00%` | `1.762` | `49.29 bps` | `-5.76%` | `13.356` | `2.943` | `6.22%` |

### Live-Candidate 初筛

- `R3_live_candidate_gate_R03936`：ann `1.10x`，PF `4.353`，maxDD `-3.57%`，负收益月份 `1/14`，最差月 `-2.20%`。
- `R1_relax_frequency_R06679`：ann `1.29x`，PF `3.896`，maxDD `-5.02%`，负收益月份 `0/14`，最差月 `0.00%`。
- `R3_live_candidate_gate_R04150`：ann `1.12x`，PF `2.811`，maxDD `-2.41%`，负收益月份 `3/14`，最差月 `-1.99%`。
- `R3_live_candidate_gate_R02591`：ann `1.15x`，PF `2.667`，maxDD `-5.17%`，负收益月份 `3/14`，最差月 `-3.06%`。
- `R1_relax_frequency_M00079`：ann `1.11x`，PF `2.414`，maxDD `-3.58%`，负收益月份 `2/14`，最差月 `-1.50%`。
- `R1_relax_frequency_R01159`：ann `1.40x`，PF `2.082`，maxDD `-10.81%`，负收益月份 `3/14`，最差月 `-2.07%`。
- `R1_relax_frequency_R06015`：ann `1.28x`，PF `2.126`，maxDD `-9.08%`，负收益月份 `3/14`，最差月 `-4.12%`。
- `R3_live_candidate_gate_R05312`：ann `1.06x`，PF `1.496`，maxDD `-8.34%`，负收益月份 `2/14`，最差月 `-6.02%`。

## 结论

出现可进入下一步 paper audit / live-spec 草案的初筛候选；仍需参数邻域、逐笔路径图、订单维护与重启恢复审计后才能真实资金运行。

## 产物

- JSON：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_relaxed_rounds_2026-06-26.json`
- 全量 summary：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_relaxed_rounds_summary_2026-06-26.csv`
- 候选表：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_relaxed_rounds_candidates_2026-06-26.csv`
- 月度审计：`research/hype/5m-micro-scalp/artifacts/hype_5m_micro_scalp_relaxed_rounds_monthly_2026-06-26.csv`
