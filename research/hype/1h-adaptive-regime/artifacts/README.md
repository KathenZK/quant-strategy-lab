# Artifacts（已清理）

本目录的中间产物与大体积数据已于 2026-08-04 磁盘清理时删除。
研究结论与版本身份以家族 README、core ledger、diagnostics、specs 与 decision-log 为准；需要复现时用 scripts/ 从数据湖重建。

---

# Artifacts

本目录存放 `HYPE-1H-Adaptive-Regime` 可再生证据，包括：

- 数据质量与合约快照 JSON；
- 搜索 ranking、时间切片、交易明细、参数邻域、成本/延迟压力 CSV；
- 搜索 summary JSON。

当前关键产物：

- `hype_binance_1h_data_quality.json`：全量 K、资金费和 Binance 合约过滤器快照。
- `hype_1h_adaptive_regime_search_2026-07-01.json`：第一轮 `120,768` 配置广搜。
- `hype_1h_adaptive_regime_refine_2026-07-01.json`：第二轮 `180,000` unique-neighbor 精调。
- `hype_1h_adaptive_regime_boundary_audit_2026-07-01.json`：最终 not-promoted 审计。
- `hype_1h_adaptive_regime_boundary_stress_2026-07-01.csv`：延迟、成本和暴露压力。
- `hype_1h_adaptive_regime_boundary_ablation_2026-07-01.csv`：`164` 行单腿与 active-field 消融。
- `hype_1h_ar_v1_full_ablation_2026-07-02.json`：V1 刷新指标、`76/76` 全字段覆盖和分类汇总。
- `hype_1h_ar_v1_full_ablation_fields_2026-07-02.csv`：逐字段 dormant/fixed/active 分类及 V2 删除证据。
- `hype_1h_ar_v2_clean_tune_2026-07-02.json`：V2 exact-equivalence 与第一轮 active 参数微调。
- `hype_1h_ar_v2_tune_frontier_audit_2026-07-02.json`：基础达标前沿的实盘压力审计，稳健通过 `0`。
- `hype_1h_ar_v2_live_robust_tune_2026-07-02.json`：`800 x 800` 三场景 prefit 联合搜索及冻结后诊断。
- `hype_1h_ar_v2_live_robust_ranking_2026-07-02.csv`：三场景预拟合排名前 `1,000` 行。

非 Markdown artifacts 默认被仓库 `.gitignore` 忽略；以 `scripts/` 下脚本复现，不手工编辑。
