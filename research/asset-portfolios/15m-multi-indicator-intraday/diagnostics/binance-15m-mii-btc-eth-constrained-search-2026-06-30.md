# Binance 15m MII BTC/ETH 受约束微调搜索 2026-06-30

Family：`Binance-15M-Multi-Indicator-Intraday-Transfer`

## 结论

本报告不是重新发明策略，而是在 `HYPE-15M-MII-V1.1` 的同一机制内做跨资产微调：保留 RSI 反转、MACD 方向过滤、ATR/RVOL、固定 TP/SL/hold 和下一根 open 入场，只缩放 BTC/ETH 更小波动所需的阈值。

- Stage1 共评估 `69122` 个 asset-config 行；全样本 K+1/K+2 strict transfer pass `24/69122`。
- 对 top 配置补做前后半段、Last90 和最近 30 天后，balanced diagnostic pass `33/500`。
- BTC 可以找到 K+1/K+2 同时为正的微调版本，但收益很低，更多像低频 sanity candidate，而不是有实盘吸引力的迁移版本。
- ETH 可以找到 K+1-only 赚钱版本，但本次受约束搜索中 `0` 个 ETH 配置做到全样本 K+1/K+2 同时为正；延迟一根 K 后明显转亏。
- 数据来自 Binance futures kline API 直接拉取，不是本仓库标准 raw/normalized 数据湖；结果只能作为迁移诊断，不能作为实盘或 paper-live promotion。

## 数据质量

- `BTCUSDT`：`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`，rows `37607`，gap `0`，duplicates `0`，critical nulls `0`，invalid OHLC `0`，quality gate `True`。
- `ETHUSDT`：`2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`，rows `37607`，gap `0`，duplicates `0`，critical nulls `0`，invalid OHLC `0`，quality gate `True`。

## 搜索边界

- RSI：window `7/9`，low `35/40/45`，high `55/60/65`，且 high-low 至少 `15`。
- Filter：side `both/long/short`；`MACD(12,26,9)` 方向过滤；`ATR96 pct` 最低门槛 `0%-0.45%`；`RVOL96` 最低门槛 `0/0.5/1.0`。
- Exit：`TP=0.45%-0.90%`，`SL=0.90%-2.40%`，hold `8/16/24` 根 `15m` K。
- Exposure：固定 `1x`；手续费 `0.1000%`/fill，滑点 `0.0400%`/fill，round-trip `0.2800%`；资金费未计入。

## 代表参数

### BTC 均衡诊断版

`btceth_mii_rsi9_35_60_long_atrmin35_rvol1_tp90_sl240_hold8_x1`

- 参数：`RSI(9)` 上穿 `35` 做多；只做多；`MACD(12,26,9)` 方向过滤；`ATR96 pct >= 0.35%`；`RVOL96 >= 1.0`；`TP=0.90%`、`SL=2.40%`、最长 `8` 根 `15m` K；`1x`。
- K+1 全样本：年化 `2.78%`、总收益 `2.99%`、回撤 `-3.46%`、胜率 `61.29%`、`31` 笔。
- K+2 全样本：年化 `2.08%`、总收益 `2.24%`、回撤 `-4.03%`、胜率 `67.74%`、`31` 笔。
- 时间切片：后半段 K+1 `+1.23%`、K+2 `+1.24%`；Last90 K+1 `+1.37%`、K+2 `+0.33%`；最近 30 天 K+1 `+0.62%`、K+2 `-0.50%`。
- 结论：比直接套 HYPE V1.1 明显更适配 BTC 波动，但收益太薄，且最近 30 天 K+2 为负，只能作为 BTC 低频迁移诊断。

### ETH K+1-only 诊断版

`btceth_mii_rsi9_40_60_short_atrmin45_rvol1_tp75_sl240_hold24_x1`

- 参数：`RSI(9)` 下穿 `60` 做空；只做空；`MACD(12,26,9)` 方向过滤；`ATR96 pct >= 0.45%`；`RVOL96 >= 1.0`；`TP=0.75%`、`SL=2.40%`、最长 `24` 根 `15m` K；`1x`。
- K+1 全样本：年化 `6.17%`、总收益 `6.63%`、回撤 `-5.99%`、胜率 `82.81%`、`64` 笔。
- K+2 全样本：年化 `-10.40%`、总收益 `-11.11%`、回撤 `-17.13%`、胜率 `70.31%`、`64` 笔。
- 时间切片：后半段 K+1 `+3.38%`，但 K+2 `-4.14%`；Last90 K+1 `+4.31%`、K+2 `+3.84%`；最近 30 天 K+1/K+2 都是 `+1.42%`。
- 结论：ETH 的 K+1 样本内形状能赚钱，但对入场延迟高度敏感；不能作为稳健迁移版本。

### BTC Top 5

| 资产 | 策略 | K+1年化 | K+1总收益 | K+1回撤 | K+1笔数 | K+2年化 | K+2总收益 | K+2回撤 | K+2笔数 | 后半段K+1 | Last90 K+1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `BTC` | `btceth_mii_rsi9_35_65_long_atrmin45_rvol1_tp75_sl240_hold8_x1` | `0.35%` | `0.38%` | `-3.26%` | `17` | `2.43%` | `2.61%` | `-2.49%` | `17` | `0.76%` | `0.00%` |
| `BTC` | `btceth_mii_rsi9_35_55_long_atrmin45_rvol1_tp75_sl240_hold8_x1` | `0.35%` | `0.38%` | `-3.26%` | `17` | `2.43%` | `2.61%` | `-2.49%` | `17` | `0.76%` | `0.00%` |
| `BTC` | `btceth_mii_rsi9_35_60_long_atrmin45_rvol1_tp75_sl240_hold8_x1` | `0.35%` | `0.38%` | `-3.26%` | `17` | `2.43%` | `2.61%` | `-2.49%` | `17` | `0.76%` | `0.00%` |
| `BTC` | `btceth_mii_rsi9_35_60_long_atrmin35_rvol1_tp75_sl240_hold8_x1` | `0.92%` | `0.98%` | `-3.09%` | `31` | `3.56%` | `3.82%` | `-3.38%` | `31` | `0.03%` | `1.07%` |
| `BTC` | `btceth_mii_rsi9_35_65_long_atrmin35_rvol1_tp75_sl240_hold8_x1` | `0.92%` | `0.98%` | `-3.09%` | `31` | `3.56%` | `3.82%` | `-3.38%` | `31` | `0.03%` | `1.07%` |

### ETH Top 5

| 资产 | 策略 | K+1年化 | K+1总收益 | K+1回撤 | K+1笔数 | K+2年化 | K+2总收益 | K+2回撤 | K+2笔数 | 后半段K+1 | Last90 K+1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ETH` | `btceth_mii_rsi9_45_60_short_atrmin45_rvol1_tp60_sl240_hold24_x1` | `0.43%` | `0.46%` | `-7.59%` | `64` | `-7.19%` | `-7.69%` | `-12.39%` | `65` | `0.34%` | `2.92%` |
| `ETH` | `btceth_mii_rsi9_35_60_short_atrmin45_rvol1_tp60_sl240_hold24_x1` | `0.43%` | `0.46%` | `-7.59%` | `64` | `-7.19%` | `-7.69%` | `-12.39%` | `65` | `0.34%` | `2.92%` |
| `ETH` | `btceth_mii_rsi9_40_60_short_atrmin45_rvol1_tp60_sl240_hold24_x1` | `0.43%` | `0.46%` | `-7.59%` | `64` | `-7.19%` | `-7.69%` | `-12.39%` | `65` | `0.34%` | `2.92%` |
| `ETH` | `btceth_mii_rsi9_40_60_short_atrmin45_rvol1_tp75_sl240_hold24_x1` | `6.17%` | `6.63%` | `-5.99%` | `64` | `-10.40%` | `-11.11%` | `-17.13%` | `64` | `3.38%` | `4.31%` |
| `ETH` | `btceth_mii_rsi9_45_60_short_atrmin45_rvol1_tp75_sl240_hold24_x1` | `6.17%` | `6.63%` | `-5.99%` | `64` | `-10.40%` | `-11.11%` | `-17.13%` | `64` | `3.38%` | `4.31%` |

## 状态

即使找到样本内赚钱版本，也只能称为 `diagnostic`。下一步必须做标准数据湖复验、资金费回放、更多时间窗口、参数邻域和真实成交滑点审计。

## 产物

- 脚本：`research/asset-portfolios/15m-multi-indicator-intraday/scripts/research_binance_15m_mii_btc_eth_constrained_search.py`
- Ranking CSV：`research/asset-portfolios/15m-multi-indicator-intraday/artifacts/binance_15m_mii_btc_eth_constrained_search_ranking_2026-06-30.csv`
- Finalists CSV：`research/asset-portfolios/15m-multi-indicator-intraday/artifacts/binance_15m_mii_btc_eth_constrained_search_finalists_2026-06-30.csv`
- Slices CSV：`research/asset-portfolios/15m-multi-indicator-intraday/artifacts/binance_15m_mii_btc_eth_constrained_search_slices_2026-06-30.csv`
- JSON：`research/asset-portfolios/15m-multi-indicator-intraday/artifacts/binance_15m_mii_btc_eth_constrained_search_2026-06-30.json`
