# Binance-1D-BTCETH-Crisis-Override-Shadow-Trend Core Ledger

## 身份与状态

- family：`Binance-1D-BTCETH-Crisis-Override-Shadow-Trend`
- short id：`BIN-1D-BE-COST`
- primary status：`explore`
- overlays：`not promoted / not live-ready`
- research line：`closed / HARD-GATE-FAILED`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1d-be-cost-p0-contract-2026-08-12.md)
- development `[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` sealed
- prospective 首个 eligible closed day `>=2026-08-13`，首次执行 `>=2026-08-14 00:00 UTC`
- `0.001/fill + 4/8bps slippage + actual funding`
- 账户 gross target `<=1x`；互斥 shadow single position / dual-short basket

## 版本表

| 版本 | 状态 | 证据 | 结论 |
| --- | --- | --- | --- |
| - | `explore / not promoted / not live-ready` | [P0裁决](diagnostics/binance-1d-be-cost-p0-2026-08-12.md) | 最佳 `23.1321x/-35.22%`，0 hard-pass，research line closed |

## 关闭边界

- 禁止扩 EMA/slope/confirm、return/vol阈值、pair stop/TP或杠杆。
- audit/prospective从未读取；COST不形成版本。
- 下一机制只能另立partial-profit runner identity，处理盈利仓持仓内回吐。
