# MUUSDT V35 迁移回测

> 迁移说明：本文由 legacy Cursor Canvas `mu-usdt-v35-transfer-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：MU-HYPE-XFER legacy Canvas。

直接使用 HYPE V35 冻结参数回测 Binance U 本位 MUUSDT，不做 MU 专属调参；funding 按 Binance 8h 结算点对齐到 15m K。

Source: Binance FAPI + data lake · 2026-04-07 13:30 UTC → 2026-06-17 05:45 UTC · 6,786 bars · warmup 1,600 bars.

> **结论**
> V35 在 MU 上不是完全失效，但不适合直接上线：回测期 V35 +25.64%，同期 warmup 后买入持有 +121.66%；策略回撤 -29.58%，还比买持 -22.95% 更深。问题主要不是没有多头信号，而是 MU 在上涨段更适合持有，V35 的短 TP/重复追多会吃到多次止损。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| V35 return | +25.64% |
| V35 max DD | -29.58% |
| V35 win rate | 67.65% |
| Buy & hold | +121.66% |

## 核心对比

X 轴：策略或基准；Y 轴：收益/最大回撤百分比。回撤用负值展示。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Return (%) | Max DD (%) |
| --- | --- | --- |
| V35 | 25.64 | -29.58 |
| Buy & hold | 121.66 | -22.95 |

## 退出结构

X 轴：退出原因；Y 轴：交易次数与该类交易 PnL 合计百分比。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Trades | PnL sum (%) |
| --- | --- | --- |
| TP | 23 | 152.75 |
| SL | 10 | -92.56 |
| Indicator | 1 | -5.67 |

### 方向表现

| 方向 | 笔数 | PnL合计 | 胜率 | 最差单笔 | 退出 |
| --- | --- | --- | --- | --- | --- |
| Long | 33 | +67.11% | 69.70% | -9.99% | 23 TP / 9 SL / 1 indicator |
| Short | 1 | -12.60% | 0.00% | -12.60% | 1 SL |

### 按退出原因拆分

| 退出 | 笔数 | PnL合计 | 胜率 | 平均单笔 |
| --- | --- | --- | --- | --- |
| take_profit | 23 | +152.75% | 100.00% | +6.64% |
| stop_loss | 10 | -92.56% | 0.00% | -9.26% |
| indicator_exit | 1 | -5.67% | 0.00% | -5.67% |

> **迁移判断**
> MU 样本只有约 70 天，V35 有效测试段约 54 天，结论只能当作早期迁移验证。当前数据更支持“MU 需要单独研究股票永续版趋势参数”，不支持把 HYPE V35 原样搬过去；尤其需要重新看 TP/SL、max allocation、是否减少连续追多，以及股票美盘时段的量能过滤。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| data/normalized/ohlcv/.../symbol=mu_usdt_usdt.parquet | MUUSDT 15m OHLCV normalized data lake partitions |
| data/normalized/funding_rates/.../symbol=mu_usdt_usdt.parquet | MUUSDT funding normalized data lake partitions |
| reports/mu_usdt_data_lake_summary.json | 数据湖写入摘要 |
| reports/mu_usdt_v35_backtest_summary.json | V35 回测结构化结果 |
| reports/mu_usdt_v35_backtest_trades.csv | 34 笔交易明细 |
