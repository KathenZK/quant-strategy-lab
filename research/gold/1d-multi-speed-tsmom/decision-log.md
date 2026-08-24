# Decision Log

## 2026-08-18 — 建立独立黄金多速度 TSMOM 基线

按固定 `1M/3M/12M` 文献规则建立新家族；第三方 Stooq `GC.F` 连续合约快照仅作
`raw_unaccepted` 探索，不登记版本、不进入 promotion。证据见[基线规格](specs/gold-1d-ms-tsmom-baseline-2026-08-18.md)与[诊断报告](diagnostics/gold-1d-ms-tsmom-backtest-2026-08-18.md)。

## 2026-08-18 — 补充 2022–2026 独立近期段

Stooq 固定快照止于 2021；同源当前下载受浏览器验证限制，CME 官方连续价格历史需要
DataMine 权限。因此用 Yahoo Chart API `GC=F` raw quote OHLC 建立独立近期段，明确排除
adjusted close，并从 2020-01 预热、2021-12 开始评估。供应商序列不拼接，数据继续保持
`raw_unaccepted`；结果为 diagnostic-only，不改变家族状态。
