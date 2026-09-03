# Binance-OHLCV-Data-Lake-Governance Core Ledger

## Family Identity

- Full family name / alias：`Binance-OHLCV-Data-Lake-Governance` / `BIN-OHLCV-DLG`。
- Market / timeframe：Binance USD-M USDT perpetual OHLCV；底座为 accepted normalized `15m`。
- Mechanism：用 `dataset_id` 固定数据身份与 scope；partial/unaccepted 数据 fail closed；由 15m 生成版本化 1h/4h/1d；cache 只能作为可重建家族产物。
- Boundary：这是平台数据治理线，不是交易策略；不得把治理完成解释为策略 PASS，也不得覆盖 legacy normalized 1h。

## Current State

- Current observation：第二轮可信读取 / 版本 / 缓存门禁。
- Status（分项，不以笼统 READY 代替缺口）：基础设施 `READY`；数据集 15m 与 `from_15m.v1` 全量 SQL `PASS`，legacy 1h 仍是 `PARTIAL_SCOPE_LEGACY`，家族缓存仍是 `FAMILY_CACHE`；消费者 `PARTIAL`。这不是策略 PASS。
- Runner / dry-run / live：none。
- Next gate：破坏性清理、面板重建、历史脚本迁移仍待用户批准。4H 全市场 `P0R-DATA` 结果另开会话；本轮只完成取数门禁。

## Version Rules

- 数据版本与策略版本分离。`from_15m.v1` 是衍生数据集版本，不是策略 `V1`。
- 已发布 derived 目录不可覆盖；公式、phase、来源裁决或输入窗口变化必须新 `vN`。
- cache sidecar 不是新数据版本；它只描述现有 parquet。
- Round 2 修读取门禁，不发布新的 OHLCV 数据版本。

## Version Table

| Observation | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `15m.normalized.v1` | `TRUSTED_BASE` | Binance 全市场可信底座 | 60,266,362 行 / 853 symbols；库存指纹 `c615a4c1…` | [inventory](diagnostics/binance-ohlcv-dataset-inventory-2026-09-02.md) · [SQL 审计](diagnostics/binance-ohlcv-trusted-quality-audit-2026-09-03.md) | 新研究必须用 dataset-id 入口 |
| `1h.normalized.legacy` | `PARTIAL_SCOPE_LEGACY` | 残缺 1h，多数代码只有 2026-07 快照 | 以现场审计为准 | [inventory](diagnostics/binance-ohlcv-dataset-inventory-2026-09-02.md) | `FULL_MARKET` fail closed |
| `1h/4h/1d.from_15m.v1` | `TRUSTED_DERIVED` | UTC `00:00` 完整桶聚合 | 1h 15,066,337；4h 3,766,251；1d 627,283 | derived `_MANIFEST.json` · [SQL 审计](diagnostics/binance-ohlcv-trusted-quality-audit-2026-09-03.md) | 不覆盖 legacy 1h |
| `1d.cache` / MA7 RC panels | `FAMILY_CACHE` | 可重建，非标准 OHLCV | sidecar `.cache-meta.json` | cache sidecar | 不得当其他家族事实源 |
| `G0–G4` | `GOVERNANCE_FOUNDATION_READY` | 身份、scope gate、sidecar、衍生发布与对账 | 旧 parquet 未改写 | [对账](diagnostics/binance-ohlcv-reconciliation-2026-09-02.md) | 基础就绪，不是策略通过 |
| Round 2 | 基础设施 `READY`；数据集 `PASS`+缺口；消费者 `PARTIAL` | 可信读取、manifest、幂等版本、无聊天取数 | 受保护文件 327,640 未变；测试 60 passed | [第二轮契约](specs/binance-ohlcv-round2-trusted-load-contract-2026-09-03.md) · [验收](diagnostics/binance-ohlcv-round2-acceptance-2026-09-03.md) | 门禁收口；历史消费者未全迁 |

## Shared Assumptions

- Data：只治理现有本地数据，不下载新行情。
- Source union：Vision monthly 优先于 Futures API；未列入来源排除。
- Aggregation：4/16/96 根连续闭合合法 15m；不补 K。
- Cost / execution：不适用。

## Evidence Map

- [Family README](README.md)
- [身份契约](specs/binance-ohlcv-dataset-identity-contract-2026-09-02.md)
- [第二轮契约](specs/binance-ohlcv-round2-trusted-load-contract-2026-09-03.md)
- [第二轮验收](diagnostics/binance-ohlcv-round2-acceptance-2026-09-03.md)
- [现场审计](diagnostics/binance-ohlcv-dataset-inventory-2026-09-02.md)
- [对账](diagnostics/binance-ohlcv-reconciliation-2026-09-02.md)
- [成交额追溯](diagnostics/binance-ohlcv-volume-rca-2026-09-03.md)
- [全量 SQL 质量](diagnostics/binance-ohlcv-trusted-quality-audit-2026-09-03.md)
- [消费者迁移 09-03](diagnostics/binance-ohlcv-consumer-migration-2026-09-03.md)
- [4H P0R 交接](specs/binance-4h-ma7-rc-p0r-data-handoff-2026-09-02.md)
- [产物索引](artifacts/README.md)
- [data-lake-spec §16](../../../docs/data-lake-spec.md)
- [catalog.py](../../../src/strategy_lab/data/catalog.py)
