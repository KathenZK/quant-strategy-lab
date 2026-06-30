# HYPE-15M-Pullback-Trail Decision Log

## 2026-06-30: 15m 回踩事件源 + 入场即 bracket 搜索

问题：保留 15m 回踩/恢复信号作为事件源，但放弃旧 V3.3 delayed trailing，改成实盘从入场时刻就能存在的 fixed TP/SL bracket、emergency stop 和 timeout，判断是否能找到收益、胜率、回撤更均衡的策略。

结论：找到一个 `paper-audit candidate only`，不能直接提升为 paper-live、dry-run 或 live candidate。该结构解决了 delayed trailing 解锁后 stop 不可实盘的问题，但 OOS 样本只有 `9` 笔，且 `2025-09-01 -> 2025-12-01` 切片表现弱，后续必须先做 walk-forward 固化和 paper audit runner。

候选：`ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl4_tx24`。全样本 `70` 笔，收益 `39.56%`，年化 `1.36x`，胜率 `62.86%`，PF `1.677`，payoff `0.991`，最大回撤 `-12.49%`。OOS `2026-06-01 -> latest` 为 `9` 笔，收益 `11.39%`，胜率 `77.78%`，PF `5.167`。

成本压力：在 Binance default `10 bps fee + 4 bps slip` 下仍为 `28.51%` 收益、`60.56%` 胜率、PF `1.483`、最大回撤 `-15.10%`；在 `10 bps fee + 8 bps slip` 压力下仍为 `20.46%` 收益、`61.43%` 胜率、PF `1.356`、最大回撤 `-16.45%`。

依据：`diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md`。

## 2026-06-30: V3.3 机制 15m 迁移诊断

问题：`HYPE-5M-Pullback-Trail-V3.3` 在 `5m` 上的原始回测很强，但严格 live-realistic trailing 口径失败。需要判断换成 `15m` K 是否能通过减少噪音改善机制。

结论：本 family 当前仍为 diagnostic only。15m 会降低交易频率，但没有从根上修复 V3.3 的 delayed trailing / crossed stop 问题；不能提升为 paper-live、dry-run 或 live candidate。

依据：`diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md`。
