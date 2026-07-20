# BIN-1H-MHCSML 历史 OOF、模型与 allocator 审计（2026-07-18）

## 结论

历史开发只使用 `< 2026-04-01 00:00 UTC` 的物理隔离矩阵。7 个 expanding rolling outer folds 均使用 `48h` purge，inner validation 为末尾 `120d` 且再留 `48h` purge；预测必须来自对应 outer fold 未参与训练的 OOF 模型。`2026Q2`、freeze gap 和 prospective OOS 均未参与本报告的候选选择。

最终开发候选为 `BIN-1H-MHCSML-V1 freeze R4`：

- `48h` 持有、每 `4h` 决策、short-only；
- stable-full `235` 因子的 LightGBM L1 short-return 模型；
- stable-full short-MAE `80%` quantile 模型与 short-squeeze classification 模型；
- compact `86` 因子的 short-return classification 确认模型；
- seeds `7/17/29/42` 等权集成；
- `raw_utility = return_z + 0.25 * confirmation_z - 1.0 * mae_z - 0.5 * event_z`；
- 对每个时点的 `raw_utility` 再做 median/std 横截面稳健 z-score，`utility_z >= 1.75` 才允许入选；
- 每个决策最多 `5` 腿，总 gross cap `37.5%`，48h 重叠持仓下每个 sleeve 为 `3.125%`；无通过项时空仓。

四种子集成历史 OOF：累计 `+354.64%`、年化 `59.30%`、最大回撤 `17.77%`、决策胜率 `53.67%`、Sharpe `4.49`、PF `1.546`，`7/7` outer folds 盈利；1.5x 成本压力后累计 `+273.76%`、最大回撤 `19.70%`。历史胜率仍低于最终 prospective OOS 的 `55%` 硬门槛，不能称为最终通过。

## 标签预测能力

compact 基准模型的 7-fold mean cross-sectional rank IC：

| 任务 | 4h | 8h | 12h | 24h | 48h |
| --- | ---: | ---: | ---: | ---: | ---: |
| short net return / L1 regression | 0.0508 | 0.0723 | 0.0764 | 0.0704 | 0.0825 |
| short MAE / q80 quantile | 0.4321 | 0.4191 | 0.4115 | 0.3958 | 0.3772 |
| short squeeze 10% / classification | 0.1871 | 0.2213 | 0.2454 | 0.2832 | 0.3031 |

收益 IC 不高但各期限为正；尾部模型的 IC 明显更强，因此最终 allocator 不把 LightGBM 当成直接买卖按钮，而是把收益排序与 MAE/squeeze 风险分离后组合。

## 模型与特征比较

以下均为开发 OOF 搜索结果；不同网格的最佳行只用于机制比较，不能直接互相拼接成策略：

| 机制 | 代表性开发结果 | 结论 |
| --- | --- | --- |
| compact L1 regression | 48h 风险约束前沿年化约 `27.55%`、DD `19.32%` | 有效但容量有限 |
| stable-full L1 regression | 单 seed 风险局部搜索年化 `61.67%`、DD `18.53%` | 235 个稳定覆盖特征有明显增益 |
| stable-full L2 | 年化 `41.62%`、DD `27.78%` | 不如 L1 |
| stable-full Huber | 年化 `54.57%`、DD `32.11%` | 收益尚可但回撤不合格 |
| tail-stable return-only | 年化 `27.68%`、DD `34.18%` | 仅尾部特征不足以预测方向 |
| compact classification | 年化 `13.57%`、DD `36.00%` | 不适合作唯一方向模型 |
| compact ranker | 年化 `14.87%`、DD `24.94%` | 不如 L1 regression |
| compact quantile / Ridge | quantile 年化约 `-1.38%`；Ridge 年化 `-12.59%`、DD `67.29%` | 淘汰 |
| 规则 carry-momentum | 无约束年化可达 `214.24%`，但 DD `63.25%`、胜率 `42.21%` | 高收益来自不可接受的尾部风险，未通过同口径风险门禁 |
| R4 四种子 LightGBM allocator | 年化 `59.30%`、DD `17.77%`、胜率 `53.67%`、PF `1.546` | 当前唯一冻结候选 |

`full-plus-sparse=241` 中 6 个 sparse Donchian event 特征未进入最终模型：它们未达到 stable-full 的 `>=80%` 历史覆盖门槛，不能用缺失值密集的特征为少数时期制造表现。最终 stable-full 为 `235`，compact 确认模型为 `86`。完整覆盖率见 [`factor_coverage_2026-07-18.csv`](../artifacts/factor_coverage_2026-07-18.csv)。

## 多随机种子稳定性

| 模型身份 | 年化 | 最大回撤 | 胜率 | Sharpe | PF | 盈利 folds | 压力 DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| seed 7 | 40.45% | 18.57% | 52.18% | 3.22 | 1.378 | 5/7 | 21.16% |
| seed 17 | 49.67% | 19.50% | 52.66% | 4.32 | 1.504 | 7/7 | 21.72% |
| seed 29 | 38.46% | 19.43% | 52.35% | 3.35 | 1.384 | 6/7 | 22.05% |
| seed 42 | 49.52% | 15.93% | 53.81% | 3.54 | 1.473 | 6/7 | 16.94% |
| 四种子集成 | 59.30% | 17.77% | 53.67% | 4.49 | 1.546 | 7/7 | 19.70% |

所有 seed 基础和压力成本收益均为正，基础 DD 均不超过 `25%`。四种子集成优于任一单 seed 的风险收益组合，因此最终模型固定为四种子等权，不允许在 prospective OOS 中按表现切换 seed。

## allocator 修订审计

- R1：`8h / max_positions=1`，三个月理论最多约 `276` 腿，数学上不可能通过 `>=300` 腿门槛，作废。
- R2：改为 `4h / max_positions=5`，但最终 refit 模型在无标签 freeze-gap 的固定 raw-utility 标度上仅产生 `5/106` 个活跃决策，标度迁移风险不可接受，作废。
- R3：引入横截面 utility 校准，`utility_z>=2.0`；历史通过，但 freeze-gap 无标签分布投射约 `234` 腿，仍低于合同，作废。
- R4：使用同一预先搜索网格中的 `utility_z>=1.75`；历史 OOF 预计三个月约 `346` 个有效决策、`785` 腿，freeze-gap 无标签 dry inference 为 `63/106` 个活跃决策、`95` 腿，按 92 天等比例约 `495` 腿。R4 为 prospective OOS 开始前最后一次冻结。

freeze-gap 的活动密度校验只读特征、模型分数和信号，不读取标签、逐腿收益或组合绩效。

## 边界

本报告只证明历史开发门禁和 OOS 数量可行性，不证明未来盈利。`2026-07-19 <= ts < 2026-10-19 UTC` 结束前不得报告 prospective 收益、胜率、回撤、IC 或任何可反推表现的统计；最终只能揭示一次。当前状态必须保持 `registered / not promoted / not live-ready`。
