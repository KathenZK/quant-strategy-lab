# Binance-1D-MA7-Asset-Local-Temporal-Audit Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Asset-Local-Temporal-Audit`
- Alias：`BIN-1D-MA7-ALTA`
- Market / timeframe：Binance USD-M perpetual；UTC `1d` maturity event + causal `1h` context
- Universe：21 个既有非 HYPE 资产；不新增、不删减。
- Mechanism：冻结后时间窗 `take_all` vs 无网格、单资产 `Ridge(1000)+train q80`。
- Collision warning：不是 QUML P2、pooled meta-label、第三组历史 holdout 或 HYPE V7。

## Current State

- Current version：无；P0 通过、P1 `DEVELOPMENT_HARD_GATE_FAILED`。
- Status：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。
- Train boundary：严格 `<2025-05-31T00:00:00Z`。
- Test window：`[2025-05-31T00:00:00Z, 2026-08-01T00:00:00Z)`。
- HYPE boundary：requests/files/rows/features/train/evaluation 全为零。
- Runner：无 live spec、implementation、dry-run/live instance。
- Terminal decision：按冻结合同关闭已揭示数据上的同一 maturity event selector/threshold/model 搜索；结论仅为无条件 substrate 负 edge，不等于所有独立信息均被证伪；不读取 HYPE。
- Next gate：保留 V6 clean prospective observer，或另立非 MA7 root/组合级机制；若用独立 OI/flow 重检，必须新 holdout 与 fold-local aggregates。

## Version Rules

- 本 family 只有未见时间窗 P1 与后续独立复制都通过后才可登记版本。
- 改 event、时间窗、资产、feature、policy、alpha、quantile、route 或成本均需新合同。
- P1 outcome 揭示后不得在同一窗口增加第三 policy、删资产或调参数。

## Version Table

| Phase | Status | Role | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0/P1 | `HARD-GATE-FAILED / explore` | 未见时间窗上的 event substrate 与 asset-local fixed policy 终局审计 | [合同](specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md) · [诊断](diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md) | `take_all` mean `-0.1207%`、PF `0.829`、bootstrap `0.16%`；关闭路线 |

## Shared Assumptions

- Fee `0.001/fill`；主 slippage `8bps/fill`；`0.25x`；实际 funding。
- Closed daily maturity signal，下一 UTC daily open 成交；MA7 recross / max 5d exit。
- `take_all` 是第一主门；模型不能掩盖 substrate 自身失败。
- HYPE 不参与开发、选择、threshold calibration 或评估。

## Evidence Map

- [P0/P1 合同](specs/binance-1d-ma7-alta-p0-p1-contract-2026-08-10.md)
- [P1 失败诊断](diagnostics/binance-1d-ma7-alta-p1-temporal-audit-2026-08-10.md)
- [P0 data quality](artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json)
- [P0 event capacity](artifacts/p0_events_2026-08-10/p0_capacity.json)
- [P1 summary](artifacts/p1_temporal_audit_2026-08-10/p1_summary.json)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
- [QUML P1 复核更正](../1d-ma7-quantile-utility-meta-label/diagnostics/binance-1d-ma7-quml-p1-development-2026-08-10.md)
