# HYPE-30M-Keltner-Breakout-Retest Decision Log

## 2026-07-17：建立独立研究线

结论：建立 `HYPE-30M-Keltner-Breakout-Retest` 独立家族，研究 Keltner 突破后等待回踩并 reclaim 的趋势状态机；目标是提高胜率，但不得以放宽止损、机械缩小止盈或后验删除亏损交易实现。

证据：[README.md](README.md)，[hype-30m-keltner-breakout-retest-core-ledger.md](hype-30m-keltner-breakout-retest-core-ledger.md)。

## 2026-07-17：首轮搜索失败

结论：864 组 upper-retest→reclaim 状态机没有候选达到高于 V3 的全样本与 validation 胜率目标；最接近行仅 `38 笔 / 胜率 60.53% / Return +317.64% / MDD -22.15%`。不登记 V1，停止扩大当前假设的参数网格。

证据：[diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md](diagnostics/hype-30m-keltner-breakout-retest-initial-search-2026-07-17.md)。
