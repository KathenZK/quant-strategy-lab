# Binance-1D-MA7-Quantile-Utility-Meta-Label Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Quantile-Utility-Meta-Label`
- Alias：`BIN-1D-MA7-QUML`
- Market / timeframe：Binance USD-M perpetual；UTC `1d` maturity event + causal `1h` context
- Legacy training：BTC/ETH/BNB/SOL/TRX/XRP/DOGE/ADA/LINK/LTC/DOT/AVAX/UNI
- Fresh outer：BCH/ETC/XLM/ATOM/VET/NEAR/AAVE/FIL
- Mechanism：price-only Ridge 预测 continuous `z_8bps`；threshold 只取当前 train predictions 的 frozen quantile。
- Collision warning：不是 TFML flow variant、BPML binary selector 或 HYPE V7；不继承任何失败路线的 promotion 证据。

## Current State

- Current version：无；P0 通过，历史 P1 因 held source history 进入预计算 market aggregates 而失效。
- Status：`explore / diagnostic-only / not promoted / not live-ready`；P1 evidence invalidated。
- Cutoff：`2025-05-31T00:00:00Z` exclusive。
- HYPE boundary：requests/files/rows/features/train/evaluation 全为零。
- Runner：无 live spec、implementation、dry-run/live instance。
- Terminal decision：不运行 P2、不补第三组历史资产 holdout、不读取 HYPE；撤回“有效证伪 pooled historical maturity-selection”的归因。
- Next gate：仅允许另立未见时间窗或全新机制合同，并在每个 fold 内重建 aggregates；不在已揭示 second-fresh 上修补。

## Version Rules

- 本 family 只有 quantile calibration 通过 P1/P2 后才可登记版本。
- 改 event、target、feature set、quantile grid、held universe 或执行规则均需新合同；不能在揭示 second-fresh outcome 后回填。

## Version Table

| Phase | Status | Role | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0/P1 | `invalidated evidence / diagnostic-only` | Train-distribution quantile vs absolute control | [合同](specs/binance-1d-ma7-quml-p0-p1-contract-2026-08-10.md) · [复核更正](diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md) | P0 有效；P1 aggregate isolation 违反合同，不得解释 |

## Shared Assumptions

- Fee `0.001/fill`；main slippage `8bps/fill`；`0.25x`；实际 funding。
- Closed daily signal，下一 UTC daily open 成交；MA7 recross / max 5d exit。
- HYPE 不参与开发、选择或 threshold calibration。

## Evidence Map

- [P0/P1 合同](specs/binance-1d-ma7-quml-p0-p1-contract-2026-08-10.md)
- [P1 复核更正](diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)
- [P0 source quality](artifacts/p0_price_data_2026-08-10/p0_data_quality_manifest.json)
- [P0 event capacity](artifacts/p0_events_2026-08-10/p0_capacity.json)
- [P1 summary](artifacts/p1_development_2026-08-10/p1_summary.json)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
- [TFML fresh failure](../1d-ma7-taker-flow-meta-label/diagnostics/binance-1d-ma7-tfml-p1e-fresh-universe-2026-08-10.md)
