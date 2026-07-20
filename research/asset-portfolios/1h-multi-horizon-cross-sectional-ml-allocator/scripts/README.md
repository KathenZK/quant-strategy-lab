# BIN-1H-MHCSML Scripts

本目录只存放该家族的数据审计、标签/面板、nested walk-forward、模型比较、allocator、冻结和 prospective OOS 门禁脚本。命令统一从仓库根目录通过 `uv run python ...` 执行。

任何读取 `2026-07-19 <= ts < 2026-10-19 UTC` 标签、收益或绩效的脚本必须在冻结 manifest 中列出，并在窗口结束前 fail closed。

当前主要入口：

- `prepare_development_model_matrix.py`：只读取 `2026-04` 之前的物理分区，生成 4h 基准决策矩阵；2026Q2 与 prospective OOS 标签均不进入该矩阵。
- `train_development_walk_forward.py`：7 个 expanding outer folds、48h purge、120 天 inner validation；分别训练 long return、short return、long/short MAE 和 crash/squeeze event 模型。
- `search_development_allocator.py`：只消费 OOF 预测，比较 LightGBM 与规则基线，并搜索可空仓、可变 N、尾部风险惩罚及重叠持仓敞口受限的 allocator。
- `search_h48_confirmation_allocator.py`、`search_h48_local_risk_allocator.py`：48h 模型确认与局部风险前沿。
- `search_h48_calibrated_utility_allocator.py`：对 raw utility 做逐时横截面稳健 z-score，解决最终 refit 模型的分数相关性/标度迁移，同时重新执行完整 OOF 账户回测。
- `audit_h48_candidate_seed_stability.py`：固定 R4 后逐 seeds `7/17/29/42` 和四种子集成审计，不再搜索参数。
- `freeze_development_candidate.py`：在 prospective OOS 开始前写入参数锁与证据 SHA；当前有效锁为 R4，R1-R3 均保留作废链。
- `train_frozen_final_models.py`：参数先锁定后，才允许把 reused 2026Q2 用于最终 refit；输出 4 个模型职责 × 4 seeds 的 16 个模型。
- `bind_frozen_models_to_candidate_r2.py`：验证 16 个模型 SHA，并把未改变的模型二进制绑定到最终 R4 allocator 锁。
- `sync_binance_usdm_freeze_gap.py`：通过 FAPI 补当前月全市场 OHLCV/mark，并用全市场 funding 分页避免逐币 403；写回标准数据湖。
- `build_prefreeze_inference_panel.py`：只构造特征和 PIT universe，不生成任何 label。
- `score_frozen_prefreeze_panel.py`：只输出模型分数、决策和计划腿，不读取收益/PnL；用于启动前 dry inference。
- `freeze_comparison_baselines.py`：冻结 compact Ridge 与 carry-momentum 规则的受控比较基线；只用无标签 freeze-gap 密度校准信号数量。
- `frozen_r4_inference.py`：R4 与受控基线共用的只读评分内核；批内腿按 `3.125% / N` 等权。
- `sync_binance_usdm_prospective_features.py`：每轮从 FAPI 补 OHLCV、mark、funding 并写入标准数据湖；只做特征输入，不生成标签。
- `build_blind_prospective_panel.py`：重建最近 8 小时的 feature-only PIT 横截面，禁止 outcome 列。
- `collect_blind_prospective_signals.py`：每个 K0 闭合后 25 分钟内写不可变信号快照和 SHA 链；迟到节点只能记 `MISSED`。
- `audit_blind_chain_health.py`：只读核验当前应有节点、时间序列、链链接、master SHA、按时/MISSED 语义、快照 SHA 和无 outcome schema；只输出健康计数与 blocker。
- `reveal_prospective_oos_once.py`：最后 48h 腿成熟前 fail closed；最早 `2026-10-20 21:05 UTC` 才允许一次性读取收益并执行硬门槛。
- `finalize_prospective_oos_adjudication.py`：在 reveal 后把 15 个 OOS 门槛与历史 folds、seed 稳定、因子组消融、tail IC、盲链和输出 SHA 合并成唯一总裁决；基础全部通过才授权 3x 研究。
- `audit_three_x_tail_risk.py`：仅在基础总裁决全部通过后，把冻结腿敞口放大为 `3x`，执行逐小时 mark、联合 mark-high、6 个成本/MMR 场景和强平风险审计；不改变基础裁决或 promotion 状态。
- `audit_historical_factor_group_ablation.py`：只读 `<2026-04-01` development OOF，执行逐时横截面因子组置乱消融与 28 fold-seed tail IC 稳定审计；不触碰 prospective OOS。

当前 master freeze：[`bin-1h-mhcsml-v1-freeze-r4.json`](../artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json)，SHA256 `64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11`。

最终裁决合同：[`bin-1h-mhcsml-v1-final-adjudication-contract-r4.json`](../artifacts/freeze/bin-1h-mhcsml-v1-final-adjudication-contract-r4.json)，SHA256 `a5bb2d45f4edd5289990315ee67a5953b16ead61436fc438dc4b4bb27407f433`。它只冻结评估治理，不改变 master freeze 或信号；门槛测试已覆盖 15 项阈值边界、回撤方向、严格基线胜负和三段固定月份。

条件式 3x 风险合同：[`bin-1h-mhcsml-v1-three-x-risk-contract-r4.json`](../artifacts/freeze/bin-1h-mhcsml-v1-three-x-risk-contract-r4.json)，SHA256 `0cc877cd934173af033e355462e627b6a64ddcfa0c1fedb0c9b408f145a0b4ce`。它在 outcome-blind 状态下预先冻结 3x 语义、风险门槛、master/decisions 核验与输入输出 SHA 收据，只有基础门槛全部通过才允许执行。

开发矩阵命令：

```bash
uv run python research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/scripts/prepare_development_model_matrix.py --overwrite
```

任何候选只有完成多 seed、模型/因子消融、meta walk-forward 稳定性和冻结 SHA 后，才允许登记为 `V1`。

当前有效开发冻结为 R4。R1-R3 的 JSON/SHA 仅用于审计 supersession，不得用于 prospective OOS 或混合信号。
