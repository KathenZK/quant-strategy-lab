# BNB-1H-Adaptive-Regime rerun 3x 杠杆上限重放 - 2026-07-06

## 背景

2026-07-06 rerun 的唯一冻结 primary 为 `ENS__BNB_1H_AR_N0559088__BNB_1H_AR_N0610751`，机制为趋势 `keltner_break` + 反转 `cci_reversal`。原始冻结版本允许 `BNB_1H_AR_N0559088` 使用 `fixed_leverage=4.0`，导致 locked OOS 内一笔 short stop 损失约 `-32.09%` equity，full max DD 达 `-37.14%`。

本重放将全部组件的 `fixed_leverage` 与 `max_leverage` 约束到不超过 `3.0`，不改变信号、入场、出场、成本、funding、排序和 OOS 边界。

## 3x cap 重放结果

| Window | Annual multiple | Total return | Max DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | `2.42x` | `172.89%` | `-14.58%` | `91.26%` | `103` | `9.174` |
| validation | `2.52x` | `56.89%` | `-13.74%` | `92.11%` | `38` | `60.419` |
| locked OOS | `0.44x` | `-18.57%` | `-28.30%` | `75.00%` | `4` | `0.294` |
| full | `1.95x` | `248.62%` | `-28.30%` | `91.03%` | `145` | `4.488` |

## OOS 主要风险来源

- `2026-06-06T11:00:00Z` short entry `573.700428`，`2026-06-15T00:00:00Z` stop exit `618.6387169847503`。
- 原始 `4x` equity return 为 `-32.09%`；3x cap 后单笔 equity return 为 `-24.07%`。
- 该笔仍使 locked OOS max DD 达 `-28.30%`，超过 `20%` 上限。

## 结论

3x cap 能显著降低尾部亏损，但不足以让该 primary 通过 hard gate。`BNB-1H-Adaptive-Regime` 继续维持 `NO-GO / not promoted / not live-ready`。后续若继续研究 1h，搜索空间应硬性约束 `max_leverage <= 3.0`，并优先降低单笔权益风险、收窄或重新设计 `keltner_break` 宽止损 short 逻辑。
