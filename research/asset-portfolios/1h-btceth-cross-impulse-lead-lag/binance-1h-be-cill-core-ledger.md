# Binance-1H-BTCETH-Cross-Impulse-Lead-Lag Core Ledger

## 身份与状态

- family：`Binance-1H-BTCETH-Cross-Impulse-Lead-Lag`
- short id：`BIN-1H-BE-CILL`
- primary status：`explore`
- overlays：`research line closed / HARD-GATE-FAILED / not promoted / not live-ready`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1h-be-cill-p0-contract-2026-08-12.md)
- development：`[2019-12-24 00:00 UTC, 2025-08-07 00:00 UTC)`
- researcher-exposed audit：`[2025-08-07 00:00 UTC, 2026-08-10 00:00 UTC)`；development 全门禁前禁止读取
- prospective：首个 eligible closed hour `>=2026-08-13 00:00 UTC`，首次执行 `>=2026-08-13 01:00 UTC`
- 费用：`0.001/fill`；base/stress slippage `4/8bps`
- 仓位：单 follower、初始 `1x`、固定数量；无 vol target/leverage rescue

## 版本表

| 版本 | 状态 | 证据 | 结论 |
|---|---|---|---|
| - | - | [P0 诊断](diagnostics/binance-1h-be-cill-p0-development-search-2026-08-12.md) | `2,160/2,160` 完成；最高 `1.2920x/-21.78%`，无登记版本 |

## 当前决策

P0 base hard-target 为 0；完全免除 fee/slippage/funding 后最高仍仅 `1.4943x`，证明失败不是 cost-only。当前为 `research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`；audit/prospective 从未揭示。
