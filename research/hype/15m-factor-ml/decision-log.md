# Decision Log

## 2026-07-16：初始化独立研究家族

创建 `HYPE-15M-Factor-ML`，与既有 HYPE 策略家族隔离。首轮目标是验证多因子 LightGBM 是否能在真实成本和可执行订单时序下同时满足高净收益、高胜率和低回撤，而不是预设模型一定成功。

证据：[家族 README](README.md)、[核心台账](hype-15m-factor-ml-core-ledger.md)。

## 2026-07-16：首轮数据与模型结果

标准 Binance HYPEUSDT 15m OHLCV 覆盖 `2025-05-30 10:30 UTC` 至 `2026-07-14 11:15 UTC`，共 `39,364` 根，均为闭合且连续 K 线。因子库生成 `61` 个因子，主模型实际使用 `59` 个覆盖率达到 `95%` 的因子。首轮三分类 LightGBM 在第 `6` 轮早停；验证集和 OOS 均未通过硬门槛，研究线保持 `not promoted / not live-ready`。

证据：[数据集 manifest](artifacts/hype_15m_factor_dataset_manifest.json)、[模型报告](artifacts/model/model_report.json)。

## 2026-07-16：固定阈值随机种子稳健性审计

使用验证集选出的固定阈值，在 `seed=7/17/29/42` 上重新训练并只查看锁定 OOS。4 个种子的 OOS 净收益全部为负，胜率约 `34.8%–39.5%`，最大回撤约 `10.3%–46.1%`，没有一个达到净年化倍数 `10x`、胜率 `70%`、最大回撤 `20%` 和交易数 `30` 的联合门槛。因此当前多因子 LightGBM 研究面保持 `not promoted / not live-ready`，不能注册为 promoted 版本。

证据：[稳健性报告](artifacts/model/robustness.json)。当前状态保持 `not promoted / not live-ready`。

## 2026-07-16：Round 2 数据补齐与可扩展因子库

重新抓取并锁定从 Binance HYPEUSDT 永续上线首根可得闭合 `15m` K 线到 `2026-07-16 15:30 UTC` 的数据。OHLCV 和 Mark Price 各 `39,573` 行，时间轴缺口、重复、空值、OHLC 约束错误及 raw/normalized 不一致均为 `0`；Funding 通过 Binance Vision 月归档、API 全量交叉核对和当月 API 尾部补齐，共 `2,472` 行，归档与 API 费率不一致为 `0`。OI 与 basis 仅能获得最近约 30 天、覆盖全生命周期约 `7.27%`，因此保留为可用性证据但不进入模型。

因子数量不再固定为 64。Round 2 候选库扩展为 `157` 个因子，其中 `152` 个达到覆盖门槛，相关性裁剪后 `121` 个；所有因子有公式、方向、输入、lookback、版本和因果前缀审计，前缀重算未来泄漏不一致为 `0`。

证据：[数据质量报告](artifacts/data_quality/hype_15m_data_quality_round2.json)、[因子目录](artifacts/factor_audit_round2/factor_catalog.json)、[因子审计](artifacts/factor_audit_round2/factor_audit_summary.json)。

## 2026-07-16：Round 2 跨折 LightGBM 搜索与候选冻结

先进行标签、特征集、模型结构、阈值、方向、regime 和风险参数搜索；单一验证集最优候选在多种子和 walk-forward 中失稳，因此不进入 OOS。随后把选择目标改为五个 pre-OOS 扩展时间折的联合表现，在 `36` 个正则化模型身份和 `8,064` 个组合中得到 `46` 个跨折过线行。再对前沿身份做四随机种子概率集成和留一模型稳定性搜索，冻结 `top30_ic`、`dual_binary_weighted_compact`、`h48/tp1.0ATR/sl2.0ATR`、`long=0.50`、`short=0.75`、`1x` 候选。

封存前五折合计 `38` 笔、净收益 `+33.21%`、胜率 `94.74%`、最大回撤 `2.74%`、利润因子 `6.34`；四组留一集成中 `3/4` 通过硬门槛、`4/4` 保持正收益与利润因子大于 1；阈值邻域 `18/30` 通过，`8 bps` 与 `12 bps` 滑点压力均保持过线。严格的“至少三折各有八笔并通过”门槛只通过 `2/5`，但另两折无交易且所有折非负，因此按事先显式记录的稀疏覆盖门禁允许一次性 OOS 揭示；严格逐折门禁失败事实保留。

证据：[广义跨折报告](artifacts/model_round2_crossfold_broad/crossfold_summary.json)、[集成报告](artifacts/model_round2_crossfold_ensemble/ensemble_summary.json)、[稳定性阈值报告](artifacts/model_round2_ensemble_stability_refinement/stability_summary.json)、[封存前稳健性](artifacts/model_round2_stable_ensemble_prefit_robustness/prefit_robustness.json)。

## 2026-07-16：Round 2 一次性 OOS HARD-GATE-FAILED

一次性揭示锁定 OOS `2026-04-17 00:00 UTC` 至 `2026-07-16 15:30 UTC`，共 `8,703` 根 K 线。冻结模型未产生任何交易：OOS `p_long` 最大值约 `0.273`，低于冻结阈值 `0.50`；`p_short` 最大值约 `0.666`，低于冻结阈值 `0.75`。同期包含手续费、`4 bps` 不利滑点和资金费率的买入持有净收益约 `+48.64%`。

Round 2 因交易数、胜率、利润因子、正收益及相对基准均未通过，结论固定为 `HARD-GATE-FAILED / not promoted / not live-ready`。不得利用已揭示 OOS 降低阈值或继续训练；本轮不注册正式版本，也不进入 dry-run 或 live。

证据：[OOS 报告](artifacts/model_round2_final_oos/oos_report.json)、[模型清单](artifacts/model_round2_final_oos/model_manifest.json)、[OOS 预测](artifacts/model_round2_final_oos/oos_predictions.parquet)、[Round 2 诊断](diagnostics/hype-15m-factor-ml-round2-2026-07-16.md)。
