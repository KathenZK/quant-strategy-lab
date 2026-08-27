# NDX100-1D-MA7-RC-Y3：突破前市场结构图谱

## 一句话结论

**存在若干通过样本与FDR门槛的结构，但仍需独立样本验证。** 本轮研究的是突破前真实价格路径，不是个股相对强弱：大跌修复、深回撤筑底、趋势回踩、暴涨回落、横盘派发、MA层级、市场宽度和 QQQ 阶段均已逐项统计。通过门槛的 descriptive states：`MA7:L02_DEEP_DRAWDOWN_RECOVERY, MA7:L04_EARLY_RECOVERY_BELOW_MA30, MA30:L07_FAILED_BEAR_TREND_REVERSAL, MA30:L01_CRASH_REVERSAL, MA30:L02_DEEP_DRAWDOWN_RECOVERY, MA30:L04_EARLY_RECOVERY_BELOW_MA30`。

## 样本与因果口径

- Config SHA256：`d75dea70494ae497a360ea2d997db6fb3807b2cbe0d0ed12c6f9f577d1426c25`。
- Eligible：`355,038` stock-days、`100` stocks，所有状态严格截至 `t-1`。
- Events：`110,154`，同时检验 MA7 与 MA30 的向上/向下严格收盘跨越。
- 具名状态：`23` 个；连续结构维度：`11` 类。
- 当前成分回填、survivorship-biased；这是事件图谱，不是账户策略。

## 裸突破基线

| Trigger | 方向 | 20D样本 | 平均 | 中位 | 胜率 | t |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MA7 | long | 38,226 | 3.18% | 1.50% | 57.94% | 7.79 |
| MA7 | short | 38,220 | -3.20% | -1.54% | 41.81% | -8.15 |
| MA30 | long | 16,539 | 3.49% | 1.58% | 58.20% | 5.82 |
| MA30 | short | 16,565 | -3.44% | -1.43% | 42.38% | -5.48 |

## 每组排名靠前的具名结构

“增量”是相对同 trigger、同方向其余突破事件；FDR 在全部具名状态内校正。这里只是全样本描述排名，不是选参。

| Trigger | 方向 | 状态 | 大白话 | 样本 | 20D平均 | 中位 | 增量 | 增量t | FDR q | 年度增量为正占比 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MA7 | long | `L08_DEPRESSED_BREADTH_REVERSAL` | 市场宽度低位但过去10日改善 | 1,150 | 9.05% | 3.13% | 6.05% | 1.61 | 0.139 | 75.00% |
| MA7 | long | `L02_DEEP_DRAWDOWN_RECOVERY` | 60日深回撤后已从20日低点反弹 | 3,718 | 8.53% | 3.11% | 5.93% | 2.90 | 0.014 | 76.47% |
| MA7 | long | `L04_EARLY_RECOVERY_BELOW_MA30` | 仍在MA30下方的深回撤早期修复 | 3,837 | 7.06% | 2.70% | 4.32% | 2.68 | 0.020 | 82.35% |
| MA7 | long | `L07_FAILED_BEAR_TREND_REVERSAL` | 空头排列中强反弹后的向上突破 | 2,016 | 7.06% | 3.03% | 4.10% | 1.58 | 0.139 | 58.82% |
| MA7 | long | `L11_HIGH_VOL_CAPITULATION` | 高波环境中的20日暴跌反转 | 2,631 | 5.26% | 1.82% | 2.24% | 1.37 | 0.186 | 64.71% |
| MA7 | long | `L01_CRASH_REVERSAL` | 20日暴跌且仍处60日深回撤 | 3,803 | 5.12% | 2.23% | 2.16% | 1.81 | 0.128 | 64.71% |
| MA7 | short | `S10_LOW_VOL_DISTRIBUTION` | 低波低区间横盘后向下跌破 | 7,998 | -1.99% | -1.36% | 1.53% | 3.23 | 0.015 | 76.47% |
| MA7 | short | `S03_RALLY_DISTRIBUTION` | 强上涨后低区间横盘派发 | 4,251 | -2.42% | -1.58% | 0.88% | 2.02 | 0.087 | 64.71% |
| MA7 | short | `S08_EUPHORIC_BREADTH_ROLLOVER` | 市场宽度极高但过去10日下降 | 1,551 | -2.91% | -2.35% | 0.30% | 0.44 | 0.795 | 58.33% |
| MA7 | short | `S06_BEAR_TREND_CONTINUATION` | 空头排列中的顺势下破 | 4,187 | -3.07% | -1.84% | 0.15% | 0.23 | 0.894 | 41.18% |
| MA7 | short | `S05_BEAR_TREND_BOUNCE_FAILURE` | 空头排列中的小反弹失败 | 4,006 | -3.20% | -2.04% | 0.00% | 0.00 | 0.999 | 41.18% |
| MA7 | short | `S07_FAILED_BULL_TREND_REVERSAL` | 多头排列但已从20日高点明显回落 | 3,751 | -3.92% | -1.91% | -0.79% | -1.10 | 0.407 | 35.29% |
| MA30 | long | `L07_FAILED_BEAR_TREND_REVERSAL` | 空头排列中强反弹后的向上突破 | 1,284 | 12.55% | 2.94% | 9.83% | 2.17 | 0.079 | 86.67% |
| MA30 | long | `L01_CRASH_REVERSAL` | 20日暴跌且仍处60日深回撤 | 305 | 10.74% | 3.73% | 7.39% | 2.10 | 0.079 | 80.00% |
| MA30 | long | `L08_DEPRESSED_BREADTH_REVERSAL` | 市场宽度低位但过去10日改善 | 624 | 10.14% | 2.60% | 6.91% | 1.12 | 0.363 | 72.73% |
| MA30 | long | `L02_DEEP_DRAWDOWN_RECOVERY` | 60日深回撤后已从20日低点反弹 | 2,588 | 8.34% | 2.94% | 5.75% | 2.52 | 0.043 | 70.59% |
| MA30 | long | `L11_HIGH_VOL_CAPITULATION` | 高波环境中的20日暴跌反转 | 203 | 9.15% | 3.77% | 5.73% | 1.71 | 0.162 | 100.00% |
| MA30 | long | `L04_EARLY_RECOVERY_BELOW_MA30` | 仍在MA30下方的深回撤早期修复 | 4,428 | 6.19% | 2.41% | 3.69% | 2.63 | 0.043 | 64.71% |
| MA30 | short | `S10_LOW_VOL_DISTRIBUTION` | 低波低区间横盘后向下跌破 | 5,250 | -2.09% | -1.28% | 1.98% | 2.23 | 0.308 | 64.71% |
| MA30 | short | `S03_RALLY_DISTRIBUTION` | 强上涨后低区间横盘派发 | 2,959 | -2.76% | -1.69% | 0.83% | 0.99 | 0.505 | 47.06% |
| MA30 | short | `S07_FAILED_BULL_TREND_REVERSAL` | 多头排列但已从20日高点明显回落 | 2,532 | -3.04% | -1.74% | 0.47% | 0.51 | 0.610 | 58.82% |
| MA30 | short | `S12_EXTREME_RUNUP_BREAKDOWN` | 从60日低点上涨超过30%后的下破 | 1,963 | -4.03% | -2.11% | -0.67% | -0.61 | 0.592 | 58.82% |
| MA30 | short | `S02_STRONG_RUNUP_ROLLOVER` | 60日强上涨后已从20日高点回落 | 3,673 | -4.08% | -2.07% | -0.83% | -0.72 | 0.564 | 47.06% |
| MA30 | short | `S04_EARLY_ROLLOVER_ABOVE_MA30` | 仍在MA30上方的强上涨早期转弱 | 5,477 | -4.07% | -1.91% | -0.95% | -0.96 | 0.505 | 23.53% |

## 关键多头结构怎样随时间展开

这些状态在突破后 `1–5D` 没有稳定的增量优势，差异主要在 `10–40D` 展开。因此更像数周级修复/反转延续，而不是突破次日跳一下。

| Trigger | 状态 | Horizon | 样本 | 平均 | 中位 | 相对其余同向突破增量 | 增量t | FDR q |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MA7 | `L02_DEEP_DRAWDOWN_RECOVERY` | 10D | 3,759 | 3.72% | 1.64% | 2.38% | 2.54 | 0.041 |
| MA7 | `L02_DEEP_DRAWDOWN_RECOVERY` | 20D | 3,718 | 8.53% | 3.11% | 5.93% | 2.90 | 0.014 |
| MA7 | `L02_DEEP_DRAWDOWN_RECOVERY` | 40D | 3,653 | 16.13% | 6.14% | 11.03% | 3.49 | 0.001 |
| MA7 | `L04_EARLY_RECOVERY_BELOW_MA30` | 10D | 3,871 | 2.53% | 1.38% | 1.06% | 1.56 | 0.183 |
| MA7 | `L04_EARLY_RECOVERY_BELOW_MA30` | 20D | 3,837 | 7.06% | 2.70% | 4.32% | 2.68 | 0.020 |
| MA7 | `L04_EARLY_RECOVERY_BELOW_MA30` | 40D | 3,772 | 14.91% | 5.77% | 9.71% | 3.55 | 0.001 |
| MA30 | `L01_CRASH_REVERSAL` | 10D | 311 | 2.01% | 1.68% | 0.41% | 0.46 | 0.942 |
| MA30 | `L01_CRASH_REVERSAL` | 20D | 305 | 10.74% | 3.73% | 7.39% | 2.10 | 0.079 |
| MA30 | `L01_CRASH_REVERSAL` | 40D | 301 | 14.75% | 7.65% | 8.34% | 2.35 | 0.051 |
| MA30 | `L02_DEEP_DRAWDOWN_RECOVERY` | 10D | 2,614 | 2.80% | 1.47% | 1.41% | 1.59 | 0.407 |
| MA30 | `L02_DEEP_DRAWDOWN_RECOVERY` | 20D | 2,588 | 8.34% | 2.94% | 5.75% | 2.52 | 0.043 |
| MA30 | `L02_DEEP_DRAWDOWN_RECOVERY` | 40D | 2,555 | 15.46% | 5.31% | 10.53% | 2.66 | 0.029 |
| MA30 | `L04_EARLY_RECOVERY_BELOW_MA30` | 10D | 4,459 | 2.18% | 1.22% | 0.78% | 1.14 | 0.654 |
| MA30 | `L04_EARLY_RECOVERY_BELOW_MA30` | 20D | 4,428 | 6.19% | 2.41% | 3.69% | 2.63 | 0.043 |
| MA30 | `L04_EARLY_RECOVERY_BELOW_MA30` | 40D | 4,375 | 11.66% | 4.97% | 6.95% | 2.89 | 0.029 |
| MA30 | `L07_FAILED_BEAR_TREND_REVERSAL` | 10D | 1,289 | 4.17% | 1.27% | 2.78% | 1.68 | 0.407 |
| MA30 | `L07_FAILED_BEAR_TREND_REVERSAL` | 20D | 1,284 | 12.55% | 2.94% | 9.83% | 2.17 | 0.079 |
| MA30 | `L07_FAILED_BEAR_TREND_REVERSAL` | 40D | 1,270 | 21.50% | 6.15% | 16.18% | 2.04 | 0.075 |

## 去掉明显跳空后的诊断

下表只保留突破日绝对 gap 不超过 `1%` 的事件。关键修复结构的 20D 均值仍为正，说明结果不只是财报或隔夜跳空机械造成；`2%/3%` 阈值也已保存在 robustness 机器表中。

| Trigger | 状态 | 样本 | 20D平均 | 中位 | 胜率 | t |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MA7 | `L02_DEEP_DRAWDOWN_RECOVERY` | 1,756 | 5.74% | 2.45% | 58.66% | 3.28 |
| MA7 | `L04_EARLY_RECOVERY_BELOW_MA30` | 1,934 | 3.33% | 2.61% | 59.31% | 6.61 |
| MA30 | `L01_CRASH_REVERSAL` | 97 | 10.66% | 1.59% | 55.67% | 1.77 |
| MA30 | `L02_DEEP_DRAWDOWN_RECOVERY` | 1,363 | 7.84% | 2.27% | 57.81% | 2.08 |
| MA30 | `L04_EARLY_RECOVERY_BELOW_MA30` | 2,519 | 5.34% | 2.01% | 57.09% | 2.56 |
| MA30 | `L07_FAILED_BEAR_TREND_REVERSAL` | 711 | 12.69% | 2.30% | 58.79% | 1.76 |

## 各结构维度的最好与最差档

| Trigger | 方向 | 维度 | 最好档/20D | 最差档/20D | 最大差 |
| --- | --- | --- | ---: | ---: | ---: |
| MA7 | long | 市场宽度10日变化 | RISING_GT_10PP / 3.34% | STABLE_-10PP_10PP / 2.91% | 0.43% |
| MA7 | long | 站上MA30的市场宽度 | DEPRESSED_LT_35 / 5.48% | BROAD_GT_65 / 2.01% | 3.47% |
| MA7 | long | 60日高点回撤 | DEEP_LE_-20 / 9.30% | NEAR_HIGH_GT_-5 / 1.57% | 7.73% |
| MA7 | long | MA30/60/120层级 | BEAR_STACK / 5.99% | MIXED / 2.02% | 3.96% |
| MA7 | long | 归一化ATR历史位置 | Q5_HIGH / 5.30% | Q1_LOW / 2.17% | 3.13% |
| MA7 | long | QQQ市场阶段 | bear / 6.88% | bull / 2.42% | 4.46% |
| MA7 | long | 价格相对MA30的ATR距离 | BELOW_-2ATR_0 / 3.67% | ABOVE_0_2ATR / 2.45% | 1.22% |
| MA7 | long | 20日价格区间历史位置 | Q4 / 4.40% | Q1_COMPRESSED / 2.07% | 2.33% |
| MA7 | long | 从20日低点反弹 | REBOUND_GE_15 / 4.79% | LT_3 / 2.25% | 2.54% |
| MA7 | long | 过去20日涨跌路径 | CRASH_LE_-10 / 4.88% | SIDEWAYS_-3_3 / 2.39% | 2.49% |
| MA7 | long | 60日低点涨幅 | EXTREME_GE_30 / 5.36% | STRONG_15_30 / 2.08% | 3.29% |
| MA7 | short | 市场宽度10日变化 | STABLE_-10PP_10PP / -2.88% | FALLING_LT_-10PP / -3.61% | 0.73% |
| MA7 | short | 站上MA30的市场宽度 | BROAD_GT_65 / -2.21% | DEPRESSED_LT_35 / -6.02% | 3.81% |
| MA7 | short | 60日高点回撤 | NEAR_HIGH_GT_-5 / -2.15% | DEEP_LE_-20 / -10.20% | 8.06% |
| MA7 | short | MA30/60/120层级 | MIXED / -2.12% | BEAR_STACK / -6.07% | 3.95% |
| MA7 | short | 归一化ATR历史位置 | Q1_LOW / -2.27% | Q5_HIGH / -5.36% | 3.09% |
| MA7 | short | QQQ市场阶段 | bull / -2.45% | bear / -7.33% | 4.87% |
| MA7 | short | 价格相对MA30的ATR距离 | FAR_ABOVE_GT_2ATR / -2.68% | FAR_BELOW_LT_-2ATR / -5.02% | 2.34% |
| MA7 | short | 20日价格区间历史位置 | Q1_COMPRESSED / -2.26% | Q4 / -4.76% | 2.50% |
| MA7 | short | 从20日低点反弹 | LT_3 / -1.90% | REBOUND_GE_15 / -5.82% | 3.92% |
| MA7 | short | 过去20日涨跌路径 | UP_3_10 / -2.78% | CRASH_LE_-10 / -6.25% | 3.48% |
| MA7 | short | 60日低点涨幅 | LOW_LT_5 / -1.77% | EXTREME_GE_30 / -4.86% | 3.09% |
| MA30 | long | 市场宽度10日变化 | RISING_GT_10PP / 4.42% | STABLE_-10PP_10PP / 2.04% | 2.38% |
| MA30 | long | 站上MA30的市场宽度 | DEPRESSED_LT_35 / 5.57% | BROAD_GT_65 / 2.71% | 2.86% |
| MA30 | long | 60日高点回撤 | DEEP_LE_-20 / 12.57% | NEAR_HIGH_GT_-5 / 1.28% | 11.29% |
| MA30 | long | MA30/60/120层级 | BEAR_STACK / 6.18% | MIXED / 2.19% | 4.00% |
| MA30 | long | 归一化ATR历史位置 | Q5_HIGH / 5.93% | Q1_LOW / 2.05% | 3.87% |
| MA30 | long | QQQ市场阶段 | bear / 8.24% | bull / 2.59% | 5.65% |
| MA30 | long | 价格相对MA30的ATR距离 | BELOW_-2ATR_0 / 3.50% | FAR_BELOW_LT_-2ATR / 2.40% | 1.10% |
| MA30 | long | 20日价格区间历史位置 | Q4 / 6.37% | Q1_COMPRESSED / 2.44% | 3.94% |
| MA30 | long | 从20日低点反弹 | REBOUND_GE_15 / 10.99% | LT_3 / 1.73% | 9.26% |
| MA30 | long | 过去20日涨跌路径 | CRASH_LE_-10 / 9.43% | SIDEWAYS_-3_3 / 2.77% | 6.66% |
| MA30 | long | 60日低点涨幅 | EXTREME_GE_30 / 5.67% | LOW_LT_5 / 1.48% | 4.20% |
| MA30 | short | 市场宽度10日变化 | STABLE_-10PP_10PP / -2.69% | RISING_GT_10PP / -3.94% | 1.25% |
| MA30 | short | 站上MA30的市场宽度 | BROAD_GT_65 / -2.38% | DEPRESSED_LT_35 / -9.27% | 6.89% |
| MA30 | short | 60日高点回撤 | NEAR_HIGH_GT_-5 / -1.93% | DEEP_LE_-20 / -15.74% | 13.81% |
| MA30 | short | MA30/60/120层级 | MIXED / -2.06% | BEAR_STACK / -7.98% | 5.92% |
| MA30 | short | 归一化ATR历史位置 | Q1_LOW / -2.09% | Q5_HIGH / -6.32% | 4.23% |
| MA30 | short | QQQ市场阶段 | bull / -2.40% | bear / -11.09% | 8.69% |
| MA30 | short | 价格相对MA30的ATR距离 | FAR_ABOVE_GT_2ATR / -0.85% | ABOVE_0_2ATR / -3.49% | 2.64% |
| MA30 | short | 20日价格区间历史位置 | Q2 / -2.37% | Q4 / -8.57% | 6.20% |
| MA30 | short | 从20日低点反弹 | LT_3 / -1.21% | REBOUND_GE_15 / -8.59% | 7.37% |
| MA30 | short | 过去20日涨跌路径 | SIDEWAYS_-3_3 / -3.28% | SURGE_GE_10 / -5.90% | 2.62% |
| MA30 | short | 60日低点涨幅 | LOW_LT_5 / -0.51% | EXTREME_GE_30 / -4.03% | 3.52% |

## 如何解读

- 正均值不等于有效过滤；必须再看相对其余事件的增量、FDR 和分年稳定性。
- 一个状态可以同时属于多个结构，例如“深回撤修复”也可能是“低宽度反转”；状态不是互斥分类器。
- event-day gap 和 MA7/MA30 同时跨越单独保存，不混入 `t-1` 市场状态。
- 全样本排名只为找下一轮应冻结验证的少量机制，不能直接写交易规则。

合同：[Y3 structure atlas contract](../specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-contract-2026-08-25.md)。
