# Binance-1D-MA7-Taker-Flow-Meta-Label Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Taker-Flow-Meta-Label`
- Alias：`BIN-1D-MA7-TFML`
- Market / timeframe：Binance USD-M perpetual；UTC `1d` maturity events + native `5m` taker flow
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：冻结 LMML event/outcome，Ridge 直接预测 `z_8bps`；full 必须证明原生 taker-flow 相对相同 price expected-utility control 的增量。
- Collision warning：不是 BPML 的二分类调参、DSML 官方 metrics taker ratio 修复或 HYPE V7；不继承任何失败路线的 promotion 证据。

## Current State

- Current version：无；P0 native-flow source/capacity 有效；P0E flow listing有效，但price/funding feature内嵌generator SHA无对应保留源码，故P0E整体fail closed。五资产P1和八资产P1E另因market aggregate未在fold内排除held source history而失效。
- Status：`explore / diagnostic-only / not promoted / not live-ready`；P1/P1E evidence invalidated。
- Event substrate：LMML `1,448` events，identity `f224974f…a777`。
- Source-only listing：五资产到 `2025-05` 共 `316` 个 canonical monthly 5m ZIP，约 `110.64 MiB`。
- HYPE boundary：P0/P1 完全禁止；即使 P1 通过也先做 post-cutoff 五资产 P2。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Next gate：不进入 P2/HYPE；不得在已揭示五资产或八资产 outcome 上修复后重称 OOS。任何重检必须另立全新 holdout，并在每个 outer/inner fold 内重建 price/flow aggregates。

## Version Rules

- 数据容量、模型开发或 P2 observation 不构成正式版本。
- 登记版本必须冻结 source/event identity、features、continuous target、Ridge/policy、成本、排程与证据。
- 改回 binary target、加入 aggTrades large-trade/order-book/liquidation 或改变 event horizon 属于 materially new contract。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0/P1 contract | `explore / diagnostic-only` | Native 5m taker-flow expected utility | [合同](specs/binance-1d-ma7-tfml-p0-p1-contract-2026-08-10.md) | 已冻结并执行 |
| P0/P1 development | `invalidated evidence / diagnostic-only` | Full vs price expected-utility control vs flow-only | [复核更正](diagnostics/binance-1d-ma7-tfml-p1-development-2026-08-10.md) | P0 通过；五资产 nested peer 合同不可执行，P1 不得解释 |
| P0E/P1E fresh universe | `invalidated evidence / diagnostic-only` | Legacy 5 资产训练 + 8 个未见资产 outer | [合同](specs/binance-1d-ma7-tfml-p0e-p1e-universe-expansion-contract-2026-08-10.md) · [复核更正](diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md) | P0E provenance blocker；P1E另有global aggregate污染，整体撤回 |

## Shared Assumptions

- Data：Binance Vision monthly 5m futures klines；冻结 LMML event/price/funding panel。
- Timing：只用 `close_time < entry_ts` 的 4,320 根完整 5m bars。
- Cost：target 继承 fee `0.001/fill`、`8bps/fill` adverse slippage、`0.25x` 与实际 funding。
- HYPE：development 与 P2 通过前不读取。

## Evidence Map

- [P0/P1 Taker-Flow Expected-Utility 合同](specs/binance-1d-ma7-tfml-p0-p1-contract-2026-08-10.md)
- [P0/P1 复核更正](diagnostics/binance-1d-ma7-tfml-p1-development-2026-08-10.md)
- [P1 summary](artifacts/p1_development_2026-08-10/p1_summary.json)
- [P1 full report](artifacts/p1_development_2026-08-10/p1_report.json)
- [P0E/P1E Fresh-Universe 合同](specs/binance-1d-ma7-tfml-p0e-p1e-universe-expansion-contract-2026-08-10.md)
- [P1E Fresh-Universe 复核更正](diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)
- [P1E summary](artifacts/p1e_development_2026-08-10/p1e_summary.json)
- [P1E full report](artifacts/p1e_development_2026-08-10/p1e_report.json)
- [BPML 失败诊断](../1d-ma7-basis-premium-meta-label/diagnostics/binance-1d-ma7-bpml-p1-development-2026-08-10.md)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
