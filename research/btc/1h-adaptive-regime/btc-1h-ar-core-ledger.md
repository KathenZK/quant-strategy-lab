# BTC-1H-Adaptive-Regime 主账

## 家族身份

- Full family name：`BTC-1H-Adaptive-Regime`
- Short id：`BTC-1H-AR`
- 市场：Binance USD-M Futures `BTCUSDT` perpetual
- 周期：`1h`

## 当前状态

`NO-GO / not promoted / not live-ready`。

## 版本表

| Version | Identity | Status | Prefit annual / DD / win | Reused holdout annual / DD / win | Evidence | Live-readiness |
| --- | --- | --- | --- | --- | --- | --- |
| `BTC-1H-Adaptive-Regime-V1` | Keltner breakout + CCI reversal prefit-frozen ensemble | diagnostic baseline / NO-GO | `2.82x` / `-18.68%` / `68.29%` | `0.17x` / `-42.73%` / `38.46%` | `canonical-specs/btc-1h-ar-v1-baseline-spec.md`；`artifacts/btc_1h_ar_v1_config_2026-07-02.json` | not live-ready；不生成 live spec |

V1 是用户明确要求登记的研究基线。版本登记不代表 promotion，也不覆盖原始硬门槛和 reused holdout 失败。

## 研究边界记录

| Boundary | Status | Prefit annual / DD / win | Locked OOS annual / DD / win | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `BTC-1H-AR-2026-07-02-prefit-frozen` | 已登记为 V1 | `2.82x` / `-18.68%` / `68.29%` | `0.17x` / `-42.73%` / `38.46%` | `diagnostics/btc-1h-adaptive-regime-search-2026-07-02.md`；`diagnostics/btc-1h-adaptive-regime-boundary-audit-2026-07-02.md` | `NO-GO`；不可实盘 |

搜索规模：`300,768` 组配置，`41,898` 组可评分，prefit hard-gate `0`；73 个 one-at-a-time 邻域变体 joint-gate `0`；bootstrap `10,000` 次 hard-shape 命中率 `0%`。

## Promotion 门槛

必须同时通过：最近三个月 locked OOS、年化权益倍率 `>=10.0x`、胜率 `>=50%`、最大回撤 `<20%`、K+2/成本压力、参数邻域、时间切片、bootstrap、订单时序、保护单、重启恢复、missing-bar fail-closed、交易所对账和 kill switch 审计。
