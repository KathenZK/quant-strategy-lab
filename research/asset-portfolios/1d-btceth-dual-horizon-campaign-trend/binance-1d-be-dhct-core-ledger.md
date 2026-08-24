# Binance-1D-BTCETH-Dual-Horizon-Campaign-Trend Core Ledger

## 身份与状态

- family：`Binance-1D-BTCETH-Dual-Horizon-Campaign-Trend`
- short id：`BIN-1D-BE-DHCT`
- primary status：`explore`
- overlays：`not promoted / not live-ready`
- research line：`closed / HARD-GATE-FAILED`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1d-be-dhct-p0-contract-2026-08-12.md)
- development：`[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` sealed
- prospective：首个 eligible closed day `>=2026-08-13`，首次执行 `>=2026-08-14 00:00 UTC`
- 成本：`0.001/fill + 4/8bps slippage + actual funding`
- 单一固定约 `1x` BTC/ETH long/short 仓位；不加仓、不做 risk scaling

## 版本表

| 版本 | 状态 | 证据 | 结论 |
| --- | --- | --- | --- |
| - | `explore / not promoted / not live-ready` | [P0 裁决](diagnostics/binance-1d-be-dhct-p0-search-2026-08-12.md) | `108/108` 完成；growth/risk 同为 `15.3468x/-35.23%`，0 base pass，research line closed |

## 关闭边界

- audit/prospective 从未读取；不得在本 family 继续扩 EMA/slope/breakout/cooldown 或修改固定 profit protection。
- 不允许以 leverage、vol target 或组合资金缩放改写基础失败。
- 后继必须另立 family，并离开强相关资产的单仓择一结构。
