# HYPE-15M-Factor-ML Round 2 诊断

## 结论

Round 2 已完成数据补齐、可扩展因子库、LightGBM 多轮搜索、封存前稳健性和一次性锁定 OOS。最终结论是：

> `HARD-GATE-FAILED / not promoted / not live-ready`

冻结候选在 `2026-04-17 00:00 UTC` 至 `2026-07-16 15:30 UTC` 的 `8,703` 根 OOS K 线上产生 `0` 笔交易；同期 HYPE 买入持有成本后约 `+48.64%`。本轮没有找到同时满足高收益、高胜率、低回撤和足够交易覆盖的样本外策略。

## 数据完整性

- OHLCV：`39,573` 行，`2025-05-30 10:30 UTC` 至 `2026-07-16 15:30 UTC`。
- Mark Price：`39,573` 行，与 OHLCV 时间轴一一对齐。
- OHLCV/Mark 缺口、重复、空值、未闭合 K 线、OHLC 约束错误：均为 `0`。
- raw/normalized 对账：open、high、low、close、volume、quote volume、trade count、主动买量等字段不一致均为 `0`。
- Funding：`2,472` 行；14 个月 Binance Vision 归档 + API 全量交叉核对 + 当前月 API 尾部，归档/API 相同时间点费率不一致为 `0`，最大正常间隔 `8h`。
- OI 与 basis：各 `2,876` 行，仅覆盖最近约 30 天，占完整生命周期约 `7.27%`；明确排除出主模型，没有把短覆盖字段伪装成完整数据。

证据：[数据质量报告](../artifacts/data_quality/hype_15m_data_quality_round2.json)。

## 因子库

Round 2 不再以“恰好 64 个”为目标。候选因子库扩展到 `157` 个，类别包括 trend、momentum、volatility、liquidity、order flow、derivatives、regime、seasonality、price action 和 mean reversion。

- 候选因子：`157`。
- 覆盖门槛合格：`152`。
- 相关性裁剪后：`121`。
- 入最终冻结模型：`30`。
- 因果前缀重算：所有检查点不一致数为 `0`。
- 每个因子均记录 name、category、formula、direction、inputs、lookback、warmup、version hash 和覆盖率。

完整清单见 [factor_catalog.json](../artifacts/factor_audit_round2/factor_catalog.json)，训练期 IC 与覆盖审计见 [single_factor_train_audit.csv](../artifacts/factor_audit_round2/single_factor_train_audit.csv)，相关性裁剪见 [correlation_pruned.csv](../artifacts/factor_audit_round2/correlation_pruned.csv)。

## 数据切分与防泄漏

- Train：`ts < 2026-01-01 00:00 UTC`。
- Validation：`2026-01-01 00:00 UTC <= ts < 2026-04-17 00:00 UTC`。
- 一次性 OOS：`2026-04-17 00:00 UTC <= ts <= 2026-07-16 15:30 UTC`。
- 模型选择、因子 IC、相关性、阈值、regime、风险参数、walk-forward 和多种子审计均只使用 pre-OOS 数据。
- OOS 揭示前，搜索脚本物理截断到 `2026-04-17`；最终揭示脚本先验证冻结候选的 prefit pass 和哈希，再加载 OOS。
- 信号在闭合 K 线形成，下一根 K 线开盘成交；最后 `48` 根 OOS 信号因最大持有路径不完整而清空。

证据：[切分锁](../artifacts/factor_audit_round2/split_lock_round2.json)、[封存候选](../artifacts/model_round2_stable_ensemble_prefit_robustness/frozen_candidate.json)。

## 搜索过程

### 单一验证集搜索

157 因子扩展后，单一验证集产生 `120` 个过线行，但只有 4 个独立模型身份。代表候选包括：

- 70 笔、净收益 `+20.37%`、胜率 `75.71%`、回撤 `8.80%`、利润因子 `1.44`。
- 86 笔双向、净收益 `+17.29%`、胜率 `74.42%`、回撤 `10.39%`、利润因子 `1.32`。

这些候选在多随机种子或 walk-forward 中失稳，全部被否决，OOS 当时仍保持封存。

### 五折联合搜索

把选择目标改为五个扩展时间折的联合策略表现：

- 36 个模型身份。
- 8,064 个标签/特征集/模型/方向/regime/阈值组合。
- 46 个组合通过跨折联合门槛。
- 最佳单模型跨折结果：170 笔、`+59.59%`、胜率 `79.41%`、回撤 `9.11%`、利润因子 `1.60`，五折全部为正。

该单模型换种子后不稳定，因此继续升级为四随机种子概率集成。

### 四种子集成与稳定性冻结

四种子集成对 6 个前沿身份进行 1,344 次组合搜索，28 行跨折过线。随后对完整集成和四组留一集成共同搜索 477 个阈值，3 行通过稳定性门槛。

冻结候选：

- 模型：`dual_binary_weighted_compact`。
- seeds：`7, 17, 29, 42`，概率平均。
- 特征：训练期 `top30_ic`。
- 标签/执行：最长持有 `48` 根，止盈 `1.0 ATR`，止损 `2.0 ATR`，stop-first，同根冲突先止损。
- 阈值：`p_long >= 0.50` 或 `p_short >= 0.75`，较高概率方向胜出。
- 仓位：固定 `1x`。
- 成本：每次成交手续费 `0.001`，每次成交 `4 bps` 不利滑点，持仓期间实际 funding。

封存前五折：38 笔、`+33.21%`、胜率 `94.74%`、回撤 `2.74%`、利润因子 `6.34`。留一集成 `3/4` 过硬门槛、`4/4` 正收益且利润因子大于 1；阈值邻域 `18/30` 过线；`8 bps` 和 `12 bps` 滑点压力仍保持正收益、胜率和回撤门槛。

需要保留的限制：严格逐折门槛只有 `2/5` 折达到“至少 8 笔且全部指标通过”；另两个折无交易。候选按显式稀疏覆盖门禁进入 OOS，不应把它描述为每个窗口都活跃。

## 最终 OOS

| 指标 | 冻结模型 OOS | 硬门槛 |
| --- | ---: | ---: |
| 交易数 | 0 | >= 30 |
| 净收益 | 0.00% | > 0 |
| 胜率 | 0.00% | >= 55% |
| 最大回撤 | 0.00% | <= 20% |
| 利润因子 | 0.00 | >= 1.30 |
| 买入持有净收益 | +48.64% | 策略应显著优于基准 |

OOS 没有漏单。概率分布为：

- `p_long`：中位数约 `0.260`，99 分位约 `0.265`，最大约 `0.273`，从未达到 `0.50`。
- `p_short`：中位数约 `0.285`，99 分位约 `0.530`，最大约 `0.666`，从未达到 `0.75`。

这表明训练期/验证期与 OOS 发生明显概率分布漂移。由于阈值已冻结，不能在看到 OOS 后把 `0.50/0.75` 降低；那会把最终 OOS 变成新的训练集。

证据：[OOS 报告](../artifacts/model_round2_final_oos/oos_report.json)、[OOS 预测](../artifacts/model_round2_final_oos/oos_predictions.parquet)、[模型清单](../artifacts/model_round2_final_oos/model_manifest.json)、[特征重要性](../artifacts/model_round2_final_oos/feature_importance.csv)。

## 决策与后续边界

1. Round 2 不注册正式版本，不进入 `live spec`、`dry-run` 或 `live`。
2. 已揭示 OOS 永久保留为失败证据，不得用于阈值、标签、特征或超参数优化。
3. 若继续本家族，下一轮应等待并锁定未来新增数据作为新 OOS；旧 OOS最多只能降级为训练/诊断数据，但必须在新一轮开始前写明边界。
4. 下一轮优先研究概率校准漂移、按 regime 的校准器、稳定特征筛选和交易覆盖约束，而不是继续无条件增加因子数量。
5. OI/basis 在取得足够长的原生历史覆盖前仍不得进入主模型。
