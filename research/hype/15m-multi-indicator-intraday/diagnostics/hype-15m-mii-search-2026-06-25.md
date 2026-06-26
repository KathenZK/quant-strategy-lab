# HYPE-15M-Multi-Indicator-Intraday Search - 2026-06-25

## 结论

本轮在 Binance HYPEUSDT perpetual `15m` K 线上没有找到满足用户目标的策略。

目标口径：

- 年化收益率 `>= 2000%`。
- 年化权益倍数 `>= 20x` 同步记录，但不作为单独放宽口径。
- 最大回撤 `>= -20%`。
- 胜率 `>= 70%`。
- 交易频率偏好：约 `0.75-2.25` 笔/日，接近用户说的每天 `1-2` 次。

最终评估 `1,076,400` 个可交易候选，其中同时满足年化收益、最大回撤和胜率三项 core target 的数量为 `0`；同时满足交易频率偏好的数量也为 `0`。

因此本 family 当前状态是 **negative diagnostic / not a candidate**，不能提升为 live、paper-live、handoff 或 candidate。

## 数据与执行假设

- 数据：`data/cache/hypeusdt_15m_fapi.csv`
- 交易对：Binance USD-M futures `HYPEUSDT`
- 周期：`2025-05-30 10:30:00 UTC` 到 `2026-06-25 13:45:00 UTC`
- K 线数量：`37,550`
- 缺口数量：`0`
- 手续费：每边 `0.05%`
- 滑点：每边 `0.025%`
- 统一 round-trip 成本：`0.15%`

执行规则：

- 信号只使用已收盘的 `15m` bar。
- 入场按下一根 `15m` bar open。
- 固定止损/止盈使用 intrabar high/low 检查。
- 同一根 K 同时触发止损和止盈时，保守地按先止损处理。
- 过滤后只允许单仓，不允许重叠持仓。

## 搜索空间

脚本：`research/hype/15m-multi-indicator-intraday/scripts/research_hype_15m_mii_search.py`

输出：

- Summary JSON：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_search_summary.json`
- Ranking CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_search_ranking.csv`
- Top trades CSV：`research/hype/15m-multi-indicator-intraday/artifacts/hype_15m_mii_search_top_trades.csv`

覆盖面：

- 信号形态：`137`
- 粗退出参数：`60`
- 细退出参数：`264`
- 基础过滤器：`14`
- 最终过滤器：`598`
- 暴露倍数：`0.5x, 1.0x, 1.5x, 2.0x, 2.5x, 3.0x`
- Stage 1 保留：`800`
- Stage 2 保留：`300`
- 最终评估：`1,076,400`

信号族包括：

- EMA cross
- MACD zero / signal cross
- Donchian breakout
- RSI reversal
- Bollinger reversion / breakout
- EMA pullback resume
- Squeeze release

## 最佳综合候选

名称：

`HYPE_15M_MII_rsi_reversal_w7_lo30_hi60_fixed_tp90p0_sl280p0_hold16_macd0p0_atr60p0to280p0_x1p5`

规则摘要：

- 信号：`RSI(7)` 反转，low `30`，high `60`。
- 方向过滤：MACD histogram 同方向 `>= 0`。
- ATR 过滤：`ATR96 pct` 在 `0.60%-2.80%`。
- 出场：固定 take-profit `0.9%`，stop `2.8%`，最长持仓 `16` 根 `15m` bar。
- 暴露：`1.5x`。

全样本指标：

| Metric | Value |
| --- | ---: |
| Final equity | `2.5755x` |
| Total return | `+157.55%` |
| Annual return | `+141.92%` |
| Annual equity multiple | `2.419x` |
| Max drawdown | `-18.88%` |
| Win rate | `76.90%` |
| Trades | `368` |
| Trades/day | `0.94` |
| Profit factor | `1.48` |

这个候选满足回撤、胜率和交易频率偏好，但年化收益远低于 `2000%`，只有目标的大约 `7.1%`。

## 时间切片稳定性

最佳综合候选的表现明显前强后弱：

| Window | Annual return | Max DD | Win rate | Trades/day |
| --- | ---: | ---: | ---: | ---: |
| First half | `+350.56%` | `-14.79%` | `79.33%` | `0.92` |
| Second half | `+29.89%` | `-18.88%` | `74.60%` | `0.97` |
| Last 90d | `-5.26%` | `-15.55%` | `71.43%` | `0.93` |
| Q1 | `+130.49%` | `-14.79%` | `73.63%` | `0.93` |
| Q2 | `+780.76%` | `-5.50%` | `85.23%` | `0.90` |
| Q3 | `+77.67%` | `-18.88%` | `77.00%` | `1.02` |
| Q4 | `-5.04%` | `-15.55%` | `71.91%` | `0.91` |

这不是可提升候选。后半段和最近 `90d` 的收益衰减太明显，继续加过滤器可能只是过拟合。

## 边界候选

在 retained ranking 中，满足 `DD <= 20%` 且 `win rate >= 70%` 的最高年化收益候选为：

`HYPE_15M_MII_ema_cross_f89_s377_fixed_tp260p0_sl280p0_hold64_rvol1_atr35p0to400p0_x3`

| Metric | Value |
| --- | ---: |
| Annual return | `+247.04%` |
| Annual equity multiple | `3.470x` |
| Max drawdown | `-19.54%` |
| Win rate | `74.51%` |
| Trades | `51` |
| Trades/day | `0.13` |
| Exposure | `3.0x` |

这个候选比最佳综合候选收益高，但交易频率很低，距离 `2000%` 年化仍差一个数量级。

retained ranking 中年化收益最高的候选为：

`HYPE_15M_MII_bb_breakout_w96_k2p5_fixed_tp120p0_sl280p0_hold64_adx34_atrR1p2_x2p5`

| Metric | Value |
| --- | ---: |
| Annual return | `+264.91%` |
| Annual equity multiple | `3.649x` |
| Max drawdown | `-21.93%` |
| Win rate | `80.85%` |
| Trades | `188` |
| Trades/day | `0.48` |
| Exposure | `2.5x` |

它突破了回撤限制，也没有达到交易频率偏好。

## Live Feasibility

本轮没有候选可进入 live feasibility promotion。

原因：

- 没有任何候选同时满足年化收益、回撤、胜率三项 core target。
- 最佳综合候选最近 `90d` 已经转负，说明边际已经退化。
- 最高收益候选要么频率过低，要么突破 `20%` 回撤。
- 继续扩大盲目参数搜索很可能只会找到时间段拟合，而不是可真实下单的状态机。

如果继续研究，下一步不应是机械放大过滤器，而应改为：

1. 用 train/test 或 walk-forward 固定训练区间选参数，再只看 holdout。
2. 把 `1-2` 次/日作为单独目标，先建立 event-quality label，再训练/筛选信号质量。
3. 对已有低频高收益 family 单独复核当前数据，而不要把它混入本 family。
