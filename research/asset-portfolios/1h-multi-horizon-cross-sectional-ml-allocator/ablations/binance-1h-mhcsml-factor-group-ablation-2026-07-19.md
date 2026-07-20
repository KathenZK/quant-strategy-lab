# BIN-1H-MHCSML 历史因子组消融与 Tail IC 审计（2026-07-19）

## 结论

本审计只读取 `< 2026-04-01 00:00 UTC` 的历史 development OOF 数据，未读取 prospective OOS 的标签、收益、PnL、IC 或绩效。按冻结契约中的“因子组方向稳定、尾部 IC 方向一致”口径，本轮为 `PASS`；它不替代未来 OOS，也不改变 R4 的任何模型、阈值或 allocator。

关键结果：

- stable-full 48h short-return seed 42 的 mean cross-sectional rank IC 为 `0.08230`，`7/7` outer folds 为正；
- funding、lifecycle、trend-breakout、volatility-tail 四组分别在至少 `5/7` folds 置乱后令 IC 下降；
- short-MAE quantile 的 `28/28` fold-seed IC 为正，均值 `0.37870`，最差 `0.31939`；
- short-squeeze classification 的 `28/28` fold-seed IC 为正，均值 `0.30497`，最差 `0.24056`；
- 因子作用并不均衡：volatility-tail 组占全部正向 IC drop 的 `87.62%`，这是明确的模型依赖风险。

## 方法

收益模型使用 seed 42 的 7 个 stable-full 48h short-return OOF LightGBM。每次只对一个因子组做“同一时点内按 symbol 循环移动一位”的确定性置乱，保持该组的横截面分布但破坏 symbol 与因子值的对应，再比较置乱前后的 mean cross-sectional rank IC。

这是 permutation ablation，不是逐组重训。它回答“已训练模型是否依赖该组信息”，不能证明删组后重新训练一定得到相同变化。完整逐 fold 明细见 [`historical_factor_group_ablation_2026-07-19.csv`](../artifacts/historical_factor_group_ablation_2026-07-19.csv)，机器可读结论见 [`historical_factor_group_ablation_2026-07-19.json`](../artifacts/historical_factor_group_ablation_2026-07-19.json)。

## 分组结果

| 因子组 | 因子数 | 置乱后 IC | IC drop | IC drop 为正的 folds |
| --- | ---: | ---: | ---: | ---: |
| volatility-tail | 77 | 0.00554 | 0.07675 | 7/7 |
| lifecycle | 1 | 0.07741 | 0.00488 | 5/7 |
| trend-breakout | 33 | 0.07775 | 0.00455 | 6/7 |
| funding-carry | 15 | 0.08094 | 0.00136 | 5/7 |
| mark-basis-premium | 17 | 0.08225 | 0.00004 | 3/7 |
| liquidity-volume-flow | 47 | 0.08228 | 0.00002 | 3/7 |
| market-regime-cross-asset | 8 | 0.08229 | 0.00000 | 3/7 |
| momentum-reversal-price-action | 37 | 0.08281 | -0.00052 | 3/7 |

`momentum-reversal-price-action` 的平均 drop 略为负，说明这组在当前已训练模型里不是稳定的独立增益来源；但 R4 冻结后不允许据此删因子重训。相反，这一结果保留为十月揭盲后的新版本研究线索。

## Feature-set 对照边界

历史搜索中，compact、stable-full、tail-stable 和 Ridge 的各自最佳网格行支持“stable-full 提供更多方向信息、tail-only 不足、Ridge 明显落后”的机制判断，但这些行的 cadence、阈值、持仓数和敞口并不完全相同，不能直接当成严格同参数消融。严格 prospective 比较已经另行冻结为同期 Ridge 与规则盲信号。

## 风险与最终门禁

本审计通过的是历史方向稳定门禁，不是最终策略通过。volatility-tail 高度集中意味着：如果未来市场的波动结构发生变化，R4 的 return score 与独立 MAE/squeeze 过滤器可能同时退化。最终仍必须等待 `2026-10-20 21:05 UTC` 后一次性揭盲，并同时检查收益、回撤、胜率、交易数量、压力成本、集中度以及同期 LightGBM 对 Ridge/规则基线的优势。
