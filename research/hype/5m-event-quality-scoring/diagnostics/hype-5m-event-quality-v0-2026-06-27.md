# HYPE-5M-Event-Quality-Scoring V0 诊断

生成日期：`2026-06-27`

## 结论

- V0 没有找到可直接提升为 paper-live 的候选。
- 最好的 walk-forward 行是 `tp160_sl220_h48__all__expanding__q95`，但至少一项稳定性门槛未过。

这不是深度学习版本，而是低依赖的事件质量分箱 ranker。目标是先确认：
入场前特征是否能把同一批事件区分出高低质量。如果 V0 不能稳定分层，
直接上更重的模型也很容易只是更隐蔽地过拟合。

## 数据质量

- 数据：Binance HYPEUSDT perpetual `5m`。
- 时间范围：`2025-05-30 10:30:00+00:00` 到 `2026-06-26 04:15:00+00:00`。
- 行数：`112822`，期望 K 线：`112822`。
- 缺口：`0`。
- raw/normalized timestamp 对齐：`True`。
- raw/normalized 最大差异：`{'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0, 'quote_volume': 0.0, 'trade_count': 0.0, 'vwap': 0.0}`。
- `is_closed` 分布：`{'True': 112822}`。
- `source` 分布：`{'binance_futures_kline_api': 101956, 'ccxt': 8423, 'binance_futures_api': 2443}`。

## V0 方法

- 事件源：EMA reclaim、VWAP revert、BB revert、wick reject、micro breakout、MACD flip、momentum pause。
- 标签：closed-bar signal，下一根 open 入场，立即固定 TP/SL bracket。
- 执行：同一根 K 同时触发 TP/SL 时按 stop-first；开盘穿越 stop/target 按 open 市价成交。
- 成本：沿用 5m micro-scalp 的 Binance 观测成本，entry slippage `10.73 bps`，fee `4.1466 bps/fill`。
- 训练：月度 walk-forward，只用测试月之前的事件，并按 bracket 持仓窗口 purge。
- 筛选：使用训练集 score 分位数阈值，只交易测试月里分数排名足够高的事件。

## 事件集

- 事件数：`252277`。
- 事件时间范围：`2025-05-31 04:00:00+00:00` 到 `2026-06-26 04:00:00+00:00`。
- 事件源数量：`23`。

## 最佳候选

- candidate：`tp160_sl220_h48__all__expanding__q95`
- 交易数：`669`
- 频率：`2.244` trades/day
- OOS 1x 收益：`-12.04%`
- OOS 年化：`-14.53%`
- 胜率：`53.96%`
- PF：`0.990`
- 平均单笔：`-0.72 bps`
- 最大回撤：`-24.18%`
- last 20% 收益：`-16.78%`
- 最近 30 天收益：`0.34%`
- 活跃月份/亏损活跃月份：`10` / `4`
- paper gate：`False`

## Top 10

| rank | candidate | trades | t/day | ret | PF | win | DD | fwd20 | recent30 | gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `tp160_sl220_h48__all__expanding__q95` | 669 | 2.24 | -12.04% | 0.990 | 53.96% | -24.18% | -16.78% | 0.34% | False |
| 2 | `tp160_sl220_h48__all__trailing_180d__q95` | 711 | 2.38 | -38.12% | 0.922 | 52.04% | -40.52% | -21.09% | -2.18% | False |
| 3 | `tp160_sl220_h48__all__expanding__q90` | 1012 | 3.39 | -38.42% | 0.949 | 53.26% | -42.51% | -23.93% | 0.34% | False |
| 4 | `tp220_sl300_h72__all__expanding__q95` | 543 | 1.82 | -41.72% | 0.916 | 52.67% | -46.33% | -19.59% | -4.00% | False |
| 5 | `tp220_sl300_h72__all__trailing_120d__q85` | 1019 | 3.42 | -43.33% | 0.963 | 53.68% | -59.33% | -43.07% | -10.67% | False |
| 6 | `tp220_sl300_h72__core__trailing_120d__q90` | 856 | 2.87 | -44.49% | 0.945 | 52.34% | -51.37% | -20.50% | 7.79% | False |
| 7 | `tp220_sl300_h72__all__trailing_120d__q95` | 632 | 2.12 | -44.50% | 0.922 | 52.37% | -57.36% | -30.27% | -4.94% | False |
| 8 | `tp160_sl220_h48__core__expanding__q95` | 645 | 2.16 | -45.61% | 0.885 | 53.18% | -46.41% | -15.40% | 0.34% | False |
| 9 | `tp220_sl300_h72__core__expanding__q95` | 568 | 1.90 | -46.62% | 0.898 | 50.35% | -48.80% | -32.43% | 2.18% | False |
| 10 | `tp220_sl300_h72__all__expanding__q90` | 798 | 2.68 | -49.52% | 0.929 | 52.13% | -49.52% | -31.55% | -0.98% | False |

## 事件源质量

以下是按独立事件标签计算的平均质量，不等于最终可交易回放。

| bracket | source | events | avg bps | win | target rate | long share |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `tp120_sl160_h36` | `bb_revert_2p0` | 1028 | -10.46 | 52.14% | 40.18% | 52.63% |
| `tp120_sl160_h36` | `bb_revert_1p5` | 5015 | -10.58 | 52.14% | 39.62% | 50.71% |
| `tp120_sl160_h36` | `bb_revert_1p2` | 9313 | -12.43 | 50.72% | 38.99% | 50.57% |
| `tp120_sl160_h36` | `bb_revert_2p4` | 215 | -12.94 | 52.09% | 39.07% | 55.81% |
| `tp120_sl160_h36` | `bb_revert_1p8` | 2363 | -13.89 | 51.04% | 38.68% | 52.94% |
| `tp120_sl160_h36` | `vwap_revert_200` | 5641 | -14.81 | 51.69% | 45.45% | 47.21% |
| `tp120_sl160_h36` | `wick_reject_1p0` | 1759 | -15.13 | 49.12% | 36.61% | 56.11% |
| `tp120_sl160_h36` | `macd_flip` | 6724 | -15.59 | 49.41% | 38.07% | 50.57% |
| `tp120_sl160_h36` | `vwap_revert_50` | 21188 | -15.66 | 49.59% | 38.80% | 49.94% |
| `tp120_sl160_h36` | `vwap_revert_75` | 17521 | -15.68 | 49.80% | 39.78% | 50.15% |
| `tp120_sl160_h36` | `wick_reject_0p6` | 10932 | -15.93 | 49.03% | 37.50% | 53.92% |
| `tp120_sl160_h36` | `vwap_revert_20` | 26348 | -16.04 | 49.09% | 37.63% | 50.28% |
| `tp120_sl160_h36` | `vwap_revert_12` | 27767 | -16.08 | 49.06% | 37.49% | 50.22% |
| `tp120_sl160_h36` | `vwap_revert_140` | 9945 | -16.12 | 50.68% | 42.63% | 49.76% |
| `tp120_sl160_h36` | `vwap_revert_30` | 24668 | -16.35 | 49.12% | 37.83% | 50.19% |
| `tp120_sl160_h36` | `vwap_revert_100` | 14124 | -16.35 | 49.96% | 40.55% | 50.28% |
| `tp120_sl160_h36` | `ema34_144_reclaim` | 6973 | -16.76 | 48.47% | 38.23% | 49.78% |
| `tp120_sl160_h36` | `ema21_96_reclaim` | 9263 | -18.19 | 47.73% | 37.09% | 50.16% |
| `tp120_sl160_h36` | `ema21_55_reclaim_buf5` | 10691 | -18.71 | 47.42% | 36.22% | 50.15% |
| `tp120_sl160_h36` | `ema21_55_reclaim` | 9304 | -18.83 | 47.48% | 36.58% | 50.27% |

## 保留产物

- JSON：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_2026-06-27.json`
- 事件表：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_events_2026-06-27.parquet`
- 排名表：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_summary_2026-06-27.csv`
- 月度切片：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_monthly_2026-06-27.csv`
- 事件源质量：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_source_quality_2026-06-27.csv`
- 最佳候选交易：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_top_trades_2026-06-27.csv`
- 最佳候选入选事件：`research/hype/5m-event-quality-scoring/artifacts/hype_5m_event_quality_v0_top_selected_events_2026-06-27.csv`

## 最佳候选月度

| month | trades | ret | PF | win | avg bps | DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2025_09` | 77 | -14.85% | 0.743 | 46.75% | -19.71 | -17.17% |
| `2025_10` | 80 | 6.10% | 1.119 | 57.50% | 8.78 | -8.72% |
| `2025_11` | 73 | 4.92% | 1.104 | 57.53% | 8.05 | -13.03% |
| `2025_12` | 69 | 0.89% | 1.036 | 56.52% | 2.50 | -10.84% |
| `2026_01` | 77 | -8.74% | 0.868 | 55.84% | -10.54 | -18.57% |
| `2026_02` | 77 | 4.97% | 1.115 | 59.74% | 7.51 | -14.60% |
| `2026_03` | 89 | 17.83% | 1.337 | 59.55% | 19.54 | -5.18% |
| `2026_04` | 60 | -3.64% | 0.896 | 45.00% | -5.44 | -10.52% |
| `2026_05` | 65 | -17.61% | 0.608 | 41.54% | -28.82 | -21.56% |
| `2026_06` | 2 | 2.66% | inf | 100.00% | 131.99 | 1.10% |
