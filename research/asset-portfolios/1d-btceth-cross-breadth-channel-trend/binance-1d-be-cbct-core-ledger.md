# Binance-1D-BTCETH-Cross-Breadth-Channel-Trend Core Ledger

## 身份与状态

- family：`Binance-1D-BTCETH-Cross-Breadth-Channel-Trend`
- short id：`BIN-1D-BE-CBCT`
- primary status：`explore`
- overlays：`not promoted / not live-ready`
- research line：`closed / HARD-GATE-FAILED`
- registered versions：无
- runner handoff：无

## 冻结边界

- P0：[冻结合同](specs/binance-1d-be-cbct-p0-contract-2026-08-12.md)
- development：`[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` 封存
- prospective：首个 eligible closed day `>=2026-08-13`，首次执行 `>=2026-08-14 00:00 UTC`
- 成本：`0.001/fill + 4/8bps slippage + actual funding`
- 初始 `1x`、固定数量；单一 BTC/ETH long/short 仓位

## 版本表

| 版本 | 状态 | 证据 | 结论 |
|---|---|---|---|
| - | `explore / not promoted / not live-ready` | [P0 裁决](diagnostics/binance-1d-be-cbct-p0-search-2026-08-12.md) | `2,808/2,808` 完成；growth `13.2404x/-48.00%`，risk `1.6607x/-27.88%`；`0` hard-target pass，无版本 |
| - | `explore / not promoted / not live-ready` | [P1 裁决](diagnostics/binance-1d-be-cbct-p1-profit-protection-2026-08-12.md) | `18/18` 完成；growth `21.2707x/-37.20%`，risk `4.4107x/-34.20%`；`0` soft-continue，research line closed |

## 当前门禁

- P0/P1 均已停止；audit/prospective 未读取。
- 禁止继续搜索 Donchian/EMA/chandelier/cooldown/giveback，禁止加入 handoff/re-entry/RSI 组合救援，也不允许杠杆或风险缩放。
- 下一步只能另立具有慢周期 regime/campaign state 的 materially new family；P1 增量仅作 development evidence。
