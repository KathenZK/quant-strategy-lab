# Decision Log

## 2026-08-06 — 建立独立 close-reversal 家族

决定：把“闭合 4H 站上 MA7 则下一期开盘做多，闭合跌破则下一期开盘直接反手做空”定义为独立 `HYPE-4H-MA7-Close-Reversal` 零参数基准；它不是现有 4H ABT 的 pullback-reclaim 候选，也不继承日线 V1。证据：[冻结合同](specs/hype-4h-ma7-close-reversal-contract-2026-08-06.md)。

## 2026-08-06 — 零参数基准失败

决定：原始 close-reversal 全期 base / gross 无交易成本分别为 `-90.01% / -52.34%`，四个整点相位全亏且 12 个滚动 90 日窗口仅 2 个为正；因此不登记版本，并停止在同一已揭示历史上直接追加过滤参数。证据：[基准诊断](diagnostics/hype-4h-ma7-close-reversal-baseline-2026-08-06.md)。
