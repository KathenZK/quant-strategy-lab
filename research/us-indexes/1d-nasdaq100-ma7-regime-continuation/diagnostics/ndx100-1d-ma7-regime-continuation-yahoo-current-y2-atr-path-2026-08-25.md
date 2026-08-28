# NDX100-1D-MA7-RC-Y2：Crypto ATR 路径迁移到股票

## 一句话结论

**加密 P2 的两个方向性格子在当前纳指成分股票上未形成稳定可迁移优化：多头仅有20D局部改善，空头方向相反。** 多头外部格相对裸 MA7 的 20 日均值变化为 `0.49%`，但 10D/40D 不保持；空头虽然相对裸样本少亏 `0.81%`，自身 expectancy 仍为负。本轮不根据股票结果换档位或阈值。

## 冻结口径与样本

- Config SHA256：`58196be62c5b4b2a043c13b9651a73c6dcb6efefcf147700e3f8f71def603305`。
- Universe：Yahoo 当前 Nasdaq-100 terminal snapshot `102` 条证券，回填历史，明确 survivorship-biased。
- Eligible：`359,422` security-days、`100` securities，`2010-01-04` 至 `2026-08-21`。
- MA7 events：`77,957`；long `38,988`、short `38,969`。
- 完全复制 Crypto P2：ATR20 十日路径、同股 trailing-60 causal quintile、`TR/ATR20[t-1]` 的 0.8/1.2、MA slope aligned。

## 过滤前与外部格

每格为 `样本 / 20D平均 / 中位数 / 胜率 / 双向聚类t`。

| 口径 | long | short |
| --- | ---: | ---: |
| ALL_MA7 | 38,778 / 3.18% / 1.49% / 57.87% / t=7.87 | 38,776 / -3.20% / -1.53% / 41.95% / t=-8.23 |
| CRYPTO_TRANSFER_DIRECTIONAL_CELL | 1,607 / 3.68% / 1.37% / 57.62% / t=3.08 | 2,134 / -2.39% / -1.16% / 43.30% / t=-5.56 |

## 外部格相对其余 MA7 事件的增量

每行用事件级回归估计候选格与同方向其余 MA7 事件的均值差，标准误按股票和日期双向聚类。

| 方向 | 周期 | 外部格均值 | 其余事件均值 | 增量 | 增量t |
| --- | ---: | ---: | ---: | ---: | ---: |
| long | 10D | 1.51% | 1.57% | -0.05% | t=-0.09 |
| long | 20D | 3.68% | 3.16% | 0.52% | t=0.45 |
| long | 40D | 4.49% | 6.32% | -1.83% | t=-1.53 |
| short | 10D | -1.25% | -1.53% | 0.28% | t=0.82 |
| short | 20D | -2.39% | -3.24% | 0.85% | t=1.64 |
| short | 40D | -6.50% | -6.39% | -0.11% | t=-0.10 |

## ATR 路径五档

先要求 MA7 slope aligned。每格为 `次数 / 20D平均 / 中位数`；Q1 是最快收缩，Q5 是最快扩张。

| ATR path | long | short |
| --- | ---: | ---: |
| Q1 | 4,948 / 3.11% / 1.43% | 4,403 / -2.69% / -1.47% |
| Q2 | 4,181 / 3.51% / 1.51% | 3,873 / -3.52% / -1.43% |
| Q3 | 3,881 / 2.45% / 1.35% | 3,459 / -2.21% / -1.31% |
| Q4 | 3,798 / 2.69% / 1.45% | 3,499 / -3.67% / -1.71% |
| Q5 | 3,463 / 3.10% / 1.51% | 3,273 / -2.87% / -1.60% |

## Crypto 预先指定的两个 burst 格

| 外部格 | 样本 / 20D平均 / 中位数 / 胜率 / t |
| --- | ---: |
| LONG_FAST_EXPANSION_BURST | 1,607 / 3.68% / 1.37% / 57.62% / t=3.08 |
| SHORT_FAST_CONTRACTION_BURST | 2,134 / -2.39% / -1.16% / 43.30% / t=-5.56 |

## QQQ 市场阶段

| 外部格 | QQQ phase | 样本 / 20D平均 / 中位数 / 胜率 / t |
| --- | --- | ---: |
| LONG_FAST_EXPANSION_BURST | bull | 1,061 / 3.38% / 0.90% / 54.57% / t=2.13 |
| LONG_FAST_EXPANSION_BURST | bear | 193 / 3.43% / 2.07% / 64.25% / t=3.35 |
| LONG_FAST_EXPANSION_BURST | transition | 353 / 4.68% / 1.94% / 63.17% / t=1.98 |
| SHORT_FAST_CONTRACTION_BURST | bull | 1,306 / -2.37% / -0.84% / 44.03% / t=-4.74 |
| SHORT_FAST_CONTRACTION_BURST | bear | 246 / -5.01% / -4.17% / 39.02% / t=-2.41 |
| SHORT_FAST_CONTRACTION_BURST | transition | 582 / -1.32% / -1.19% / 43.47% / t=-1.87 |

## 与 Crypto 直接对照

定义和 20D trigger-close raw return 一致；资产池和交易日结构不同。

| 外部格 | 市场 | 样本 / 20D平均 / 中位数 / 胜率 / t |
| --- | --- | ---: |
| LONG_FAST_EXPANSION_BURST | Crypto | 2,232 / 6.37% / -0.53% / 48.92% / t=2.42 |
| LONG_FAST_EXPANSION_BURST | Nasdaq100CurrentYahoo | 1,607 / 3.68% / 1.37% / 57.62% / t=3.08 |
| SHORT_FAST_CONTRACTION_BURST | Crypto | 2,335 / 4.89% / 6.88% / 67.19% / t=3.28 |
| SHORT_FAST_CONTRACTION_BURST | Nasdaq100CurrentYahoo | 2,134 / -2.39% / -1.16% / 43.30% / t=-5.56 |

## ATR path 与旧 RV252 的同样本分离度

| 分类 | 方向 | Q5-Q1 | 最大-最小 | Q顺序Spearman |
| --- | --- | ---: | ---: | ---: |
| ATR_PATH_60 | long | -0.04% | 1.10% | -0.50 |
| ATR_PATH_60 | short | -0.12% | 1.39% | -0.30 |
| HISTORICAL_RV_252 | long | 2.35% | 2.62% | 0.70 |
| HISTORICAL_RV_252 | short | -1.80% | 2.07% | -0.80 |

## 裁决边界

- 这是事件统计，不是账户策略回测；没有 next-open、持仓冲突、费用、分红、借券、退出、年化或回撤。
- Y2 参数来自 Crypto P2，股票结果只做 accept/reject/partial-transfer，不允许挑出股票端最好格另称“优化成功”。
- 历史 PIT Y1 仍因 `81.18%` 覆盖 fail closed；Y2 不能清除当前成分回填的 survivorship bias。

合同：[Y2 ATR path contract](../specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-contract-2026-08-25.md)。
