# HYPE-1D-MA7-ABT V6 漏趋势归因与隔离 Probe 诊断（2026-08-10）

## 裁决

本轮裁决为 **`NON_ECONOMIC_MISSES / post-reveal diagnostic-only`**。

用户观察成立：按 CTLS-R4 的事后稳定方向标签，全窗有 29 个趋势段，V6 只在其中 15 段出现过同向实际持仓，14 段完全未覆盖；按趋势段总时长加权，V6 同向暴露率仅 `39.51%`。但“漏段很多”仍不能推出“把 delayed cross 全部做成小仓 probe 会改善 V6”：

- 固定 `0.25x`、状态隔离、V6 无条件抢占的 probe 共成交 34 笔，覆盖全部 8 个 `54d` block；
- exact V6 为 `+617.11% / -18.39%`，加入 probe 后为 `+496.39% / -21.72%`；
- 收益下降 `120.72pp`，真实 `1h` MDD 恶化 `3.32pp`，收益与回撤双劣；
- `8bps`、funding-off、probe 额外延迟 1 日也全部双劣。

因此，本轮同时确认了两件事：**V6 确有结构性漏趋势；现有因果变量仍无法在事前把这些漏段与大量假 cross 分开。** 不修改 V6，不登记 V7，不开启前瞻 probe。

## 合同、数据与审计边界

- 合同：[漏趋势归因与隔离 Probe 合同](../specs/hype-1d-ma7-v6-missed-trend-attribution-contract-2026-08-10.md)。
- 机器证据：[锁定 JSON](../artifacts/hype_1d_ma7_v6_missed_trend_attribution_2026-08-10.json)及其 [SHA256](../artifacts/hype_1d_ma7_v6_missed_trend_attribution_2026-08-10.sha256)。
- 复现脚本：[归因审计脚本](../scripts/audit_hype_1d_ma7_v6_missed_trend_attribution.py)。
- 市场：Binance USD-M `HYPEUSDT` perpetual；`10,390` 根可信 `1h` K 线、`2,597` 条 funding，聚合为 `[2025-05-31, 2026-08-06)` 的 432 个完整 UTC 日。
- 成本：手续费 `0.001/fill`、基础不利滑点 `4bps/fill`、实际 funding；压力滑点 `8bps/fill`。
- exact V6、PEHC 配置、交易账本、真实 `1h` 风险回放、自建组合回放、非重叠仓位及 terminal equity 共 9 项 invariant 全部通过。
- 全部 432 日早已 researcher-exposed；参考趋势段依赖中心 7 日标签，只能归因，绝不进入 probe 信号。

## 逐段漏识别账

29 个参考段中：

- 任意同向捕获：`15/29 = 51.72%`；
- 按时长加权同向暴露：`39.51%`；
- 捕获来源：native `8` 段、已有仓位 carry `3` 段、PEHC handoff `3` 段、forced reversal `1` 段；
- 完全漏掉：14 段，其中 freshness 失效 10 段、全局 cooldown 3 段、已有仓位占用 1 段；
- 14 个漏段都能找到同方向 raw-cross root，不属于“完全没有当时可知 seed”；
- 其中 9 段的主 root 同时通过固定 5 日趋势标签，且 `1x` 固定 5 日 standalone 在成本/funding 后为正；另外 5 段本身不经济。

| 段 | 方向 | 参考区间 UTC | 主因 | 主 root 固定 5 日净收益 | 5 日趋势标签 |
| --- | --- | --- | --- | ---: | --- |
| `REF002` | short | 2025-06-16 → 2025-06-19 | freshness 失效 | `+3.20%` | PASS |
| `REF006` | long | 2025-08-04 → 2025-08-13 | freshness 失效 | `+15.72%` | PASS |
| `REF009` | long | 2025-09-28 → 2025-10-02 | cooldown | `-0.64%` | FAIL |
| `REF010` | short | 2025-10-03 → 2025-10-10 | freshness 失效 | `+9.07%` | PASS |
| `REF011` | long | 2025-10-22 → 2025-10-27 | cooldown | `+18.08%` | PASS |
| `REF012` | short | 2025-10-28 → 2025-11-03 | freshness 失效 | `+0.34%` | PASS |
| `REF015` | short | 2026-01-16 → 2026-01-22 | freshness 失效 | `-6.00%` | FAIL |
| `REF017` | short | 2026-02-06 → 2026-02-09 | freshness 失效 | `-6.68%` | FAIL |
| `REF020` | long | 2026-04-04 → 2026-04-14 | freshness 失效 | `+5.40%` | PASS |
| `REF021` | short | 2026-04-15 → 2026-04-20 | freshness 失效 | `-2.11%` | FAIL |
| `REF022` | long | 2026-05-01 → 2026-05-05 | freshness 失效 | `-1.93%` | FAIL |
| `REF024` | long | 2026-05-28 → 2026-05-31 | cooldown | `+13.06%` | PASS |
| `REF026` | long | 2026-06-12 → 2026-06-16 | 仓位占用 | `+12.21%` | PASS |
| `REF027` | short | 2026-06-17 → 2026-06-25 | freshness 失效 | `+0.95%` | PASS |

这里的固定 5 日收益是统一经济标签，不是可直接部署的退出规则。

## 为什么 slope 是最大漏口，但不能直接放宽

全窗共有 99 个 raw MA7 cross：

| Cross 日状态 | 数量 |
| --- | ---: |
| 原生 buffer+slope 同日通过 | 28 |
| 只失败 slope | 57 |
| 只失败 buffer | 7 |
| buffer 与 slope 都失败 | 7 |

其中 41 个 root 在 5 日内后来满足原 V6 buffer+slope，30 个在成熟前已经 recross。按固定未来 5 日标签，可评估的 68 个成熟 root 中只有 35 个趋势命中。也就是说，slope 同日约束确实是最大漏口，但允许晚成熟后仍只有约一半 root 看起来像趋势；它没有提供足够精度。

## 隔离 Probe 结果

probe 不改 V6 的仓位、cooldown、OAPP、PEHC 或交易时点；只在 V6 flat 时以 `0.25x` 入场，并在 MA7 recross、5 日到期或下一笔 V6 core entry 时退出。V6 core trade 的方向、时间、价格和退出保持不变，因此本轮已把“挤掉 V6 状态链”的机会成本尽量隔离。

| 路径 | 净收益 | 真实 `1h` MDD | 相对 control 收益 | 相对 control MDD |
| --- | ---: | ---: | ---: | ---: |
| exact V6 control | `+617.11%` | `-18.39%` | — | — |
| V6 + base probe | `+496.39%` | `-21.72%` | `-120.72pp` | `-3.32pp` |
| `8bps` probe 对同成本 control | — | — | `-123.02pp` | `-3.43pp` |
| funding-off probe 对同口径 control | — | — | `-122.12pp` | `-3.33pp` |
| probe 额外延迟 1 日 | — | — | `-107.67pp` | `-5.19pp` |
| 删除最大正贡献 probe | — | — | `-139.59pp` | `-3.32pp` |

34 笔 probe 只有 11 笔盈利：14 笔 long 中 4 笔盈利，直接累计 PnL 约 `-0.0033` equity units，接近持平；20 笔 short 中 7 笔盈利，直接累计 PnL 为 `-0.4705`。short 噪声是主要拖累，probe 亏损又降低后续 core trade 的复利本金，使终值损失大于 probe 逐笔 PnL 之和。

## 事后“看起来可选”的核心陷阱

把 probe 交易事后映射回参考趋势段：

- 落在 14 个漏掉参考段中的 13 笔 probe：8 胜，直接累计 PnL `+0.2380`；
- 其余 21 笔 probe：仅 3 胜，直接累计 PnL `-0.7118`。

这解释了为什么图上逐段挑选会显得很有希望：真正漏段里的 probe 确实总体赚钱；但“该 cross 最终属于稳定漏趋势段”依赖未来中心窗口，是不可用于实盘的事后信息。当前可因果获得的 raw cross、原 buffer/slope 晚成熟、MA7 同侧与固定 5 日寿命，无法复制这层筛选。

## 近期切片

切片沿完整组合权益路径、锚定 `2026-08-06 00:00 UTC`，只作审计：

| 切片 | exact V6 收益 / MDD | V6 + probe 收益 / MDD |
| --- | ---: | ---: |
| `1d` | `0.00% / 0.00%` | `0.00% / 0.00%` |
| `7d` | `+1.63% / -3.49%` | `+1.63% / -3.49%` |
| `1m` | `+18.53% / -8.52%` | `+18.79% / -8.52%` |
| `3m` | `+72.14% / -12.66%` | `+72.62% / -12.66%` |
| `6m` | `+110.43% / -18.39%` | `+99.45% / -21.72%` |
| `1y` | `+365.83% / -18.39%` | `+289.99% / -21.72%` |

最近 1–3 个月的小幅增量不能抵消 6 个月、1 年和全窗的双劣，也不用于选择。

## 决策与下一步

1. 保持 V6 `registered / shadow-only / not promoted / not live-ready`，不改参数、不登记 V7。
2. 关闭“raw cross + 原阈值晚成熟 + 固定小仓”的全量 overlay；即使消除状态挤占，它仍不经济。
3. 不根据 14 个已知漏段反向训练或手工增加筛选条件；那只会把 CTLS-R4 的事后标签泄漏回信号。
4. 若继续，只允许在新数据或独立跨资产长历史上预先冻结一个**不读取未来 reference label**的机会分类器；先验证它能把“漏段内 13 笔”与“其余 21 笔”分开，再讨论 probe PnL。
5. 本轮不生成交易路径 HTML：这是普通 diagnostic，且没有登记新版本或用户图表请求。
