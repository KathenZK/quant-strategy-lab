# Binance-1D-BTCETH-Relative-Cycle-Rotation Core Ledger

## 家族身份

- family：`Binance-1D-BTCETH-Relative-Cycle-Rotation`
- short id：`BIN-1D-BE-RCR`
- primary status：`explore`
- overlays：`research line closed / HARD-GATE-FAILED / not promoted / not live-ready`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0 合同：[binance-1d-be-rcr-p0-contract-2026-08-12.md](specs/binance-1d-be-rcr-p0-contract-2026-08-12.md)
- development：`[2019-12-24 00:00 UTC, 2025-08-07 00:00 UTC)`
- researcher-exposed audit：`[2025-08-07 00:00 UTC, 2026-08-10 00:00 UTC)`；只有 development 唯一候选通过后才可揭示
- prospective：信号日 `>=2026-08-13`、首次可执行开盘 `>=2026-08-14 00:00 UTC`；保持结果盲
- 费用：每次 fill `0.001`；base slippage `4 bps/fill`；stress `8 bps/fill`
- 仓位：任一时点仅一个 `BTC/ETH × long/short` 状态，入场约 `1x`、持有期固定数量，总毛杠杆不超过 `1x`

## 版本表

| 版本 | 状态 | 证据 | 结论 |
|---|---|---|---|
| - | - | - | 尚无满足登记条件的版本 |

## 当前决策

P0–P6 已全部完成。P0 growth 为 `21.2605x/-69.6600% ordered MDD`，risk 为 `8.6109x/-30.7607%`；P1/P3 无 hard-target，P4/P5 price transitions 均 `0/6 PASS`。P6 `POSITION_CROWD24` AUC 有排序信息，但最弱分层 edge `4.56pp < 8pp`，最终仍 `0/6 PASS`。当前为 `research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`；audit/prospective 从未揭示，不登记版本。证据见 [P0](diagnostics/binance-1d-be-rcr-p0-development-search-2026-08-12.md)、[P1](diagnostics/binance-1d-be-rcr-p1-protective-exit-2026-08-12.md)、[P2/P3](diagnostics/binance-1d-be-rcr-p2-p3-entry-context-2026-08-12.md)、[P4](diagnostics/binance-1d-be-rcr-p4-holding-transition-2026-08-12.md)、[P5](diagnostics/binance-1d-be-rcr-p5-hourly-hazard-2026-08-12.md)与 [P6](diagnostics/binance-1d-be-rcr-p6-funding-crowding-2026-08-12.md)。
