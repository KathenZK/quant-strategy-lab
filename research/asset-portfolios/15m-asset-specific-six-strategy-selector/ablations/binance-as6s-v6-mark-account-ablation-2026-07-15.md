# BIN-15M-AS6S V6 mark账户逐腿消融（2026-07-15）

每次删除一条完整策略腿，重新运行mark触发和联合账户仲裁；可删除判定同时要求全部硬门槛与-18.5%回撤缓冲。

## `nonpreemptive`

scale 0.57，full 579笔，胜率 85.66%，年化倍数 12.748x，回撤 -17.89%。

| 删除腿 | hard pass | 缓冲通过 | 分数变化 | full年化变化 | 当前3m收益变化 | 失败门槛 |
|---|---|---|---:|---:|---:|---|
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | `False` | `False` | +12.735 | +0.224x | -0.55% | stress_8bps_current_3m_win_ge_80pct |
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | `False` | `False` | -0.257 | -0.379x | +0.00% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | `False` | `False` | -0.344 | -0.423x | +0.00% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | `False` | `False` | -0.910 | -0.221x | -1.33% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | `False` | `False` | -0.922 | -0.904x | -22.79% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `legacy1h:BTCUSDT:keltner_break` | `False` | `False` | -0.937 | -0.970x | -2.38% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | `False` | `False` | -0.985 | -1.680x | +1.91% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `legacy1h:SOLUSDT:donchian_break` | `False` | `False` | -1.109 | -1.830x | -5.51% | base_current_frequency_1_to_2, stress_8bps_full_dd_lt_20pct |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | `False` | `False` | -1.569 | -1.360x | -11.24% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `legacy1h:ETHUSDT:rsi_reversal` | `False` | `False` | -1.845 | -2.983x | +0.00% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `legacy1h:TRXUSDT:macd_flip` | `False` | `False` | -13.311 | -2.444x | +4.59% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct, k_plus_2_current_3m_win_ge_80pct |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | `False` | `False` | -14.947 | -3.462x | -49.52% | base_current_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct, k_plus_2_current_3m_win_ge_80pct |
| `legacy1h:HYPEUSDT:di_cross` | `False` | `True` | -15.749 | -3.844x | -29.21% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48` | `False` | `False` | -21.364 | -3.263x | -35.67% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |
| `legacy1h:BNBUSDT:wick_reject` | `False` | `False` | -24.138 | +0.205x | +0.70% | base_current_frequency_1_to_2, base_full_dd_lt_20pct, stress_8bps_full_dd_lt_20pct, stress_8bps_current_3m_win_ge_80pct |

可删除腿：`无`。

## `strong_breakout_preemptive`

scale 0.63，full 580笔，胜率 85.34%，年化倍数 13.670x，回撤 -16.87%。

| 删除腿 | hard pass | 缓冲通过 | 分数变化 | full年化变化 | 当前3m收益变化 | 失败门槛 |
|---|---|---|---:|---:|---:|---|
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | `True` | `True` | -0.135 | -0.172x | +0.00% | 无 |
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | `True` | `False` | -0.359 | -0.384x | +0.00% | 无 |
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | `True` | `False` | -0.391 | -1.654x | +1.07% | 无 |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | `True` | `False` | -1.180 | -1.678x | -4.32% | 无 |
| `legacy1h:TRXUSDT:macd_flip` | `True` | `False` | -1.313 | -2.340x | +5.20% | 无 |
| `legacy1h:ETHUSDT:rsi_reversal` | `True` | `True` | -2.599 | -4.115x | +0.00% | 无 |
| `legacy1h:BNBUSDT:wick_reject` | `False` | `False` | -12.191 | -0.175x | +1.56% | stress_8bps_full_dd_lt_20pct |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | `False` | `True` | -12.937 | -1.085x | -25.92% | base_current_frequency_1_to_2 |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | `False` | `True` | -13.011 | -0.273x | -2.63% | base_current_frequency_1_to_2 |
| `legacy1h:BTCUSDT:keltner_break` | `False` | `True` | -13.087 | -0.699x | -15.93% | base_current_frequency_1_to_2 |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | `False` | `True` | -13.606 | -1.601x | -12.83% | base_current_frequency_1_to_2 |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | `False` | `True` | -16.363 | -4.863x | -60.74% | base_current_frequency_1_to_2 |
| `legacy1h:HYPEUSDT:di_cross` | `False` | `True` | -27.593 | -3.487x | -11.29% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2 |
| `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48` | `False` | `True` | -46.093 | -3.636x | -42.77% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2, stress_8bps_current_3m_win_ge_80pct |

可删除腿：`无`。

结构化结果：[`binance_as6s_v6_mark_account_ablation_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_account_ablation_2026-07-15.json)。
