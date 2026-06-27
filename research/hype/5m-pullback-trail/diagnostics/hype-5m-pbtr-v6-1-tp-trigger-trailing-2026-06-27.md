# HYPE-5M-PBTR-V6.1 TP trigger trailing 2026-06-27

Family id：`HYPE-5M-PBTR`

本报告测试“触发止盈后不直接平仓，而是改为 trailing stop 让利润奔跑”。基线为 V6.1：`TP=2.5ATR`、`SL=7ATR`、`timeout=36`、fixed `3x`。

## 近似口径

- 价格触及 `2.5ATR` trigger 前，仍按原始 SL 保护。
- trigger 被触及时不平仓；从下一根 5m K 开始使用 trailing stop。
- trailing stop = `max(initial_stop, entry + lock_atr * ATR, peak - trail_atr * ATR)`。
- 为避免 5m OHLC 中同一根 K 的高低点顺序造成 lookahead，本轮不假设 trigger 当根内能同时完成最优 trailing 保护。
- 所有收益按 fixed `3x` sizing 统计。

## 固定止盈基线

| config | trades | total | max DD | win | PF | payoff | worst | best |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fixed_tp25_3x` | `157` | `408.95%` | `-25.63%` | `63.69%` | `1.773` | `1.011` | `-14.81%` | `9.23%` |

## 收益 Top

| config | trades | total | max DD | win | PF | payoff | worst | best | reasons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `trigger2.5_lock2.5_trail2.5_max36` | `154` | `364.32%` | `-27.70%` | `62.34%` | `1.755` | `1.060` | `-14.81%` | `27.12%` | `{"stop_market": 2, "time_open_untriggered": 68, "trail_gap_open": 55, "trail_stop": 29}` |
| `trigger2.5_lock2.5_trail3_max36` | `154` | `349.44%` | `-28.25%` | `62.34%` | `1.740` | `1.052` | `-14.81%` | `27.87%` | `{"stop_market": 2, "time_open_untriggered": 68, "trail_gap_open": 55, "trail_stop": 29}` |
| `trigger2.5_lock2.5_trail1_max36` | `157` | `340.86%` | `-27.00%` | `63.06%` | `1.710` | `1.002` | `-14.81%` | `9.57%` | `{"stop_market": 2, "time_open_untriggered": 68, "trail_gap_open": 59, "trail_stop": 28}` |
| `trigger2.5_lock2.5_trail1.5_max36` | `157` | `329.78%` | `-27.43%` | `63.06%` | `1.699` | `0.995` | `-14.81%` | `9.72%` | `{"stop_market": 2, "time_open_untriggered": 68, "trail_gap_open": 59, "trail_stop": 28}` |
| `trigger2.5_lock2.5_trail2_max36` | `154` | `321.01%` | `-31.02%` | `61.69%` | `1.694` | `1.052` | `-14.81%` | `28.54%` | `{"stop_market": 2, "time_open_untriggered": 68, "trail_gap_open": 56, "trail_stop": 28}` |
| `trigger2.5_lock2.5_trail4_max36` | `152` | `303.53%` | `-28.82%` | `61.84%` | `1.676` | `1.034` | `-14.81%` | `30.42%` | `{"stop_market": 2, "time_open_triggered": 2, "time_open_untriggered": 68, "trail_gap_open": 54, "trail_stop": 26}` |
| `trigger2.5_lock2_trail1_max36` | `156` | `299.82%` | `-29.97%` | `62.82%` | `1.669` | `0.988` | `-14.81%` | `12.75%` | `{"stop_market": 2, "time_open_untriggered": 68, "trail_gap_open": 25, "trail_stop": 61}` |
| `trigger2.5_lock0_trail1.5_max36` | `145` | `297.65%` | `-26.04%` | `62.76%` | `1.701` | `1.009` | `-14.81%` | `18.28%` | `{"stop_market": 2, "time_open_triggered": 4, "time_open_untriggered": 64, "trail_gap_open": 15, "trail_stop": 60}` |
| `trigger2.5_lock1_trail1.5_max36` | `145` | `297.65%` | `-26.04%` | `62.76%` | `1.701` | `1.009` | `-14.81%` | `18.28%` | `{"stop_market": 2, "time_open_triggered": 4, "time_open_untriggered": 64, "trail_gap_open": 15, "trail_stop": 60}` |
| `trigger2.5_lock0_trail1_max36` | `154` | `291.18%` | `-30.17%` | `62.99%` | `1.663` | `0.977` | `-14.81%` | `12.75%` | `{"stop_market": 2, "time_open_untriggered": 67, "trail_gap_open": 21, "trail_stop": 64}` |
| `trigger2.5_lock1_trail1_max36` | `154` | `291.18%` | `-30.17%` | `62.99%` | `1.663` | `0.977` | `-14.81%` | `12.75%` | `{"stop_market": 2, "time_open_untriggered": 67, "trail_gap_open": 21, "trail_stop": 64}` |
| `trigger2.5_lock1.5_trail1_max36` | `154` | `291.18%` | `-30.17%` | `62.99%` | `1.663` | `0.977` | `-14.81%` | `12.75%` | `{"stop_market": 2, "time_open_untriggered": 67, "trail_gap_open": 21, "trail_stop": 64}` |
| `trigger2.5_lock2_trail1.5_max36` | `154` | `290.86%` | `-30.91%` | `62.34%` | `1.663` | `1.005` | `-14.81%` | `14.23%` | `{"stop_market": 2, "time_open_triggered": 2, "time_open_untriggered": 68, "trail_gap_open": 21, "trail_stop": 61}` |
| `trigger2.5_lock2_trail2.5_max36` | `150` | `280.75%` | `-31.15%` | `62.00%` | `1.655` | `1.014` | `-14.81%` | `27.12%` | `{"stop_market": 2, "time_open_triggered": 5, "time_open_untriggered": 66, "trail_gap_open": 16, "trail_stop": 61}` |
| `trigger2.5_lock2_trail3_max72` | `121` | `272.36%` | `-44.27%` | `74.38%` | `1.695` | `0.584` | `-18.50%` | `27.87%` | `{"stop_market": 5, "time_open_triggered": 1, "time_open_untriggered": 33, "trail_gap_open": 15, "trail_stop": 67}` |

## 回撤 Top

| config | trades | total | max DD | win | PF | worst | best |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `trigger2.5_lock1_trail2.5_max36` | `132` | `220.84%` | `-24.29%` | `59.85%` | `1.622` | `-14.81%` | `27.12%` |
| `trigger2.5_lock0_trail2.5_max36` | `132` | `169.16%` | `-25.38%` | `59.09%` | `1.534` | `-14.81%` | `18.28%` |
| `trigger2.5_lock0_trail1.5_max36` | `145` | `297.65%` | `-26.04%` | `62.76%` | `1.701` | `-14.81%` | `18.28%` |
| `trigger2.5_lock1_trail1.5_max36` | `145` | `297.65%` | `-26.04%` | `62.76%` | `1.701` | `-14.81%` | `18.28%` |
| `trigger2.5_lock1.5_trail1.5_max36` | `146` | `255.05%` | `-26.23%` | `62.33%` | `1.646` | `-14.81%` | `18.28%` |
| `trigger2.5_lock1_trail3_max36` | `130` | `166.44%` | `-26.51%` | `58.46%` | `1.532` | `-14.81%` | `27.87%` |
| `trigger2.5_lock2.5_trail1_max36` | `157` | `340.86%` | `-27.00%` | `63.06%` | `1.710` | `-14.81%` | `9.57%` |
| `trigger2.5_lock2.5_trail1.5_max36` | `157` | `329.78%` | `-27.43%` | `63.06%` | `1.699` | `-14.81%` | `9.72%` |
| `trigger2.5_lock1_trail4_max36` | `125` | `134.15%` | `-27.45%` | `59.20%` | `1.476` | `-14.81%` | `30.42%` |
| `trigger2.5_lock2.5_trail2.5_max36` | `154` | `364.32%` | `-27.70%` | `62.34%` | `1.755` | `-14.81%` | `27.12%` |

## 结论

本轮最高收益 trailing overlay 为 `trigger2.5_lock2.5_trail2.5_max36`，总收益 `364.32%`、最大回撤 `-27.70%`。固定止盈 V6.1 基线为总收益 `408.95%`、最大回撤 `-25.63%`。

若 trailing overlay 没有明显超过 fixed TP，说明 V6.1 的 edge 更像是“强动量后吃一段 2.5ATR 目标”，而不是持续持有趋势右尾；此时强行让利润奔跑会降低胜率并增加回撤。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_1_tp_trigger_trailing.py`
- summary CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_tp_trigger_trailing_summary_2026-06-27.csv`
- trades CSV：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_tp_trigger_trailing_trades_2026-06-27.csv`
- JSON：`research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6-1_tp_trigger_trailing_2026-06-27.json`
