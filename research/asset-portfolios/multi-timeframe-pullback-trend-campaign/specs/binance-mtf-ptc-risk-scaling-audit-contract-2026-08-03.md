# BIN-MTF-PTC 风险缩放审计合同

只对 V1 唯一保持正证据的 BTC `weekly_monthly_consensus + 3 layers + no half-reduce + market restart` 做机械风险缩放；ETH/HYPE 因 base/stress 失败不得靠放大风险救参。Locked evaluation 不运行。

冻结档位：

| 档位 | 每层请求风险 | operational cap | hard cap | effective leverage cap |
|---|---:|---:|---:|---:|
| 1x | 0.25% | 0.9% | 1.0% | 3x |
| 2x | 0.50% | 1.8% | 2.0% | 3x |
| 3x | 0.75% | 2.7% | 3.0% | 3x |

信号、meter、入口、stop、layer、退出完全不变。分别在 2021/2022/2023 development folds 和 revealed diagnostic validation 跑 base 4bps 与 stress 8bps，报告年化倍数、MDD、bar 内回撤、最大有效杠杆、实际 stop risk 和风险违规。

目标判断：

- 任一档位 MDD >20%、effective leverage >3x 或 hard risk violation，档位不可用；
- 若合规档位仍远低于 20x annual equity multiple，说明缺口来自机制 alpha，不是仓位未放大；
- 不允许用线性外推结果冒充回测，只可额外报告达到 20x 所需的对数增长倍数，作为不可能性边界。
