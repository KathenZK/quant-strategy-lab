# Binance-1D-MA7-Basis-Premium-Meta-Label Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Basis-Premium-Meta-Label`
- Alias：`BIN-1D-MA7-BPML`
- Market / timeframe：Binance USD-M perpetual；UTC `1d` maturity event + `1h` basis/premium
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：冻结 LMML maturity 经济事件，增加 premium-index 与 mark/index basis；full 必须在相同事件和 folds 上严格超越 price control。
- Collision warning：不是 DSML 的 source fallback、DSTO 的 daily-anchor 变体或 HYPE V7；不继承失败路线的 promotion 证据。

## Current State

- Current version：无；14 日 P0R 接受 `1,335/1,448` 并通过容量门，但 P1 full `19/20` folds 为 `NO_SELECTION`，唯一 OOF trade `-1.5633%`。
- Status：`HARD-GATE-FAILED / explore / diagnostic-only / not promoted / not live-ready`。
- Event substrate：LMML `1,448` events，identity `f224974f…a777`。
- HYPE boundary：P0/P1 禁止 HYPE；通过全部非 HYPE development gate 后才可另立 exposed-target transfer 合同。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Next gate：本 family 的 maturity + basis/premium binary meta-label 路线关闭；真实 taker flow/liquidation 或组合级 target 必须另立合同。

## Version Rules

- P0 数据、P1 模型或单资产 observation 均不构成正式版本。
- 登记版本必须冻结 source/event identity、feature、label、模型、threshold、成本、排程与证据。
- 改变 maturity target、horizon、加入 OI/liquidation/order book 或按资产/方向设参数均是 materially new contract。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0/P1 contract | `explore / diagnostic-only` | Basis/premium 对冻结 LMML price control 的严格增量 | [合同](specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md) | 待执行 |
| Original P0 30d | `explore / diagnostic-only` | 连续 `744h` 逐 event 准入 | [容量证据](artifacts/p0_data_2026-08-10/p0_original_30d_capacity.json) | 容量失败：`1,233/1,448`，未运行模型 |
| P0R 14d | `explore / diagnostic-only` | 保持原容量门，reference 改为连续 14 日 | [修订合同](specs/binance-1d-ma7-bpml-p0r-14d-basis-contract-2026-08-10.md) | 容量通过：`1,335/1,448`，允许 P1 |
| P0R/P1 basis development | `HARD-GATE-FAILED` | Full vs price control vs basis-only nested LOAO | [失败诊断](diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md) | P0R 通过；无稳定 choice，不保存模型、不读 HYPE |

## Shared Assumptions

- Data：Binance Vision monthly `1h` premiumIndex/markPrice/indexPrice Klines；LMML direct price/funding event panel。
- Timing：basis 只用 `open_time/close_time < entry_ts`；下一 UTC 日 open 已由冻结 event 定义。
- Cost：继承 LMML fee `0.001/fill`、主 label `8bps/fill`、固定 `0.25x` 与实际 funding。
- HYPE：development 截止 `2025-05-31 UTC`，不读取 HYPE 数据或结果。

## Evidence Map

- [P0/P1 数据与模型合同](specs/binance-1d-ma7-bpml-p0-p1-contract-2026-08-10.md)
- [P0R 14 日 Basis 修订合同](specs/binance-1d-ma7-bpml-p0r-14d-basis-contract-2026-08-10.md)
- [原 30 日 P0 容量证据](artifacts/p0_data_2026-08-10/p0_original_30d_capacity.json)
- [P0/P1 失败诊断](diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md)
- [P1 summary](artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 full report](artifacts/p1_development_2026-08-10/p1_report.json)
- [LMML P1 失败诊断](../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
- [DSML P0 容量失败诊断](../1d-ma7-derivatives-structure-meta-label/diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)
- [DSTO P1 OI + Funding 失败诊断](../1d-derivatives-structure-trend-opportunity/diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
