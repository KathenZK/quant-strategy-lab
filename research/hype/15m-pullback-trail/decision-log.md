# HYPE-15M-Pullback-Trail Decision Log

## 2026-06-30: V3.3 机制 15m 迁移诊断

问题：`HYPE-5M-Pullback-Trail-V3.3` 在 `5m` 上的原始回测很强，但严格 live-realistic trailing 口径失败。需要判断换成 `15m` K 是否能通过减少噪音改善机制。

结论：本 family 当前仍为 diagnostic only。15m 会降低交易频率，但没有从根上修复 V3.3 的 delayed trailing / crossed stop 问题；不能提升为 paper-live、dry-run 或 live candidate。

依据：`diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`。
