# Binance-1D-BTCETH-Crisis-Partial-Profit-Runner Core Ledger

## 身份与状态

- family：`Binance-1D-BTCETH-Crisis-Partial-Profit-Runner`
- short id：`BIN-1D-BE-CPPR`
- primary status：`explore`
- overlays：`not promoted / not live-ready`
- research line：`closed / HARD-GATE-FAILED`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1d-be-cppr-p0-contract-2026-08-12.md)
- development `[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` sealed
- prospective首个eligible closed day `>=2026-08-13`
- `0.001/fill + 4/8bps slippage + actual funding`；固定初始约`1x`，只减仓不加仓

## 版本表

| 版本 | 状态 | 证据 | 结论 |
| --- | --- | --- | --- |
| - | `explore / not promoted / not live-ready` | [P0裁决](diagnostics/binance-1d-be-cppr-p0-2026-08-12.md) | growth `16.4626x/-31.87%`，risk `6.6693x/-29.25%`，0 hard-pass |

## 关闭边界

- 禁止新增fraction、signal参数、第二次partial、resize或杠杆。
- audit/prospective从未读取；无版本。
- 后继只能另立full profit-exit + causal handoff continuity family。
