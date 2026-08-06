# Artifacts

本目录保存 Goal 的数据质量、实验注册表、全候选指标、Pareto frontier、逐 Campaign/lot/action 账本、rolling OOS、压力测试、搜索摘要与交互式 HTML。

仅 durable、可复现证据进入本目录；临时并行搜索分片先写 scratch，合并和校验后再晋升。

- `binance_mtf_dstc_data_audit_2026-08-04.json`：cutoff-safe OHLCV/funding/raw parity 与因果聚合审计。
- `binance_mtf_dstc_contract_status_2026-08-04.json`：Binance 官方 `exchangeInfo` 当前交易状态、tick/step/min-notional 快照。
- `binance_mtf_dstc_baselines_2026-08-04.*`：E01 基线。
- `binance_mtf_dstc_single_variable_2026-08-04.*`：E02 单变量搜索。
- `binance_mtf_dstc_combinations_2026-08-04.*`：E03 有资格槽位组合。
- `binance_mtf_dstc_layers_mfe_2026-08-04.*`：E04 Probe/Add/MFE 归因。
- `binance_mtf_dstc_stability_2026-08-04.*`：E05 risk/stress/delay/side/rolling 审计。
- `binance_mtf_dstc_campaign_audit_2026-08-04.html`：四个 E05 候选的交互式权益与 Campaign 时间带。
- `stability_ledgers/`：四个冻结诊断候选在 1% 风险下的 Campaign/lot/action/equity Parquet 账本。
