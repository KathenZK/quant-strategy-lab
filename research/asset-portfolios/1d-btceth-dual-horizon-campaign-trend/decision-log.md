# BIN-1D-BE-DHCT Decision Log

## 2026-08-12 — P0 家族与合同冻结

- MA7 P2、RCR、LRMR、CILL 已分别关闭；CBCT P1 虽达 `21.2707x`，但 MDD仍 `-37.20%`。
- CBCT 剩余最大回撤来自多笔交易之间的慢周期方向错配，而非单笔 profit giveback。
- 冻结独立 dual-horizon campaign state：共同慢周期 state 决定方向/neutral，快周期突破只负责选币；共 `108` 个配置。
- CBCT P1 的 profit-protection 仅作为 development-derived 固定组件，不把其参数或收益称为 OOS；audit/prospective保持 sealed。

## 2026-08-12 — P0 HARD-GATE-FAILED；research line closed

- `108/108` 完成，base pass `0`；growth/risk path-equal，为 `15.3468x/-35.23%`、24 笔。
- 最大单笔正 log-growth 占 `42.47%`；profit protection 19 次、regime invalidation仅1次。
- 慢周期 state 删除机会但未形成 20x/20% 前沿；按合同不扩参数、不读取 audit/prospective，关闭 family。[P0 裁决](diagnostics/binance-1d-be-dhct-p0-search-2026-08-12.md)
