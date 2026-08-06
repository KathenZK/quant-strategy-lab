# Artifacts（已清理）

本目录的中间产物与大体积数据已于 2026-08-04 磁盘清理时删除。
研究结论与版本身份以家族 README、core ledger、diagnostics、specs 与 decision-log 为准；需要复现时用 scripts/ 从数据湖重建。

---

# Artifacts

本目录保存 Goal 冻结脚本生成的机器可读 data-quality、feature/label validation、search registry、metrics、campaign、layer、action、equity、rolling、ablation、stress 和可视化数据。禁止手工修改生成文件。

主要证据组：

- `binance_mtf_ptc_data_split_audit_*`：数据与切分；
- `binance_mtf_ptc_continuation_meter_v0_*`：meter、子组和消融；
- `binance_mtf_ptc_pullback_entry_*` / `probe_search_v0_*`：回调诊断与 probe 搜索；
- `binance_mtf_ptc_campaign_engine_v0_*`：真实 lot Campaign；
- `binance_mtf_ptc_regime_campaign_v1_*`：日/周方向先验 rolling folds；
- `binance_mtf_ptc_limit_retest_v2_*`：限价回踩；
- `binance_mtf_ptc_risk_scaling_v1_*`：1x/2x/3x 风险边界。
- [`binance_mtf_ptc_goal_evidence_2026-08-03.html`](binance_mtf_ptc_goal_evidence_2026-08-03.html)：可交互资产、meter、集中度与风险缩放证据页。

所有 JSON 均明确 `locked_evaluation_used=false`。
