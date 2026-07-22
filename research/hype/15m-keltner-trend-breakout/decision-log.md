# HYPE-15M-KTB 决策日志

- 2026-07-20：纯 Keltner 通道精简机制在当前成本与可执行成交口径下失败；主口径 full `-86.46% / -89.60% MaxDD`，固定 `1x` 仍为 `-73.56% / -78.46%`，K2 时序虽改善 full 收益但回撤仍达 `-72.43%` 且近期切片恶化。决定保持 `explore / not promoted / not live-ready`，不登记版本、不在相同纯通道机制下扩搜。证据见[首轮回测诊断](diagnostics/hype-15m-keltner-only-initial-backtest-2026-07-20.md)。
- 2026-07-21：预先冻结的外轨事件突破、压缩扩张突破和中轨趋势回踩三条新机制全部失败，零手续费/零滑点后 full 仍分别为 `-88.96%`、`-36.15%`、`-15.52%`。决定不登记 V1，并停止当前纯 Keltner 家族扩搜；证据见[新机制假设诊断](diagnostics/hype-15m-keltner-mechanism-hypotheses-2026-07-21.md)。
