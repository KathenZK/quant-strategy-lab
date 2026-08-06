# HYPE-15M-Pullback-Trail

- Full family name：`HYPE-15M-Pullback-Trail`（无历史别名）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `15m`（由本地 `5m` 标准数据重采样为闭合 `15m`）
- 机制：15m 回踩/恢复事件源研究——最初检验 `HYPE-5M-Pullback-Trail` V3.3 delayed trailing 迁移到 `15m` 是否改善；随后转向入场即存在的 fixed bracket / emergency stop / timeout 可执行出场结构。
- 当前状态：V3.3 直接迁移 `not promoted / not live-ready`（未修复 trailing 解锁后 stop 可执行性）；bracket 搜索有一个未登记观察行 `ema21_96_pb0.015_long_nocandle__ret32>=600__tp2_sl4_tx24`，OOS 样本仍太短，整体为 `explore / not promoted / not live-ready`。

## 边界

- 不是 `HYPE-5M-Pullback-Trail` 的 promoted 版本；不要单独引用裸 `V3.3`——在本目录写作 `HYPE-5M-Pullback-Trail-V3.3` 的 15m transplant。
- bracket 候选不是"V3.3 修复版"：它只复用了相似的回踩事件源，出场结构已完全不同。

## 入口

- 主账：[hype-15m-pbtr-core-ledger.md](hype-15m-pbtr-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- bracket 可执行搜索（含候选机制定义与切片弱点）：[hype-15m-pullback-trail-bracket-search-2026-06-30.md](diagnostics/hype-15m-pullback-trail-bracket-search-2026-06-30.md)
- V3.3 迁移诊断（not-promoted 证据）：[hype-15m-pullback-trail-v3-3-migration-2026-06-30.md](diagnostics/hype-15m-pullback-trail-v3-3-migration-2026-06-30.md)

脚本在 `scripts/`，被报告引用的 JSON/CSV 在 `artifacts/`。候选参数、执行口径与指标以上述报告和 decision-log 为准。
