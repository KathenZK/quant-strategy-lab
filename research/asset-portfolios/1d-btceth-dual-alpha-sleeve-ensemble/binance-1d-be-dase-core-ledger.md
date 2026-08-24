# Binance-1D-BTCETH-Dual-Alpha-Sleeve-Ensemble Core Ledger

## 身份与状态

- family：`Binance-1D-BTCETH-Dual-Alpha-Sleeve-Ensemble`
- short id：`BIN-1D-BE-DASE`
- primary status：`explore`
- overlays：`not promoted / not live-ready`
- research line：`closed / HARD-GATE-FAILED`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1d-be-dase-p0-contract-2026-08-12.md)
- development：`[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` sealed
- prospective：首个 eligible closed day `>=2026-08-13`，首次执行 `>=2026-08-14 00:00 UTC`
- 每个 sleeve 内部已计 `0.001/fill + 4/8bps slippage + actual funding`
- 固定初始资本权重、无再平衡、无资本借用、无 leverage/vol target

## 版本表

| 版本 | 状态 | 证据 | 结论 |
| --- | --- | --- | --- |
| - | `explore / not promoted / not live-ready` | [P0 裁决](diagnostics/binance-1d-be-dase-p0-2026-08-12.md) | `75/25` 为 `21.2681x/-34.34%`，0 hard-pass，research line closed |

## 关闭边界

- 禁止新增权重、动态 vol/drawdown parity、跨 sleeve再平衡或低收益 sleeve + leverage。
- agreement/disagreement 的跨年份效果不稳定，不授权动态 consensus router。
- audit/prospective 从未读取；后继必须另立机制身份与合同。
