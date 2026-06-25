# HYPE-5M-PBTR-V3.3 Minimal 回测 2026-06-24

Family id：`HYPE-5M-PBTR`

V3.3 在 V3.2 基础上删除所有兼容保留、关闭、有限值保护和基本不触发参数，只保留最小有效策略表达。

策略名称：`HYPE-5M-PBTR-V3.3`；时间级别：`5m`。

## 最小参数

| 参数 | 值 |
| --- | ---: |
| `ema_fast` | `21` |
| `ema_slow` | `96` |
| `pullback_buffer` | `0.01` |
| `stop_atr` | `0.5` |
| `trail_atr` | `0.75` |
| `min_hold_bars` | `9` |

删除项：`side_mode`、`entry_style`、`donchian`、`roc_window`、`regime_age`、`breakout_buffer`、`max_dist_ema`、`ROC/RSI/ADX/CHOP/RVOL/CMF/MACD/OBV/HTF/efficiency`、`tp_atr`、`max_hold_bars`、`exit_ema`、`cooldown_bars`、`final_dir_htf_filter`。

## V3.2 vs V3.3

| 版本 | 信号数 | 交易数 | 权益倍数 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE-5M-PBTR-V3.2` | `21282` | `8025` | `5112332636.95x` | `1324019761.54x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |
| `HYPE-5M-PBTR-V3.3` | `21289` | `8027` | `5128398716.73x` | `1327928815.51x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

相对 V3.2，V3.3 交易数变化 `+2`，胜率从 `55.66%` 到 `55.66%`，PF 从 `4.15` 到 `4.15`，最大回撤从 `-8.69%` 到 `-8.69%`。

## 时间切片

| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | `141` | `54.19%` | `6486157893.73x` | `60.28%` | `2.94` | `4.47` | `-3.07%` |
| `recent_1m` | `623` | `969.17%` | `3377958191953.49x` | `61.00%` | `3.35` | `5.25` | `-4.35%` |
| `recent_3m` | `1881` | `9153.01%` | `95462194.20x` | `54.07%` | `3.42` | `4.03` | `-4.50%` |
| `recent_6m` | `3735` | `2526865.27%` | `858237901.65x` | `55.02%` | `3.45` | `4.22` | `-7.02%` |
| `full` | `8027` | `512839871573.17%` | `1327928815.51x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

周/月摘要：

- 周数：`56`，盈利周 `56/56`，中位周收益 `43.86%`。
- 最差周：`week_048_20260424_20260430`，收益 `9.92%`，最大回撤 `-4.50%`；最好周：`week_036_20260130_20260205`，收益 `167.02%`。
- 月数：`14`，盈利月 `14/14`，中位月收益 `459.67%`。
- 最差月：`2025-05`，收益 `11.92%`；最好月：`2025-10`，收益 `880.91%`。

## 结论

V3.3 用最小逻辑重写后表现与 V3.2 几乎一致，说明 V3.2 中所有关闭/兼容/保护参数都可以从实盘交接规格中移除。本次仅多出 2 笔交易，差异来自 V3.2 旧代码中额外的 NaN 预热保护，而不是策略核心变化。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_minimal.py`
- JSON：`artifacts/hype_5m_pbtr_v3-3_minimal.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v3-3_minimal_summary.csv`
- 滚动切片：`artifacts/hype_5m_pbtr_v3-3_minimal_rolling.csv`
- 周切片：`artifacts/hype_5m_pbtr_v3-3_minimal_weekly.csv`
- 月切片：`artifacts/hype_5m_pbtr_v3-3_minimal_monthly.csv`
- 交易明细：`artifacts/hype_5m_pbtr_v3-3_minimal_trades.csv`
