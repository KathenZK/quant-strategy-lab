# HYPE-15M-Factor-ML Core Ledger

## Family Identity

- 完整家族名：`HYPE-15M-Factor-ML`
- 别名：`HYPE-15M-FML`
- 市场：Binance HYPEUSDT perpetual
- 周期：`15m`
- 机制：多因子特征库 + LightGBM 概率预测 + 成本后可执行 bracket 回测
- 边界：不继承其他 HYPE 家族的版本、参数或 promotion 结论

## Current State

- 状态：`explore / not promoted / not live-ready`
- 当前版本：尚未注册正式版本
- 当前观察：Round 2 已完成数据补齐、157 因子扩展、跨折/多种子集成搜索和一次性 OOS；冻结候选在 OOS 产生 0 笔交易，`HARD-GATE-FAILED`
- 下一道门：不得再使用已揭示 OOS 调参；若继续研究，必须重新定义只使用未来新增数据的下一轮 holdout，并优先解决概率校准和跨 regime 分布漂移

## Version Rules

- 因子集合、标签、模型配置、阈值和执行模型任一冻结边界发生实质变化，注册新的家族版本。
- 单次训练、阈值观察和诊断结果不自动成为版本。
- 进入 `live spec`、`dry-run` 或 `live` 前必须另行完成 live-executable 审计。

## Version Table

| 版本 | 状态 | 角色 | 决策 |
| --- | --- | --- | --- |
| 首轮研究面 | explore | 61 因子、三分类 LightGBM、15m triple-barrier 标签 | 验证/OOS 未通过硬门槛，暂不注册/不推广 |
| Round 2 研究面 | explore | 157 因子候选库、30 因子四种子 LightGBM 集成、五折联合筛选 | 封存前门禁通过；锁定 OOS 0 笔交易，`HARD-GATE-FAILED`，不注册/不推广 |

## Shared Assumptions

- 使用标准数据湖 `normalized` 层的已闭合 Binance HYPEUSDT 15m OHLCV。
- funding 和 mark price 通过不使用未来时间的 as-of 对齐；OI/basis 覆盖不足或为空时不进入主模型。
- Binance 默认手续费：每次成交名义金额的 `0.001`；每次成交不利滑点 `4 bps`。
- 因子值只使用当前闭合 K 线及历史；标签使用下一根开盘之后的未来路径。
- 因子库按目标和信息增量扩展，不固定为 64 个；单模型只使用经训练期 IC 与相关性筛选后的子集。
- Round 2 OOS 硬筛选线：交易数 `>=30`、胜率 `>=55%`、利润因子 `>=1.30`、最大回撤 `<=20%`、净收益为正，并与同期买入持有比较。
- Round 2 锁定 OOS 只揭示一次；揭示后不得把该窗口用于模型、阈值、标签或风控调参。

## Evidence Map

- 数据集构建：[build_hype_15m_factor_dataset.py](scripts/build_hype_15m_factor_dataset.py)
- 标签构建：[label_hype_15m_dataset.py](scripts/label_hype_15m_dataset.py)
- 模型训练：[train_hype_lgbm.py](scripts/train_hype_lgbm.py)
- 执行回测：[backtest_hype_lgbm.py](scripts/backtest_hype_lgbm.py)
- 因子数据集：[hype_15m_factor_dataset.parquet](artifacts/hype_15m_factor_dataset.parquet)
- 数据集 manifest：[hype_15m_factor_dataset_manifest.json](artifacts/hype_15m_factor_dataset_manifest.json)
- 模型报告：[model_report.json](artifacts/model/model_report.json)
- 稳健性审计：[robustness.json](artifacts/model/robustness.json)
- 首轮诊断：[hype-15m-factor-ml-round1-2026-07-16.md](diagnostics/hype-15m-factor-ml-round1-2026-07-16.md)
- Round 2 数据质量：[hype_15m_data_quality_round2.json](artifacts/data_quality/hype_15m_data_quality_round2.json)
- Round 2 因子清单与元数据：[factor_catalog.json](artifacts/factor_audit_round2/factor_catalog.json)
- Round 2 因子审计：[factor_audit_summary.json](artifacts/factor_audit_round2/factor_audit_summary.json)
- Round 2 广义跨折搜索：[crossfold_summary.json](artifacts/model_round2_crossfold_broad/crossfold_summary.json)
- Round 2 集成稳定性搜索：[stability_summary.json](artifacts/model_round2_ensemble_stability_refinement/stability_summary.json)
- Round 2 封存前稳健性：[prefit_robustness.json](artifacts/model_round2_stable_ensemble_prefit_robustness/prefit_robustness.json)
- Round 2 最终 OOS：[oos_report.json](artifacts/model_round2_final_oos/oos_report.json)
- Round 2 模型与特征重要性：[model_manifest.json](artifacts/model_round2_final_oos/model_manifest.json)、[feature_importance.csv](artifacts/model_round2_final_oos/feature_importance.csv)
- Round 2 诊断：[hype-15m-factor-ml-round2-2026-07-16.md](diagnostics/hype-15m-factor-ml-round2-2026-07-16.md)
