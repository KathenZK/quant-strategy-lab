# MU Polygon 动态杠杆回测

> 迁移说明：本文由 legacy Cursor Canvas `mu-polygon-dynamic-leverage-backtest.canvas.tsx` 自动转换为 Markdown；原 Canvas 未删除，仅作为历史来源。
> 归类：MU-HYPE-XFER legacy Canvas。

在 Polygon MU 一年 15m 真股数据上测试 HYPE 风格动态仓位：allocation = min(max_allocation, target_atr_pct / atr_pct672)。V 系列仍为 long-only、TP10/SL9。

Source: research/mu/artifacts/mu_polygon_hype_v35_dynamic_leverage_ledger.csv · backtest after warmup 2025-07-24 15:45 UTC → 2026-06-16 23:45 UTC · Polygon 无 20:00-04:00 ET overnight bars。

> **结论**
> 动态 max3 值得替代固定 3x，但 target 不能太高。target 1.25% max3 的平均实际杠杆为 2.37x，ALL 收益 +610.92%，MDD -27.98%，比固定 3x 的 +923.81% / -40.07% 稳很多，也比固定 2x 的 +415.63% / -28.16% 更有收益弹性。

### 关键指标

| 指标 | 数值 |
| --- | --- |
| D2 target 1.25% max3 return | +610.92% |
| D2 max drawdown | -27.98% |
| D2 average allocation | 2.37x |
| D2 win rate | 82.76% |

## 收益与回撤

X 轴：regular 主线版本；Y 轴：ALL 窗口百分比。动态 target 越高，越接近固定 3x。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Return (%) | Max DD (%) |
| --- | --- | --- |
| Fixed 2x | 415.63 | -28.16 |
| D2 1.25% | 610.92 | -27.98 |
| D4 1.5% | 771.55 | -32.85 |
| D6 2.0% | 891.51 | -38.63 |
| Fixed 3x | 923.81 | -40.07 |

## 实际杠杆

X 轴：regular 动态版本；Y 轴：实际 allocation。target 2% 已基本打满 3x。

原 Canvas 使用图表展示；这里保留图表底层数据。

| 分类 | Average allocation | Median allocation |
| --- | --- | --- |
| D2 1.25% | 2.367 | 2.268 |
| D4 1.5% | 2.65 | 2.722 |
| D6 2.0% | 2.947 | 3.0 |

### Regular 主线对比

| 版本 | 收益 | MDD | 平均杠杆 | 中位杠杆 | 平均估算止损 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| Fixed 2x regular | +415.63% | -28.16% | 2.000 | 2.000 | 9.75% | V1/V3 fixed baseline |
| Fixed 3x regular | +923.81% | -40.07% | 3.000 | 3.000 | 14.6%* | 收益高但回撤过大 |
| D2 target 1.25% max3 | +610.92% | -27.98% | 2.367 | 2.268 | 10.97% | 动态 3x 里最均衡 |
| D4 target 1.5% max3 | +771.55% | -32.85% | 2.650 | 2.722 | 12.49% | 收益更高，回撤接近 B&H |
| D6 target 2.0% max3 | +891.51% | -38.63% | 2.947 | 3.000 | 14.25% | 几乎退化成固定 3x |
| Buy & Hold | +823.61% | -33.82% | - | - | - | MU 一年强趋势基准 |

## 分窗口表现

1W / 1M / 3M / ALL 分窗口结果。D2 在 3M 和 ALL 的回撤控制最好；D4 更激进，但 MDD 已接近买入持有。

| 版本 | 1W | 1M | 3M | ALL | ALL MDD |
| --- | --- | --- | --- | --- | --- |
| D2 target 1.25% max3 | -3.54% | +6.81% | +65.44% | +610.92% | -27.98% |
| D4 target 1.5% max3 | -4.30% | +7.40% | +79.44% | +771.55% | -32.85% |
| D6 target 2.0% max3 | -5.86% | +7.77% | +88.73% | +891.51% | -38.63% |
| Fixed 2x regular | -5.58% | +9.01% | +61.95% | +415.63% | -28.16% |
| Fixed 3x regular | -8.71% | +9.76% | +92.22% | +923.81% | -40.07% |

## 时段放开测试

使用同一个 target 1.25% max3。盘前和盘后放开后交易数增加，但胜率和收益下降。

| 版本 | 收益 | MDD | 交易 | 胜率 | 平均杠杆 | TP / SL / 指标退出 |
| --- | --- | --- | --- | --- | --- | --- |
| Regular D2 | +610.92% | -27.98% | 29 | 82.76% | 2.367 | 24 / 5 / 0 |
| Premarket+Regular D8 | +377.91% | -27.98% | 33 | 72.73% | 2.364 | 24 / 8 / 1 |
| Extended Day D14 | +322.06% | -33.40% | 34 | 70.59% | 2.379 | 24 / 9 / 1 |

> **注意**
> 这仍然不是 overnight 验证。Polygon 没有 20:00-04:00 ET，所以这里只能说明真股 regular / extended hours 上动态杠杆的表现；Binance 夜盘是否放开仍要用 Binance 数据单独判断。

## 产物路径

| 文件 | 内容 |
| --- | --- |
| scripts/research_mu_polygon_hype_v35_transfer.py | 已加入动态杠杆回测逻辑 |
| research/mu/artifacts/mu_polygon_hype_v35_dynamic_leverage_summary.json | 动态杠杆汇总 |
| research/mu/artifacts/mu_polygon_hype_v35_dynamic_leverage_ledger.csv | 1W/1M/3M/ALL 动态杠杆台账 |
| research/mu/artifacts/mu_polygon_hype_v35_dynamic_leverage_trades.csv | 动态杠杆交易明细 |
| research/mu/artifacts/mu_polygon_hype_v35_dynamic_leverage_equity.csv | 动态杠杆权益曲线 |
