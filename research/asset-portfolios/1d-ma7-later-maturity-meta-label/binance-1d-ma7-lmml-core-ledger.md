# Binance-1D-MA7-Later-Maturity-Meta-Label Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Later-Maturity-Meta-Label`
- Alias：`BIN-1D-MA7-LMML`
- Market / timeframe：Binance USD-M perpetual；完整 UTC `1d` 信号，direct `1h` 路径与因果特征
- Training universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Transfer target：`HYPEUSDT`，仅在非 HYPE development gate 与模型锁定后允许一次性诊断
- Mechanism：soft SMA7 cross 后按 HYPE V6 的多空非对称 slope/buffer 规则等待最多五日成熟；用独立 probe 的成本后经济结果训练 pooled meta-label，筛选被 V6 core 拒绝的机会。
- Collision warning：不继承 `BIN-1D-MA7-RSI6-DAPML`、CTLS 或 `HYPE-1D-MA7-ABT` 的版本身份与 promotion 证据。

## Current State

- Current version：无；P0 数据容量通过，P1 pooled development 已失败。
- Status：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。
- Selection boundary：模型、特征、正则、route 与 threshold 只能由 `2025-05-31 UTC` 前的非 HYPE 数据选择。
- HYPE boundary：432 日 HYPE 历史已经暴露；即使固定迁移通过，也只能记作 `exposed-target transfer support`，不能作为 clean OOS 或 promotion 证据。
- Model state：无 frozen model；OOF 只有 BNB/SOL 为正、排序相关近零，HYPE 未解锁。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Next gate：同一 maturity snapshot 关闭；另立独立 `1h` root-level hazard timing 家族。

## Version Rules

- P0 数据、P1 development 与 HYPE transfer 诊断都不自动构成正式版本。
- 登记版本必须冻结数据 SHA、root/maturity 语义、特征顺序、模型状态、阈值、probe 排程、成本和完整证据。
- 标签、入场时点、退出、资产池、时间边界或 core/probe 资本耦合变化均属于 materially new mechanism，不得静默覆盖。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0 data/capacity | `explore / diagnostic-only` | HYPE 上线前五资产 direct `1h`、UTC `1d`、funding 与 1,448 个完整成熟事件 | [P1 诊断](diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md) | PASS |
| P1 pooled development | `HARD-GATE-FAILED / explore` | L2 Logistic nested LOAO/time 筛选成本后 maturity probe | [合同](specs/binance-1d-ma7-lmml-p0-p1-contract-2026-08-10.md) · [诊断](diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md) | 不生成 frozen model；HYPE 保持锁定 |

## Shared Assumptions

- Data：沿用已审计 direct `1h`、24 小时聚合 UTC `1d` 与官方 funding/mark；训练截止早于 HYPE 上线。
- Timing：日线 `t` 收盘确认，最早 `t+1` 开盘成交；所有小时特征只使用已经闭合的 K。
- Cost：每 fill fee `0.001`；主标签使用每 fill `8 bps` 不利滑点与实际 funding，`4 bps` 只作宽松对照。
- Probe：固定 `0.25x`，不改变 V6 core 状态；HYPE 组合评估同时报告共享权益与冻结 core notional 分解。

## Evidence Map

- [P0/P1 非 HYPE 数据与模型合同](specs/binance-1d-ma7-lmml-p0-p1-contract-2026-08-10.md)
- [P1 非 HYPE development 失败诊断](diagnostics/binance-1d-ma7-lmml-p1-development-2026-08-10.md)
- [产物索引](artifacts/README.md)
- [决策记录](decision-log.md)
- [HYPE V6 漏趋势归因报告](../../hype/1d-ma7-asymmetric-body-trend/diagnostics/hype-1d-ma7-v6-missed-trend-attribution-2026-08-10.md)
