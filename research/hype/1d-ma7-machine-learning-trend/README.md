# HYPE-1D-MA7-Machine-Learning-Trend

- Alias：`HYPE-1D-MA7-MLT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`
- 机制：P0 用全体日频状态预测固定持有期收益；P1 学习严格 `SMA7 cross + slope`；P2 学习 raw-cross episode；P3 用精确 raw-cross、purged OOF 特征块与 canonical survival 学习入场和退出；P4 直接以 exact V7.1 为教师做行为克隆与残差退出延长；P5 学习穿越 root 是否进入稳定趋势；P6 以 exact V7.1 为 core，拆分学习补入价值、三日 survival 和反手价值；P7 用 BTC/ETH/BNB/SOL 训练 survival-only 并覆盖 HYPE 的 V7.1 非保护性日线退出。
- 边界：全新独立家族；不继承、不修改 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1` 的版本身份、参数、结论或 runner 权限。
- 当前状态：P0–P6 均未胜出；P7 供体 OOF AUC `0.617` 过线，但 HYPE 内部确认与 V7.1 重合且 365 日迁移更差，状态 `DEVELOPMENT_FAILED_HOLDOUT_LOCKED`。全家族 `diagnostic-only / not promoted / not live-ready`。

## 入口

- [Core Ledger](hype-1d-ma7-mlt-core-ledger.md)
- [决策记录](decision-log.md)
- [P0 冻结实验合同](specs/hype-1d-ma7-mlt-p0-365d-train-validation-contract-2026-08-27.md)
- [P0 结果](diagnostics/hype-1d-ma7-mlt-p0-365d-train-validation-2026-08-27.md)
- [P1 严格穿越与动态退出合同](specs/hype-1d-ma7-mlt-p1-cross-event-dynamic-exit-contract-2026-08-27.md)
- [P1 结果](diagnostics/hype-1d-ma7-mlt-p1-cross-event-dynamic-exit-2026-08-27.md)
- [P1 可拖动交易路径（含 SMA7）](artifacts/hype_1d_ma7_mlt_p1_cross_event_dynamic_exit_2026-08-27_trade_paths.html)
- [P2 Episode Policy 教学合同](specs/hype-1d-ma7-mlt-p2-episode-policy-learning-contract-2026-08-27.md)
- [P2 教学结果](diagnostics/hype-1d-ma7-mlt-p2-episode-policy-learning-2026-08-27.md)
- [P3 Purged Cross Survival 合同](specs/hype-1d-ma7-mlt-p3-purged-cross-survival-contract-2026-08-27.md)
- [P3 训练与验证结果](diagnostics/hype-1d-ma7-mlt-p3-purged-cross-survival-2026-08-27.md)
- [P4 V7.1 行为克隆与残差合同](specs/hype-1d-ma7-mlt-p4-v7-1-behavior-clone-residual-contract-2026-08-27.md)
- [P4 训练与验证结果](diagnostics/hype-1d-ma7-mlt-p4-v7-1-behavior-clone-residual-2026-08-27.md)
- [P4 与 exact V7.1 同图交易路径](artifacts/hype_1d_ma7_mlt_p4_v7_1_behavior_clone_residual_2026-08-27_v7_1_comparison_trade_paths.html)
- [P5 机会修复与生命周期合同](specs/hype-1d-ma7-mlt-p5-opportunity-repair-lifecycle-contract-2026-08-28.md)
- [P5 训练与验证结果](diagnostics/hype-1d-ma7-mlt-p5-opportunity-repair-lifecycle-2026-08-28.md)
- [P5 与 exact V7.1 完整446日对照图](artifacts/hype_1d_ma7_mlt_p5_opportunity_repair_lifecycle_2026-08-28_v7_1_comparison_trade_paths.html)
- [P6 V7.1 锚定三模型生命周期合同](specs/hype-1d-ma7-mlt-p6-v7-anchor-three-head-lifecycle-contract-2026-08-28.md)
- [P6 训练与开发门禁结果](diagnostics/hype-1d-ma7-mlt-p6-v7-anchor-three-head-lifecycle-2026-08-28.md)
- [P6 训练期与内部确认交易路径（后81日未读取）](artifacts/hype_1d_ma7_mlt_p6_v7_anchor_three_head_lifecycle_2026-08-28_v7_1_training_trade_paths.html)
- [P7 跨资产 survival-only 覆盖合同](specs/hype-1d-ma7-mlt-p7-cross-asset-survival-overlay-contract-2026-08-28.md)
- [P7 训练与开发门禁结果](diagnostics/hype-1d-ma7-mlt-p7-cross-asset-survival-overlay-2026-08-28.md)
- [Artifacts](artifacts/README.md)
