# Decision Log

## 2026-08-04：建立双状态 Trend Campaign successor

旧 `BIN-MTF-PTC` 已因低收益、尾部集中和 HYPE/ETH 失败关账，`HYPE-15M-MTPP` 也证明频繁动态 stop 会切碎趋势；因此建立独立家族，把 position stop 与 daily Campaign invalidation 分层，并按[Goal 合同](specs/binance-mtf-dstc-goal-contract-2026-08-04.md)重新搜索，不继承旧绩效或状态。

## 2026-08-04：HARD-GATE-FAILED，final audit 不揭示

E01–E05 共完成 432 个账户级回测。双状态、MA14、较宽 Campaign invalidation 与分层 add 在 BTC/ETH 提取到微弱优势，但最干净 `BTC-BAL` 仅 `1.028x annual / -12.2% MDD / PF1.65`；1.5% 风险仍仅 `1.041x`，2% 风险已突破 20% MDD。HYPE 无 E02 资格配置，add/MFE attribution 全失败。决定按[最终报告](final/binance-mtf-dstc-goal-final-2026-08-04.md)关账；不揭示 historical final，不登记版本，不创建 runner handoff。
