# Binance-1H-MA7-Root-Hazard-Timing Core Ledger

## Family Identity

- Full family name：`Binance-1H-MA7-Root-Hazard-Timing`
- Alias：`BIN-1H-MA7-RHT`
- Market / timeframe：Binance USD-M perpetual；UTC `1d` root、闭合 `1h` decision
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：daily soft SMA7 cross 只建立方向 root；此后最多 120 个小时 landmark 预测成本后 probe 质量，首次过阈值后下一小时边界成交。
- Collision warning：不继承 `BIN-1D-MA7-LMML`、DAPML、CTLS、PKTSC 或 HYPE ABT 的版本与 promotion 证据。

## Current State

- Current version：无；P0 容量通过，P1 hazard timing 已完成并 `HARD-GATE-FAILED`。
- Status：`explore / not promoted / not live-ready`。
- Development boundary：只读取 `2025-05-31 UTC` 前五资产数据；root 进一步截止到 `2025-05-20 UTC` 以容纳标签与延迟压力。
- HYPE boundary：development 实际读取 HYPE rows/files 均为零；失败后不设 transfer。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Blocker：OOF first-hit `30` roots，mean `−0.0437%`、PF `0.948`；root 内概率/收益中位 Spearman `−0.406`，且相对同 root 立即入场平均少 `3.663pp`。
- Next gate：本家族不再推进；materially new successor 必须更换 root 来源与目标。

## Version Rules

- P0 容量、P1 hazard 诊断和任何 asset-specific observation 都不构成正式版本。
- 登记版本必须冻结 root/candidate 时序、特征、root 权重、模型、阈值、first-hit 排程、成本与证据。
- 改变 root 来源、候选步长、标签期限、退出或允许 asset id 均是 materially new mechanism。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0/P1 | `explore / HARD-GATE-FAILED` | 五资产逐小时 root landmark、root-grouped first-hit 与 HYPE 硬锁 | [合同](specs/binance-1h-ma7-rht-p0-p1-contract-2026-08-10.md) · [失败诊断](diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md) | 关闭共享 daily MA7 root prior；不解锁 HYPE |

## Shared Assumptions

- Data：沿用 direct `1h`、24 小时重建 UTC `1d` 与官方 funding/mark。
- Timing：只使用 decision timestamp 之前已闭合的 K；在该时间边界的小时 open 成交。
- Cost：fee `0.001/fill`；主结果 `8 bps/fill` 与 actual funding，固定 `0.25x`。
- Exit：首个完整 UTC 日 MA7 recross 边界或 entry 后 120 小时，取较早者。

## Evidence Map

- [P0/P1 非 HYPE hazard 合同](specs/binance-1h-ma7-rht-p0-p1-contract-2026-08-10.md)
- [P1 development 失败诊断](diagnostics/binance-1h-ma7-rht-p1-development-2026-08-10.md)
- [直接前驱 LMML 失败诊断](../1d-ma7-later-maturity-meta-label/diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [决策记录](decision-log.md)
