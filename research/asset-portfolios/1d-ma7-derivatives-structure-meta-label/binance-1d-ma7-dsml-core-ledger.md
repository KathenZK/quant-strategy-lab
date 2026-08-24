# Binance-1D-MA7-Derivatives-Structure-Meta-Label Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Derivatives-Structure-Meta-Label`
- Alias：`BIN-1D-MA7-DSML`
- Market / timeframe：Binance USD-M perpetual；UTC `1d` events + Binance Vision `5m` derivatives metrics
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：在冻结 LMML event/label 上，仅用因果 OI、top-trader/global long-short ratio、taker ratio 与 leave-target-out 市场结构特征作 pooled meta-label。
- Collision warning：不继承 LMML/RHT/VIPR/DAPML 的模型或 promotion 结论；冻结 LMML 事件只作为不可改写的 outcome substrate。

## Current State

- Current version：无；P0 官方 archive 容量审计已完成并 `HARD-GATE-FAILED`，P1 未运行。
- Status：`explore / not promoted / not live-ready`。
- Development boundary：五资产 derivatives metrics 与 event timestamp 均严格早于 `2025-05-31 UTC`。
- HYPE boundary：实际 HYPE rows/files/requests 均为零；本合同无 transfer。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Blocker：四个 altcoin metrics 仅始于 `2021-12-01`；30 日上下文后最多 `967/1,448` 个 events，P0 四项容量门全部不可达。
- Next gate：本家族不再推进；同一独立信息源须更换为高容量 anchor/label 设计。

## Version Rules

- P0 数据、P1 模型和任何特征 observation 均不构成正式版本。
- 登记版本必须冻结 source archive manifest、event identity、特征、模型、threshold、成本和 OOF 证据。
- 改写 LMML root/label、加入 basis/liquidation、使用 asset id、改变模型家族或解锁 HYPE 均是 materially new contract。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0 capacity | `explore / HARD-GATE-FAILED` | 独立 derivatives structure 对冻结经济事件作严格 OOF 筛选 | [合同](specs/binance-1d-ma7-dsml-p0-p1-contract-2026-08-10.md) · [容量诊断](diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md) | 官方 archive 历史不足；不下载、不建模 |

## Shared Assumptions

- Event substrate：固定使用 LMML `1,448` 个 event 及其 `4/8bps`、funding、lag outcome，不重算或删改标签。
- Metrics source：Binance Vision USD-M daily metrics archive；ZIP CRC、symbol、UTC `5m` 网格、唯一性和数值合法性 fail closed。
- Timing：每个特征只使用 `create_time < signal_ts` 的 metrics。
- Model：asset id 禁止；held asset 不进入 scaler、训练、threshold 或 market aggregate。

## Evidence Map

- [P0/P1 数据与模型合同](specs/binance-1d-ma7-dsml-p0-p1-contract-2026-08-10.md)
- [P0 官方 archive 容量失败诊断](diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)
- [LMML 冻结事件及失败诊断](../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
- [VIPR 失败诊断](../1h-volatility-impulse-pullback-reclaim/diagnostics/binance-1h-vipr-p1-development-2026-08-10.md)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
