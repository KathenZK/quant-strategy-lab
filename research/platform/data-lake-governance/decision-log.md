# Decision Log — Binance-OHLCV-Data-Lake-Governance

## 2026-09-02 — 启动 Binance OHLCV 身份治理

决策：把 Binance 数据流固定为 `raw → accepted normalized 15m → versioned derived 1h/4h/1d → family cache → research artifacts`；当前 normalized 1h 登记为 `PARTIAL_SCOPE_LEGACY`，公共日K与 MA7 RC 面板登记为 `FAMILY_CACHE`。本轮只做非破坏性治理，不覆盖旧 parquet，不重跑策略。

证据：[身份契约](specs/binance-ohlcv-dataset-identity-contract-2026-09-02.md)、[data-lake-spec](../../../docs/data-lake-spec.md)。

## 2026-09-02 — 治理基础就绪

决策：现场审计、scope gate、cache sidecar、15m→1h/4h/1d 发布与对账均完成，状态 `GOVERNANCE_FOUNDATION_READY`。legacy 1h 不能再经新入口冒充 `FULL_MARKET`。旧 parquet 未改写。不把该状态解释为策略通过。

证据：[现场审计](diagnostics/binance-ohlcv-dataset-inventory-2026-09-02.md)、[对账](diagnostics/binance-ohlcv-reconciliation-2026-09-02.md)、[P0R-DATA 交接](specs/binance-4h-ma7-rc-p0r-data-handoff-2026-09-02.md)。

## 2026-09-03 — 第二轮可信读取门禁收口

决策：基础设施记 `READY`，15m 与 `from_15m.v1` 全量 SQL `PASS`，消费者仍 `PARTIAL`。不以笼统 READY 覆盖 legacy 1h、家族缓存和未迁移历史脚本。不把本轮解释为策略通过，也不外推 4H 全市场结论。

证据：[第二轮契约](specs/binance-ohlcv-round2-trusted-load-contract-2026-09-03.md)、[验收](diagnostics/binance-ohlcv-round2-acceptance-2026-09-03.md)、[SQL 审计](diagnostics/binance-ohlcv-trusted-quality-audit-2026-09-03.md)、[成交额追溯](diagnostics/binance-ohlcv-volume-rca-2026-09-03.md)。
