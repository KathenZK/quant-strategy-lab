# Scripts — BIN-15M-EMAX-LGBM

一次性研究脚本，按阶段命名。数据落标准数据湖，产物落 [../artifacts/](../artifacts/README.md)。

- P0 数据基建：`inventory_binance_usdm_15m_history.py`（Vision 15m 归档清单）、`sync_binance_usdm_15m_history.py`（月归档校验下载 + raw/normalized 落湖 + 遗留日分区补字段）、`audit_binance_usdm_15m_history.py`（数据质量冻结审计）。
- P1 基线：`extract_cross_events.py`（交叉事件与标签提取）、`run_baseline_a.py`（裸基线 A + 成本/离散度/聚簇 kill test + bracket 预注册选择）。
- P2/P3 建模：`build_event_dataset.py`（特征 + 权重 + manifest）、`train_event_models.py`（purged CV + 校准 + 诊断）。
- P4/P5：`backtest_portfolio.py`（资金约束组合回测）、`freeze_candidate.py` / `reveal_locked_oos_once.py`（冻结与一次性揭示）。
- 归档后死因复核：`diagnose_oos_score_drift.py`（分数漂移诊断）、`relabel_custom_bracket.py`（任意 bracket 重标注）、`research_feature_label_ablation.py`（2×2 特征/标签消融）、`research_feature_ablation_a2.py`（a2 增补：多日趋势特征）、`research_ema_pair_ablation.py`（换对消融：EMA30/120 对照）。
- A/F 增补（极限终判）：`inventory_binance_usdm_metrics.py` / `sync_binance_usdm_metrics.py`（Vision USDM metrics 清单与范围化同步，explore 级落 `data/normalized/derivatives_metrics/`）、`research_feature_ablation_f.py`（F 族：量价分布/90d 动量/VWAP）、`research_feature_ablation_a.py`（A 族：OI/多空比 + 终判）、`research_feature_ablation_k.py`（K 族：蜡烛形态三尺度）。
