# MU Polygon 一年 HYPE V35 Transfer 回测

> 迁移说明：本文由 legacy Cursor Canvas `mu-polygon-hype-v35-one-year-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：MU-HYPE-XFER legacy Canvas。

使用 Polygon MU 真股 15m aggregate 跑同一套 HYPE V35 transfer 候选：B0 保留原版 long/short 诊断，V 系列为 long-only、TP10/SL9、2x/3x。

Source: data/external/us_equities/polygon/symbol=mu/timeframe=15m · 15,951 bars · warmup 1,600 bars · backtest after warmup starts 2025-07-24 15:45 UTC.

> **最重要的限制**
> Polygon 本次数据只有 04:00-20:00 ET，没有 20:00-04:00 ET overnight。也就是说 V1 regular+overnight 在这个真股数据上实际退化成 regular-only，不能验证 Binance 夜盘是否应该放开。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| B0 original return | -3.43% |
| V1/V3 2x return | +415.63% |
| V1/V3 2x max DD | -28.16% |
| buy & hold return | +823.61% |

## ALL 窗口收益与回撤

X 轴：版本；Y 轴：百分比。V1 与 V3 等价，因为 Polygon 无 overnight bars；V2 与 V4 也等价。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Return (%) | Max DD (%) |
| --- | --- | --- |
| B0 | -3.43 | -42.67 |
| V1 2x | 415.63 | -28.16 |
| V2 3x | 923.81 | -40.07 |
| V5 2x | 265.8 | -28.16 |
| V7 2x | 235.73 | -28.16 |
| B&H | 823.61 | -33.82 |

## 交易质量

X 轴：版本；Y 轴：闭合交易数量与胜率。盘前/盘后放开后交易增加，但胜率下降。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Closed trades | Win rate (%) |
| --- | --- | --- |
| B0 | 52 | 57.69 |
| V1 2x | 29 | 82.76 |
| V5 2x | 33 | 72.73 |
| V7 2x | 34 | 70.59 |

### 关键版本对比

| 版本 | 收益 | MDD | 交易 | 胜率 | TP / SL / 指标退出 | 解释 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 原版 HYPE V35 | -3.43% | -42.67% | 52 | 57.69% | 29 / 17 / 6 | 原版 long+short、TP5/SL7；一年 MU 大牛市仍亏损 |
| V1 regular+overnight 2x | +415.63% | -28.16% | 29 | 82.76% | 24 / 5 / 0 | Polygon 无 overnight，实际等价 regular-only |
| V2 regular+overnight 3x | +923.81% | -40.07% | 29 | 82.76% | 24 / 5 / 0 | 收益最高之一，但回撤过大 |
| V5 premarket+regular 2x | +265.80% | -28.16% | 33 | 72.73% | 24 / 8 / 1 | 盘前多 4 笔，收益和胜率下降 |
| V7 extended-day 2x | +235.73% | -28.16% | 34 | 70.59% | 24 / 9 / 1 | 盘后再多 1 笔，进一步拖累 |
| Buy & Hold | +823.61% | -33.82% | - | - | - | MU 一年强趋势基准 |

## 分窗口表现

Source: reports/mu_polygon_hype_v35_transfer_ledger.csv。1W 只有未平仓权益变化、无闭合交易；ALL 受 MU 一年大牛市影响很大。

| 版本 | 1W | 1M | 3M | ALL | ALL MDD |
| --- | --- | --- | --- | --- | --- |
| V1 2x | -5.58% | +9.01% | +61.95% | +415.63% | -28.16% |
| V2 3x | -8.71% | +9.76% | +92.22% | +923.81% | -40.07% |
| V5 2x | -5.58% | +9.01% | +61.95% | +265.80% | -28.16% |
| V7 2x | -5.58% | +9.01% | +61.95% | +235.73% | -28.16% |
| V13 all-time 2x | -5.58% | +9.01% | +61.95% | +235.73% | -28.16% |

> **研究结论**
> Polygon 一年样本支持 “原版 HYPE V35 不能直接迁移 MU” 这个判断：B0 在大牛市里仍亏损，且回撤超过 -42%。V1/V3 2x 在这个样本里比 B0 干净很多，但没有跑赢买入持有；它的价值是把回撤从 B&H 的 -33.82% 降到 -28.16%，并避免空头拖累。3x 不建议作为 shadow 主线，回撤已经到 -40%。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_mu_polygon_hype_v35_transfer.py | Polygon 一年回测脚本 |
| reports/mu_polygon_hype_v35_transfer_summary.json | 汇总结果 |
| reports/mu_polygon_hype_v35_transfer_ledger.csv | 1W/1M/3M/ALL 分窗口台账 |
| reports/mu_polygon_hype_v35_transfer_trades.csv | V 系列交易明细 |
| reports/mu_polygon_hype_v35_original_summary.json | B0 原版 HYPE V35 诊断 |
| reports/mu_polygon_hype_v35_transfer_equity.csv | V 系列权益曲线 |
