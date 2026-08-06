# BIN-MTF-PTC Goal 完成矩阵

| 要求 | 证据 | 完成状态 | 结论 |
|---|---|---|---|
| 独立家族与冻结合同 | [家族入口](../README.md)、[Goal 合同](../specs/binance-mtf-ptc-goal-contract-2026-08-03.md)、[主账](../binance-mtf-ptc-core-ledger.md) | COMPLETE | 未继承 V35TB/PIC 身份或绩效 |
| BTC/ETH/HYPE 数据质量 | [data audit](../artifacts/binance_mtf_ptc_data_split_audit_2026-08-03.json) | COMPLETE | blocker 0 |
| 趋势识别与延续性验证 | [meter metrics](../artifacts/binance_mtf_ptc_continuation_meter_v0_metrics_2026-08-03.csv)、[audit](../artifacts/binance_mtf_ptc_continuation_meter_v0_audit_2026-08-03.json) | COMPLETE | ETH 成立；BTC 弱；HYPE calibration 失败 |
| 回调/restart 入场 | [V0](../artifacts/binance_mtf_ptc_pullback_entry_v0_summary_2026-08-03.csv)、[V1 earlier onset](../artifacts/binance_mtf_ptc_pullback_entry_v1_early_onset_summary_2026-08-03.csv) | COMPLETE | 固定回调普遍未改善 entry |
| 受治理参数搜索 | [Probe search](../artifacts/binance_mtf_ptc_probe_search_v0_inner_2026-08-03.csv)、[Regime V1](../artifacts/binance_mtf_ptc_regime_campaign_v1_inner_aggregate_2026-08-03.csv)、[Limit V2](../artifacts/binance_mtf_ptc_limit_retest_v2_inner_aggregate_2026-08-03.csv) | COMPLETE | 没有使用 locked evaluation |
| 可执行 Campaign 状态机 | [Campaign engine](../scripts/research_campaign_engine_v0.py)、[逐笔](../artifacts/binance_mtf_ptc_campaign_engine_v0_validation_campaigns_2026-08-03.csv)、[actions](../artifacts/binance_mtf_ptc_campaign_engine_v0_validation_actions_2026-08-03.csv) | COMPLETE | 真实 quantity/lot/stop/cost/funding/pending/risk |
| 动态加减仓消融 | [Campaign metrics](../artifacts/binance_mtf_ptc_campaign_engine_v0_validation_metrics_2026-08-03.csv) | COMPLETE | 默认 half-reduce 失败；BTC no-half 仅为前沿 |
| 成本与风险缩放 | [Scaling](../artifacts/binance_mtf_ptc_risk_scaling_v1_aggregate_2026-08-03.csv) | COMPLETE | 2x 最高合规；3x bar 内 MDD 超 20% |
| 测试 | `9 passed`，见 `tests/test_binance_mtf_ptc_*` | COMPLETE | 标签、事件顺序、pending、limit、risk scaling |
| 交互可视化 | [Evidence HTML](../artifacts/binance_mtf_ptc_goal_evidence_2026-08-03.html) | COMPLETE | 可切换资产并查看 risk frontier |
| 外部复现 Spec | [BTC frontier spec](../specs/binance-mtf-ptc-btc-frontier-reproduction-spec-2026-08-03.md) | COMPLETE | 明确 research-only / not live-ready |
| Runner gap | [能力差距](../runner-tracking/binance-mtf-ptc-runner-gap-2026-08-03.md) | COMPLETE | 未实施 live/dry-run；当前无 parity |
| Historical locked evaluation | 未运行 | CORRECTLY SKIPPED | pre-lock gates 已失败，禁止揭示 |
| 合格资产组合 | 无 | NOT APPLICABLE | 三资产均未取得组合资格 |
| 20x annual / MDD<=20% | [最终报告](binance-mtf-ptc-goal-final-report-2026-08-03.md) | FAILED | 最高合规约 1.134x annual；目标未实现 |

Goal 的研究、实现、验证与交付工作已完成；策略目标失败。最终状态是 `explore / not promoted / not live-ready`，本轮决定 `HARD-GATE-FAILED`。
