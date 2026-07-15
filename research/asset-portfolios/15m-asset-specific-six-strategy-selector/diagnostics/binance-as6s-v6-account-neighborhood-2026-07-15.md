# BIN-15M-AS6S V6 账户邻域稳定性（2026-07-15）

每次只替换一条腿为已通过单腿稳健排序的邻近候选；另独立扰动账户scale与抢占参数。所有变体均重放联合单仓账户。

| 路线 | 腿候选通过率 | scale邻域通过率 | 抢占参数通过率 | 联合邻域通过率 |
|---|---:|---:|---:|---:|
| `nonpreemptive` | 66.67% | 80.00% | 不适用 | 66.67% |
| `strong_breakout_preemptive` | 80.61% | 100.00% | 100.00% | 81.90% |

通过率只说明开发样本局部稳定性，不替代未来OOS；任何失败变体及其具体门槛保留在结构化结果中。

结构化结果：[`binance_as6s_v6_account_neighborhood_2026-07-15.json`](../artifacts/binance_as6s_v6_account_neighborhood_2026-07-15.json)。
