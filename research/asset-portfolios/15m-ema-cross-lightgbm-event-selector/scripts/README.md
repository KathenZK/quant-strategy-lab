# Scripts — BIN-15M-EMAX-LGBM

一次性研究脚本，按阶段命名。数据落标准数据湖，产物落 [../artifacts/](../artifacts/README.md)。

- P0 数据基建：`inventory_binance_usdm_15m_history.py`（Vision 15m 归档清单）、`sync_binance_usdm_15m_history.py`（月归档校验下载 + raw/normalized 落湖 + 遗留日分区补字段）、`audit_binance_usdm_15m_history.py`（数据质量冻结审计）。
- P1 基线：`extract_cross_events.py`（交叉事件与标签提取）、`run_baseline_a.py`（裸基线 A + 成本/离散度/聚簇 kill test + bracket 预注册选择）。
- P2/P3 建模：`build_event_dataset.py`（特征 + 权重 + manifest）、`train_event_models.py`（purged CV + 校准 + 诊断）。
- P4/P5：`backtest_portfolio.py`（资金约束组合回测）、`freeze_candidate.py` / `reveal_locked_oos_once.py`（冻结与一次性揭示）。
