# BIN-1D-TPSA-P0：突破前市场状态地图结果

## 先说这轮到底做了什么

这不是策略回测。MA7 和 MA30 只是用来标记突破发生的时间；所有市场状态都只看突破前一日及更早的 60 日路径。统计覆盖大跌/大涨后的修复或横盘、原趋势回踩、持续推进、衰竭、低波压缩、高波乱震和 ATR 收缩/扩张。

样本共 390,381 个多均线事件，646 个历史合约，日期从 2020-01-09 到 2026-06-30。全部是已经揭示的探索性历史，不是新 OOS。

## MA7 / MA30 事件数量

| MA | 方向 | 事件数 | 合约数 | 发生日期数 |
| --- | --- | ---: | ---: | ---: |
| MA7 | long | 48,765 | 643 | 1,943 |
| MA7 | short | 48,864 | 644 | 1,907 |
| MA30 | long | 20,234 | 633 | 1,738 |
| MA30 | short | 20,396 | 637 | 1,624 |

## 跨 MA 同方向的候选前置状态

### long

| 前置状态 | MA7 后20日 | MA30 后20日 | 两者较弱值 |
| --- | ---: | ---: | ---: |
| OPPOSITE_SHOCK_THEN_REPAIR | 0.422 ATR | 0.252 ATR | 0.252 ATR |
| FAST_REVERSAL | 2.818 ATR | 0.063 ATR | 0.063 ATR |
| HIGH_VOL_CHOP | 0.055 ATR | 0.022 ATR | 0.022 ATR |

### short

| 前置状态 | MA7 后20日 | MA30 后20日 | 两者较弱值 |
| --- | ---: | ---: | ---: |
| ORDERLY_TREND_PULLBACK_RESUME | 0.827 ATR | 1.808 ATR | 0.827 ATR |
| LARGE_MOVE_THEN_SIDEWAYS_BREAK | 0.397 ATR | 0.535 ATR | 0.397 ATR |
| LOW_VOL_COMPRESSION | 0.282 ATR | 0.424 ATR | 0.282 ATR |
| FAST_REVERSAL | 0.951 ATR | 0.262 ATR | 0.262 ATR |
| EXTENDED_MOVE_EXHAUSTION | 0.197 ATR | 0.309 ATR | 0.197 ATR |

## 年份稳定性

满足至少 4 个年份、其中至少 70% 年份为正的 MA×方向×状态组合共有 7 个。这只是探索性稳定度，不是交易通过。

## 机器学习有没有学到前置状态

模型只看突破前状态，分别训练 MA7/MA30 与多空；没有选交易或做账户。下面给出各组跨年份平均排序能力。RankIC 接近零代表没有学到稳定排序。

| MA | 方向 | 模型 | 正RankIC年份/总年份 | 平均RankIC | 预测头尾十分位实际差 |
| --- | --- | --- | ---: | ---: | ---: |
| MA7 | long | LIGHTGBM | 3/5 | 0.017 | 0.134 ATR |
| MA7 | long | TREE | 2/5 | 0.009 | 0.729 ATR |
| MA7 | short | LIGHTGBM | 2/5 | -0.020 | 0.022 ATR |
| MA7 | short | TREE | 2/5 | -0.014 | -0.541 ATR |
| MA30 | long | LIGHTGBM | 2/4 | 0.005 | -0.142 ATR |
| MA30 | long | TREE | 2/4 | 0.036 | -0.216 ATR |
| MA30 | short | LIGHTGBM | 1/4 | -0.062 | -0.748 ATR |
| MA30 | short | TREE | 1/4 | -0.074 | -1.438 ATR |

## 怎么读文件

- [旧走势 × 最近走势完整矩阵](../artifacts/binance_1d_tpsa_p0_move_transition_matrix.csv)：直接找“大跌后修复”“大涨后横盘”等路径。
- [波动水平 × 波动变化矩阵](../artifacts/binance_1d_tpsa_p0_volatility_state_matrix.csv)：低波/高波与收缩/扩张分开看。
- [固定可读形态统计](../artifacts/binance_1d_tpsa_p0_hypothesis_stats.csv)：十三种命名假设逐项结果。
- [逐年稳健性](../artifacts/binance_1d_tpsa_p0_hypothesis_robustness.csv)：检查是否只靠某一年。
- [MA7/MA30一致性](../artifacts/binance_1d_tpsa_p0_ma_consistency.csv)：检查是不是均线参数巧合。
- [机器学习逐年前推](../artifacts/binance_1d_tpsa_p0_ml_walk_forward_metrics.csv)：只看模型能不能给前置状态稳定排序。
- [可读决策树规则](../artifacts/binance_1d_tpsa_p0_tree_rules.txt)：模型从历史里切出的前置状态。

## 决策边界

本轮不输出策略年化、回撤或买卖规则。只有跨 MA、跨年份、样本充足且人工状态表与模型排序一致的状态，才进入下一轮冻结确认；否则结论就是现有价格路径仍不足以稳定过滤趋势突破。
