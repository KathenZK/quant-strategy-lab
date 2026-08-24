# BTC-1D-MA7-RSI6-LightGBM-Trend Core Ledger

## Family Identity

- Full family name：`BTC-1D-MA7-RSI6-LightGBM-Trend`
- Alias：`BTC-1D-MA7-RSI6-LGBM`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`BTCUSDT` perpetual，UTC `1d`
- Mechanism：以固定 `SMA7` 几何关系、严格收盘跨越事件、日 K 形态和 Wilder `RSI6` 阶段状态为输入，用 LightGBM 研究趋势延续及多空反转机会。
- Boundary：独立于 `HYPE-1D-MA7-ABT`、`BIN-1D-MA7-AS-SEARCH` 与 `BTC-1D-QZ-CPT`；不继承其版本或 promotion 证据。

## Current State

- Current version：无；P0 只是数据与特征定义阶段。
- Current status：`explore / diagnostic-only / not promoted / not live-ready`。
- Data：已同步 `2019-09-09` 至 `2026-08-06 UTC` 共 `2,524` 根完整闭合日 K；缺 K、重复、OHLC、关键空值、闭合状态及 raw/normalized 对齐均无 blocker。
- Frozen validation：最近完整一年 `2025-08-07` 至 `2026-08-06 UTC`，共 `365` 根，仅允许在开发、特征、标签、模型、阈值和执行规则全部冻结后揭示。
- Agreed features：严格 `SMA7` 上穿/下穿事件可作为离散特征；Wilder `RSI6` 作为连续阶段特征，并要求 MA7-only、RSI6-only 与组合消融。
- Model state：P1/P2/P3 均失败；P3 固定 `1.00%` Logistic-EV combined 为 `47` 笔、`+15.10%`、PF `1.2620`，但仅 `2/4` 折绝对正、`1.50%` 压力失败、bootstrap 净正概率仅 `60.94%`。
- Diagnostic lead：P3 short-only 为 `14` 笔、`+33.73%`、PF `2.9524`、四折全正，但交易数不足且 bootstrap `91.93% < 95%`。
- Validation：仍未读取；P1/P2/P3 均无 validation 揭示资格。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Next gate：停止同一 BTC 特征/edge 微调；若继续，须在新合同中采用方向对齐特征或建立独立多资产 pooled 研究。

## Version Rules

- P0 数据同步、特征提案和诊断不构成正式版本。
- 未来若登记 `V1`，必须同时冻结特征公式、标签、训练窗口、模型配置、阈值、持仓状态机、成本和证据链接。
- 标签、预测 horizon、特征集合、模型容量、阈值或执行时序发生实质变化时，不得静默覆盖已登记版本。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| P0 data and feature contract | `explore / diagnostic-only` | 完整 BTCUSDT 永续日 K、最近一年冻结验证、MA7 跨越与 RSI6 首批特征 | [P0 合同](specs/btc-1d-ma7-rsi6-lgbm-p0-data-feature-contract-2026-08-07.md) · [数据质量](artifacts/btcusdt_perp_1d_data_quality_2026-08-07.json) | 数据门禁通过；尚无模型或策略结论 |
| P1 development observation | `explore / diagnostic-only` | 严格 MA7 事件的成本后净正 meta-label；RSI6 极值反向退出；nested LightGBM/Logistic 消融 | [P1 合同](specs/btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md) · [P1 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p1-development-2026-08-07.md) | development failed；validation 未揭示；不登记版本 |
| P2 expected-return observation | `explore / diagnostic-only` | 固定 P1 事件与执行，L2 raw-return 主模型、Huber/ATR/Ridge/Logistic-EV 对照 | [P2 合同](specs/btc-1d-ma7-rsi6-lgbm-p2-expected-return-contract-2026-08-10.md) · [P2 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p2-expected-return-2026-08-10.md) | L2 主模型 failed；Logistic-EV 仅为 P3 线索；validation 未揭示 |
| P3 Logistic-EV robustness | `explore / diagnostic-only` | 固定 `1.00%` edge、绝对折收益、双 edge 压力、分层 bootstrap | [P3 合同](specs/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-contract-2026-08-10.md) · [P3 诊断](diagnostics/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-2026-08-10.md) | robustness failed；short-only 低样本线索；validation 未揭示 |

## Shared Assumptions

- Data source：Binance FAPI `/fapi/v1/klines`，`binance_futures_kline_api_direct`；仅接受完整闭合 UTC 日 K。
- Timing：日线特征在 `t` 日收盘后可知，最早 `t+1` 日开盘成交。
- Cost：未来 Binance 回测默认每 fill 手续费 `0.001`、不利滑点 `4 bps`，perpetual 持仓另计实际 funding。
- Evidence role：冻结最近一年可作为本模型流程的一次性验证，但既有 BTC MA7 历史已被研究者查看，不能包装为全新资产级 prospective 证据。

## Evidence Map

- [P0 数据与特征合同](specs/btc-1d-ma7-rsi6-lgbm-p0-data-feature-contract-2026-08-07.md)
- [P1 development 合同](specs/btc-1d-ma7-rsi6-lgbm-p1-development-contract-2026-08-07.md)
- [P1 development 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p1-development-2026-08-07.md)
- [P2 expected-return 合同](specs/btc-1d-ma7-rsi6-lgbm-p2-expected-return-contract-2026-08-10.md)
- [P2 expected-return 诊断](diagnostics/btc-1d-ma7-rsi6-lgbm-p2-expected-return-2026-08-10.md)
- [P3 Logistic-EV 稳健性合同](specs/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-contract-2026-08-10.md)
- [P3 Logistic-EV 稳健性诊断](diagnostics/btc-1d-ma7-rsi6-logistic-ev-p3-robustness-2026-08-10.md)
- [数据质量证据](artifacts/btcusdt_perp_1d_data_quality_2026-08-07.json)
- [1h stop-path 数据质量](artifacts/btcusdt_perp_1h_stop_path_quality_2026-08-07.json)
- [funding/mark 数据质量](artifacts/btcusdt_funding_mark_quality_2026-08-07.json)
- [数据同步脚本](scripts/sync_btcusdt_perp_1d.py)
- [产物索引](artifacts/README.md)
- [决策记录](decision-log.md)
