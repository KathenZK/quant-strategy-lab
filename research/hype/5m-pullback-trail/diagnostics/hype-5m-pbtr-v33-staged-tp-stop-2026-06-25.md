# HYPE-5M-PBTR-V3.3 分阶段止盈止损回测 2026-06-25

Family id：`HYPE-5M-PBTR`

本报告按 V3.3 旧回测口径测试一个分阶段退出：固定 `1ATR` 止盈先启用，原 V3.3 trailing stop 后启用。入场、EMA、pullback、`stop_atr=0.5`、`trail_atr=0.75` 均保持 V3.3 不变。

为避免“第六根开始”歧义，测试两个相邻口径：

- `tp_bar6_stop_bar10`：第 6 根持仓 K 本身可触发 `1ATR` 止盈；stop 仍按 V3.3 旧口径第 10 根起触发。
- `tp_bar7_stop_bar10`：持满 6 根后，第 7 根起可触发 `1ATR` 止盈；stop 仍按 V3.3 旧口径第 10 根起触发。

## 结果对比

| 口径 | 信号数 | 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 | target | stop | time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `V3.3 baseline` | `21289` | `8027` | `1331271064.12x` | `514213765749.76%` | `55.66%` | `3.31` | `4.15` | `-8.69%` | `0` | `8026` | `1` |
| `TP 第6根 / Stop 第10根` | `21289` | `8932` | `7225.96x` | `1279580.35%` | `56.39%` | `1.70` | `2.20` | `-8.65%` | `3819` | `5112` | `1` |
| `TP 第7根 / Stop 第10根` | `21289` | `8682` | `5006.03x` | `865758.83%` | `56.37%` | `1.69` | `2.18` | `-9.03%` | `3480` | `5201` | `1` |

## 最佳口径时间切片

最佳 PF：`v33_baseline`，PF `4.15`，交易 `8027` 笔。

| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `recent_1w` | `141` | `54.60%` | `7457866970.77x` | `60.28%` | `3.01` | `4.56` | `-3.07%` |
| `recent_1m` | `623` | `972.04%` | `3489800472818.49x` | `61.00%` | `3.37` | `5.27` | `-4.35%` |
| `recent_3m` | `1881` | `9177.80%` | `96504342.18x` | `54.07%` | `3.43` | `4.04` | `-4.50%` |
| `recent_6m` | `3735` | `2533634.99%` | `862909819.69x` | `55.02%` | `3.45` | `4.22` | `-7.02%` |
| `full` | `8027` | `514213765749.76%` | `1331271064.12x` | `55.66%` | `3.31` | `4.15` | `-8.69%` |

## 结论

加入 `1ATR` 早期止盈会显著改变 V3.3 的收益结构：它大幅提高胜率，但截断了原策略赖以盈利的大盈亏比尾部。若 PF/payoff 明显低于 baseline，则不应作为收益增强方向。

本报告仍是旧 OHLCV 回测口径，不解决 V3.3 的 live-realistic stop 穿越问题。

## 产物

- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_staged_tp_stop.py`
- JSON：`artifacts/hype_5m_pbtr_v33_staged_tp_stop.json`
- 汇总 CSV：`artifacts/hype_5m_pbtr_v33_staged_tp_stop_summary.csv`
- 交易明细 CSV：`artifacts/hype_5m_pbtr_v33_staged_tp_stop_trades.csv`
- rolling CSV：`artifacts/hype_5m_pbtr_v33_staged_tp_stop_rolling.csv`
- weekly CSV：`artifacts/hype_5m_pbtr_v33_staged_tp_stop_weekly.csv`
- monthly CSV：`artifacts/hype_5m_pbtr_v33_staged_tp_stop_monthly.csv`
