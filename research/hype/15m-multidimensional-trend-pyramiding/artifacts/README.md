# Artifacts

- `hype_15m_mdtp_v1_research_2026-07-31.json`：完整机器可读结果与数据契约。
- `hype_15m_mdtp_v1_metrics_2026-07-31.csv`：V35、新版本、成本阶梯与模块消融主指标。
- `hype_15m_mdtp_v1_trades_2026-07-31.csv`：三组新框架净成本 campaign 明细。
- `hype_15m_mdtp_v1_actions_2026-07-31.csv`：入场、加仓、减仓、退出动作。
- `hype_15m_mdtp_v1_equity_2026-07-31.csv`：净成本权益曲线。
- `hype_15m_mdtp_v1_parameter_stability_2026-07-31.csv`：27 行邻近阈值/退出稳定性。
- `hype_15m_mdtp_v1_stability_heatmap_2026-07-31.csv`：regime × confirm 聚合稳定区。
- `hype_15m_mdtp_v1_window_stability_2026-07-31.csv`：窗口 `0.8x/1.0x/1.2x`。
- `hype_15m_mdtp_v1_signed_score_quintiles_2026-07-31.csv`：signed score 与未来 24h 收益。
- `hype_15m_mdtp_v1_absolute_score_quintiles_2026-07-31.csv`：score 强度与方向收益/MFE/MAE。
- `hype_15m_mdtp_v1_cross_asset_2026-07-31.csv`：固定参数跨币种诊断；raw parity 未通过的行不可用于 promotion。
- `hype_15m_mdtp_v1_failure_audit_2026-08-02.json`：失败复审机器结果；包含修复 raw parity 后的六币同窗口对照、HYPE 成本阶梯、动作换手、禁止增仓与 V35 matched-window 诊断。
- `hype_15m_mdtp_v1_failure_audit_assets_2026-08-02.csv`：六币同窗口主指标。
- `hype_15m_mdtp_v1_failure_audit_costs_2026-08-02.csv`：HYPE `0–14 bps/fill` 成本容忍度。
- `hype_15m_mdtp_campaign_research_2026-08-02.json`：campaign successor 数据合同、冻结窗口、long/short 选择、Validation、压力、消融、bootstrap 与未揭示 prospective OOS 记录。
- `hype_15m_mdtp_campaign_train_search_2026-08-02.csv`：long/short 各 54 行完整 Train 搜索与三 fold 指标。
- `hype_15m_mdtp_campaign_{long,short}_2026-08-02_validation_{trades,equity,actions}.csv`：两个冻结方向候选的一次性 Validation 账本。
