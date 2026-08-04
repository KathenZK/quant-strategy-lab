# Decision Log

## 2026-08-04：建立双状态 Trend Campaign successor

旧 `BIN-MTF-PTC` 已因低收益、尾部集中和 HYPE/ETH 失败关账，`HYPE-15M-MTPP` 也证明频繁动态 stop 会切碎趋势；因此建立独立家族，把 position stop 与 daily Campaign invalidation 分层，并按[Goal 合同](specs/binance-mtf-dstc-goal-contract-2026-08-04.md)重新搜索，不继承旧绩效或状态。
