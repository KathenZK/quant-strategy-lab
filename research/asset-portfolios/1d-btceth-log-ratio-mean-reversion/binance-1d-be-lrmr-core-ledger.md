# Binance-1D-BTCETH-Log-Ratio-Mean-Reversion Core Ledger

## 身份与状态

- family：`Binance-1D-BTCETH-Log-Ratio-Mean-Reversion`
- short id：`BIN-1D-BE-LRMR`
- primary status：`explore`
- overlays：`research line closed / HARD-GATE-FAILED / not promoted / not live-ready`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1d-be-lrmr-p0-contract-2026-08-12.md)
- development：`[2019-12-24 00:00 UTC, 2025-08-07 00:00 UTC)`
- researcher-exposed audit：`[2025-08-07 00:00 UTC, 2026-08-10 00:00 UTC)`；development 全门禁前禁止读取
- prospective：信号日 `>=2026-08-13`、首次执行 `>=2026-08-14 00:00 UTC`；保持盲态
- 每腿每 fill：fee `0.001`；base/stress slippage `4/8bps`
- 初始两腿各 `0.5x`，总毛杠杆 `1x`；持仓期间数量固定，不做 risk scaling

## 版本表

| 版本 | 状态 | 证据 | 结论 |
|---|---|---|---|
| - | - | [P0 诊断](diagnostics/binance-1d-be-lrmr-p0-development-search-2026-08-12.md) | `15,288/15,288` 完成；最高 `1.5471x/-44.88% ordered MDD`，无登记版本 |

## 当前决策

P0 日线 hard-target 通过数为 0；growth/risk conservative ordered 前沿分别为 `1.5471x/-44.88%` 与 `1.0325x/-19.66%`。收益与目标相差数量级，不进行阈值救援。当前为 `research line closed / HARD-GATE-FAILED / explore / not promoted / not live-ready`；audit/prospective 从未揭示。
