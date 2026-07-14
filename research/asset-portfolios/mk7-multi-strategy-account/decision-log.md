# Binance-MK7-Multi-Strategy-Account Decision Log

## 2026-07-13 — 严格 10d OOS 近乎持平，随后尾部转负

结论：补齐所有输入至 `2026-07-13T12:00Z` 并冻结参数重放，冻结段 747 笔 entry identity 与 exit timestamp 零差异。严格 `2026-07-02T03:00Z` 至 `2026-07-12T03:00Z` 的 10d OOS 为 `+0.01% / -8.99% MDD / 4 trades / 75% 已平仓胜率 / PF 0.97`，没有 MII 交易；随后 HYPE DI 与 TRX Stoch 两笔高杠杆亏损使截至最新闭合时点降至 `-17.49% / -21.98% MDD / 6 trades / 50% win`。该窗口大部分早于外部规格冻结日，不能称 pristine OOS；样本过短且最新尾部已穿 `-20%`，保持 `explore / not promoted / not live-ready`。证据：[严格 10d OOS 报告](notes/mk7-v8-oos-10d-2026-07-13.md)、[OOS 汇总](artifacts/mk7_v8_oos_10d_summary_2026-07-13.json)。

## 2026-07-13 — 关闭全窗 `top_lsr` 数据 blocker，仍不 promote

结论：确认 Binance Vision USD-M `daily/metrics` 提供 HYPE 5m 大户持仓多空比，已下载 `399/399` 天并将 `sum_toptrader_long_short_ratio` 映射为 `top_lsr_pos`；REST 近窗对拍通过。使用全窗 LSR 与 15m MTM 重跑后，K2FQ 从 `92` 降至 `69`（规格 `68`），full/main 入选从 `761/616` 收敛到 `747/602`；full/main 倍数为 `7,464,949.89x / 28,103.55x`，仍未逐笔或哈希对齐，保持 `explore / not promoted / not live-ready`。证据：[回测笔记](notes/mk7-v8-backtest-2026-07-13.md)、[summary](artifacts/mk7_v8_backtest_summary_2026-07-13.json)、[修订阻塞诊断](diagnostics/mk7-v8-reproduction-blocker-2026-07-12.md)。

## 2026-07-13 — `mk7-v8` 独立回测观察（未 promote）

结论：已按外部规格实现并运行独立回测；六币除 SOL(+3) 外原始计数对齐，MII 374≈375，K2FQ 因 `top_lsr` 早段 fail-open 为 92≠68；完整/主窗入选与倍数未达规格声明，保持 `explore / not promoted / not live-ready`。证据：[回测笔记](notes/mk7-v8-backtest-2026-07-13.md)、[summary](artifacts/mk7_v8_backtest_summary_2026-07-13.json)。

## 2026-07-12 — `mk7-v8` 暂停精确复现

结论：外部 `mk7-v8` 规格要求的 MII 分规模 CVD、双所主动流与 K2FQ 外部过滤序列在当时标准数据输入中不完整，且规格未定义双所身份、CVD/失衡公式及验收哈希序列化合同；按规格的 hard-fail 规则不得静默降级后报告收益。证据见 [`mk7-v8` 复现阻塞诊断](diagnostics/mk7-v8-reproduction-blocker-2026-07-12.md)。（后续已用币安单所补数并做独立回测，见 2026-07-13 条目。）
