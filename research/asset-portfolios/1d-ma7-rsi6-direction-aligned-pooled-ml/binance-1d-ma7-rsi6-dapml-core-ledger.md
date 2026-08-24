# Binance-1D-MA7-RSI6-Direction-Aligned-Pooled-ML Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-RSI6-Direction-Aligned-Pooled-ML`
- Alias：`BIN-1D-MA7-RSI6-DAPML`
- Market / timeframe：Binance USD-M perpetual，完整 UTC `1d`；官方 `1h` stop path
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：SMA7 严格穿越定方向，方向对齐 MA7/K 线/RSI6 形态，跨资产 pooled 模型筛选成本后正 EV 事件。
- Boundary：新跨资产家族；不继承 `BTC-1D-MA7-RSI6-LGBM`、旧 EMA-cross selector 或 MA7 transfer 家族的版本与 promotion 结论。

## Current State

- Current version：无；P0 通过，P1 pooled development 已完成并失败。
- Status：P1 `HARD-GATE-FAILED / explore / not promoted / not live-ready`。
- Development cutoff：所有资产统一截止到 `2025-08-06 UTC`，禁止用其他资产同期数据侧漏 BTC 冻结年。
- Sealed period：所有资产共同封存 `2025-08-07` 至 `2026-08-06 UTC`；BTC 尤其保持未揭示。
- Model state：方向对齐 Logistic-EV temporal、leave-one-asset 与 aligned/raw 消融全部失败；LightGBM 诊断也未通过。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Next gate：无；共同 sealed year 不揭示。只有 materially new label 或交易机制才能另立后继合同。

## Version Rules

- P0/P1 数据、特征和诊断不构成正式版本。
- 未来登记版本必须冻结 universe、方向对齐公式、asset/time split、模型、edge、执行成本和完整证据。
- 资产池、方向对齐语义、标签、退出或验证结构变化时不得静默覆盖。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0 data/feature | `explore / diagnostic-only` | 五资产统一截止、动态 funding、方向对齐形态与 validation 防侧漏 | [P0 合同](specs/binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md) · [审计](diagnostics/binance-1d-ma7-rsi6-dapml-p0-data-capacity-2026-08-10.md) | PASS；P1 已冻结 |
| P1 pooled development | `HARD-GATE-FAILED / explore` | Asset-balanced Logistic-EV aligned + temporal/LOAO；raw 与 LightGBM 对照 | [P1 合同](specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-contract-2026-08-10.md) · [诊断](diagnostics/binance-1d-ma7-rsi6-dapml-p1-pooled-development-2026-08-10.md) | 不揭示 validation；停止同机制微调 |

## Shared Assumptions

- Data source：Binance FAPI direct klines、funding history 与 official mark-price klines。
- Timing：日线 `t` 收盘确认，最早 `t+1` 日开盘成交；`1h` 只解析 fixed stop。
- Cost：每 fill 手续费 `0.001`、不利滑点 `4 bps`、实际 funding。
- Validation：跨资产训练数据不得超过 `2025-08-06 UTC`，不以其他币种未来段间接学习 BTC 封存期市场状态。

## Evidence Map

- [P0 数据与方向对齐特征合同](specs/binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md)
- [P0 数据与事件容量审计](diagnostics/binance-1d-ma7-rsi6-dapml-p0-data-capacity-2026-08-10.md)
- [P1 pooled development 合同](specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-contract-2026-08-10.md)
- [P1 pooled development 失败诊断](diagnostics/binance-1d-ma7-rsi6-dapml-p1-pooled-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [决策记录](decision-log.md)
