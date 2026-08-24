# Decision Log

## 2026-08-06 — 冻结用户指定 SMA7-RSI6 状态机

决定：最近三根中任一 RSI6 `>70` 解释为 overbought memory；空头 RSI6 `<30` 后只平仓等待，MA 使用 SMA7。该机制独立于纯 MA7 反手与 4H MA7-ABT，本轮固定参数回测但不自动登记。证据：[冻结合同](specs/hype-4h-ma7-rsi6-asymmetric-reversal-contract-2026-08-06.md)。

## 2026-08-06 — 原生相位盈利但相位门禁失败

决定：原生 UTC 相位全期成本后 `+113.10%`，但 `1h/2h` 相位为 `-51.65% / -78.77%`，且无 stop 时有效杠杆最高显著漂升；因此仅保留有趣的历史观察，不登记、不推进 runner。证据：[基准诊断](diagnostics/hype-4h-ma7-rsi6-asymmetric-reversal-baseline-2026-08-06.md)。

## 2026-08-07 — V2 Cross-Reentry 不采纳

决定：保留多头做空的 RSI6 超买过滤，只增加空头重新站上 SMA7 时直接反多；该改动使全期从 `+113.10%` 降至 `+12.16%`，交易从 81 增至 139 笔，short PF 降至 `0.83`，且无 buy-and-hold 超额，因此 V2 只保留失败观察，不登记、不替换 V1 baseline。证据：[V2 诊断](diagnostics/hype-4h-ma7-rsi6-cross-reentry-v2-observation-2026-08-07.md)。
