# BTC-15M-Trend-Continuation Decision Log

## 2026-07-20

决定建立 `BTC-15M-Trend-Continuation` 研究家族，并把 `lvcb-913f4ff89386` 保留为 `explore` 研究候选：它通过长历史开发、双倍成本、滚动窗口与 trade-block bootstrap 审计，但历史数据已经被机制发现和筛选使用，且近期表现恶化，因此不登记版本、不 promotion、not live-ready。证据：[长历史搜索诊断](diagnostics/btc-15m-trend-continuation-long-history-search-2026-07-20.md)。

## 2026-07-20（六轮迭代）

宏观动量、趋势质量、突破质量、波动带、退出结构和 cooldown 六轮共 `256` 个有效变体均未通过父子采纳门槛；决定保持父候选不变，停止基于既有历史继续扩搜，仅等待 prospective 新证据。证据：[六轮迭代诊断](diagnostics/btc-15m-lvcb-iteration-rounds-2026-07-20.md)。

## 2026-07-21（空头专属搜索）

空头专属 `576` 个信号、`804` 个总配置没有任何 development gate 通过项，最佳近失项在 reused diagnostic 为 `-11.05%`、双倍成本为 `-34.98%`；决定不新增空头候选，保持 `lvcb-913f4ff89386` long-only，并停止对称 breakdown 空头历史调参。证据：[空头专属搜索诊断](diagnostics/btc-15m-lvcb-short-search-2026-07-21.md)。
