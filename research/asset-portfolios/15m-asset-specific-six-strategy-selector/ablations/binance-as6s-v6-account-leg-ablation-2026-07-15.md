# BIN-15M-AS6S V6 账户逐腿消融（2026-07-15）

每次只删除一条完整策略腿，并按原账户时序重新路由；微调腿另做单腿回退到V5参数。所有结果严格截止 `2026-07-14T09:00Z`。

## `nonpreemptive`

基线：scale 0.57，full 599笔，胜率 85.98%，年化倍数 15.827x，回撤 -17.96%。

| 删除腿 | hard pass | 分数变化 | full交易变化 | full年化变化 | 当前3m收益变化 | 失败门槛 |
|---|---|---:|---:|---:|---:|---|
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | `True` | +0.088 | +12 | -0.265x | -0.82% | 无 |
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | `True` | -0.513 | -9 | -0.771x | -15.62% | 无 |
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | `True` | -0.531 | -2 | -0.974x | +0.00% | 无 |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | `True` | -0.863 | -8 | -0.952x | -26.25% | 无 |
| `legacy1h:BTCUSDT:keltner_break` | `True` | -1.110 | -19 | -0.989x | -4.20% | 无 |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | `True` | -1.393 | -18 | -2.327x | -5.12% | 无 |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | `True` | -1.632 | -16 | -1.689x | -13.34% | 无 |
| `legacy1h:ETHUSDT:rsi_reversal` | `True` | -1.909 | -19 | -3.851x | +0.00% | 无 |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | `False` | -13.112 | -18 | -0.313x | -2.99% | base_current_frequency_1_to_2 |
| `legacy1h:SOLUSDT:donchian_break` | `False` | -13.216 | -18 | -2.438x | -6.22% | stress_8bps_full_dd_lt_20pct |
| `legacy1h:HYPEUSDT:di_cross` | `False` | -16.213 | -27 | -5.201x | -36.96% | base_current_frequency_1_to_2 |
| `legacy1h:BNBUSDT:wick_reject` | `False` | -24.789 | -39 | -0.696x | -3.24% | base_full_dd_lt_20pct, stress_8bps_full_dd_lt_20pct |
| `legacy1h:TRXUSDT:macd_flip` | `False` | -26.343 | -24 | -3.349x | -13.29% | stress_8bps_current_3m_win_ge_80pct, k_plus_2_current_3m_win_ge_80pct |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | `False` | -27.756 | -4 | -5.031x | -62.47% | stress_8bps_current_3m_win_ge_80pct, k_plus_2_current_3m_win_ge_80pct |
| `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48` | `False` | -33.749 | -196 | -4.167x | -43.65% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2 |

可删除且不降低固定scale分数的腿：`无`。

## `strong_breakout_preemptive`

基线：scale 0.66，full 588笔，胜率 85.88%，年化倍数 20.212x，回撤 -17.75%。

| 删除腿 | hard pass | 分数变化 | full交易变化 | full年化变化 | 当前3m收益变化 | 失败门槛 |
|---|---|---:|---:|---:|---:|---|
| `frontier15m:SOLUSDT:trend_state:SOLUSDT_trend_state_001425` | `True` | -0.454 | -10 | -0.957x | -18.80% | 无 |
| `frontier15m:BNBUSDT:breakout:BNBUSDT_breakout_001075` | `True` | -0.519 | -3 | -1.337x | +0.00% | 无 |
| `frontier15m:ETHUSDT:trend_state:ETHUSDT_trend_state_001071` | `True` | -0.897 | -8 | -1.587x | -31.58% | 无 |
| `frontier15m:SOLUSDT:reversal:SOLUSDT_reversal_001041` | `True` | -0.995 | -16 | -0.413x | -3.20% | 无 |
| `legacy1h:BTCUSDT:keltner_break` | `True` | -1.513 | -10 | -2.335x | -19.33% | 无 |
| `frontier15m:HYPEUSDT:reversal:HYPEUSDT_reversal_000370` | `True` | -1.664 | -16 | -2.473x | -16.13% | 无 |
| `legacy1h:TRXUSDT:macd_flip` | `True` | -2.265 | -22 | -4.126x | -16.11% | 无 |
| `legacy1h:ETHUSDT:rsi_reversal` | `True` | -2.746 | -23 | -6.508x | +0.00% | 无 |
| `frontier15m:HYPEUSDT:breakout:HYPEUSDT_breakout_000423` | `True` | -4.596 | -6 | -7.552x | -74.16% | 无 |
| `frontier15m:SOLUSDT:breakout:SOLUSDT_breakout_000222` | `False` | -13.347 | -10 | -3.435x | +1.02% | stress_8bps_full_dd_lt_20pct |
| `legacy1h:BNBUSDT:wick_reject` | `False` | -24.483 | -37 | -0.433x | -0.96% | base_full_dd_lt_20pct, stress_8bps_full_dd_lt_20pct |
| `frontier15m:ETHUSDT:breakout:ETHUSDT_breakout_000439` | `False` | -25.343 | -23 | -2.645x | -6.21% | stress_8bps_full_dd_lt_20pct, k_plus_2_full_dd_lt_20pct |
| `legacy1h:HYPEUSDT:di_cross` | `False` | -28.247 | -31 | -6.248x | -16.08% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2 |
| `cleanrsi15m:HYPEUSDT:rsi_reversal_w7_lo40_hi60:fixed_tp120p0_sl450p0_hold48` | `False` | -34.662 | -187 | -5.929x | -55.19% | base_current_frequency_1_to_2, base_all_six_frequency_1_to_2 |

可删除且不降低固定scale分数的腿：`无`。

本报告只判定历史开发样本中的边际贡献；被保留不等于通过独立未来OOS。

结构化结果：[`binance_as6s_v6_account_leg_ablation_2026-07-15.json`](../artifacts/binance_as6s_v6_account_leg_ablation_2026-07-15.json)。
