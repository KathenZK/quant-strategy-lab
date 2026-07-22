# MU-15M-Donchian-Trend-Breakout 决策日志

## 2026-07-20 — 冻结低自由度搜索协议

新建独立 Donchian 趋势突破家族，仅搜索 18 组 `entry lookback × ATR stop × EMA regime`，固定 1x、严格成本和执行时序；参数只用 train/validation 选择，final audit 只揭示一次，未通过时停止扩搜。

证据：[冻结搜索诊断](diagnostics/mu-15m-dtb-frozen-search-2026-07-20.md)

## 2026-07-20 — Final audit 未通过，停止扩搜

唯一开发候选 `dtb-5e79abef48cf` 在 final audit 为 `-4.13%` 且仅 2 笔，判定 `sample_insufficient / final gate failed`；不登记版本、不 promotion、不围绕 near-miss 扩搜。

证据：[冻结搜索与 final audit](diagnostics/mu-15m-dtb-frozen-search-2026-07-20.md)
