# HYPE-EMA-TB-V35 LightGBM 信号评分诊断（2026-07-17）

## 结论

本轮 LightGBM 信号评分 **没有提升 HYPE-EMA-TB-V35**，结论为 `diagnostic only / not promoted / not live-ready`：

- `ml_filter` 在校准段把胜率从 `80.77%` 提到 `92.86%`、最大回撤从 `-21.87%` 缩到 `-17.32%`，但收益也从 `+239.59%` 降到 `+160.41%`，本身就不是收益、回撤、胜率三项同时改善。
- 冻结模型与阈值后，`ml_filter` 在验证段从 V35 的 `+97.27%` 变成 `-12.55%`；最近三个月复用窗口只剩 `+10.23%`，V35 原策略为 `+119.05%`。
- `ml_hybrid` 尝试补救被 V35 规则拒绝的高分候选，但最近三个月仅 `+43.86% / -48.25% / 胜率50.00%`，显著弱于 V35 的 `+119.05% / -27.26% / 胜率67.65%`。
- 不修改 V35，不登记新版本，不修改 live runner。LightGBM 产物只保留为失败诊断和后续研究基线。

## 数据与对齐

- 市场：Binance USD-M `HYPEUSDT` 永续，`15m`，UTC。
- 数据范围：`2025-05-30 10:30` 至 `2026-07-16 15:30`，共 `39,573` 根闭合 K 线。
- 连续性：缺失 K 线 `0`，重复时间戳 `0`，无效 OHLC `0`，关键字段空值 `0`。
- raw/normalized：`39,573` 行逐行对齐，OHLCV、quote volume、trade count 最大绝对差均为 `0`。
- funding：`3,840` 条原始记录，映射到 `2,472` 个非零 15m 时点；未把缺失市场数据猜测为新观测。
- 因子表：复用已审计的 HYPE 15m 因子数据集，`157` 个因子；与 V35 本轮 OHLCV 时间戳和 OHLCV 数值完全一致。模型总输入为 `157` 个通用因子加 `16` 个 V35 原生状态，共 `173` 个特征。
- 成本：沿用 V35 canonical 口径，每次成交 `8.5 bps`，并计入实际 funding。

数据与模型摘要见 [hype_ema_tb_v35_lightgbm_signal_scoring.json](../artifacts/v35-lightgbm-signal-scoring/hype_ema_tb_v35_lightgbm_signal_scoring.json)。

## 信号账本

本轮没有只拿 V35 已成交的 110 笔训练，而是建立完整事件账本：

| 事件类型 | 数量 | 定义 |
|---|---:|---|
| `opened` | 110 | V35 单持仓状态机实际开仓 |
| `state_blocked` | 961 | V35 规则已通过，但 K2 时仍有持仓或正处于退出 bar，未开新仓 |
| `rule_rejected` | 31,738 | 已满足方向预条件，但未通过 V35 的 ADX、量能或 1h 强度门槛 |
| 合计 | 32,809 | 多头预条件为 EMA96>EMA384 且已闭合 1h DI 向上；空头预条件为 EMA96<EMA384 且已闭合 1h EMA24<EMA96 |

每个事件都在 K0 收盘取因子，K2 开盘按 V35 仓位公式入场，再独立重放 `TP5 / SL7 / ADX22 delayed3 / MFE1.5 后禁用指标退出 / timeout384 / funding / 双边成本`，得到反事实净收益标签。最后 3 个无法完整退出的事件标为 censored，不参加训练。

完整事件、未开仓原因、反事实结果和模型分数见 [hype_ema_tb_v35_event_scores.parquet](../artifacts/v35-lightgbm-signal-scoring/hype_ema_tb_v35_event_scores.parquet)。

## 时间切分与泄漏控制

| 分段 | 时间边界 | 完整事件 | V35 规则通过 | V35 实际开仓 | 用途 |
|---|---|---:|---:|---:|---|
| Train | `< 2026-01-01`，且标签退出也早于边界 | 16,548 | 382 | 38 | 拟合模型 |
| Calibration | `2026-01-01` 至 `2026-03-01` | 4,889 | 227 | 26 | 选模型与阈值 |
| Validation | `2026-03-01` 至 `2026-04-17` | 4,045 | 137 | 11 | 冻结后预检 |
| OOS reused window | `2026-04-17` 至 `2026-07-16` | 7,280 | 316 | 34 | 最终揭示 |

最近三个月窗口在本诊断内没有参与选模或选阈值，但此前独立的 `HYPE-15M-Factor-ML` 家族已经使用过相同市场窗口，因此这里明确写为 `OOS reused window`，不是 pristine OOS。

## 模型与阈值

- 测试 6 个正则化 LightGBM 结构；只按 Calibration 的 AUC、Average Precision 与 Brier 组合指标选模型。
- 最终结构：`num_leaves=7`、`min_child_samples=120`、`feature_fraction=0.75`、`reg_lambda=3`，early stopping 后 `133` 棵树。
- Calibration AUC 仅 `0.5793`，Average Precision `0.5121`，说明排序能力很弱；其余 5 个结构的 AUC 也只在 `0.5791–0.5825`，没有稳定结构优势。
- `ml_filter` 阈值 `0.597369`；只允许原 V35 规则通过且分数不低于阈值的信号。
- `ml_hybrid` 使用 V35 通过阈值 `0.367406`、规则拒绝补救阈值 `0.440728`。
- 阈值只在 Calibration 选择，Validation 和最近三个月没有再次调整。

模型、阈值网格和特征重要性分别见 [LightGBM model](../artifacts/v35-lightgbm-signal-scoring/hype_ema_tb_v35_lightgbm_model.txt)、[threshold search](../artifacts/v35-lightgbm-signal-scoring/hype_ema_tb_v35_threshold_search.csv) 与 [feature importance](../artifacts/v35-lightgbm-signal-scoring/hype_ema_tb_v35_feature_importance.csv)。

## 冻结回测结果

| 分段 | 方案 | 收益 | 最大回撤 | 胜率 | 交易数 | Sharpe |
|---|---|---:|---:|---:|---:|---:|
| Calibration | V35 | +239.59% | -21.87% | 80.77% | 26 | 6.89 |
| Calibration | ML filter | +160.41% | -17.32% | 92.86% | 14 | 7.25 |
| Calibration | ML hybrid | +142.72% | -29.37% | 62.50% | 48 | 4.66 |
| Validation | V35 | +97.27% | -16.59% | 90.91% | 11 | 5.27 |
| Validation | ML filter | -12.55% | -21.02% | 40.00% | 5 | -1.73 |
| Validation | ML hybrid | +85.12% | -34.18% | 59.46% | 37 | 3.60 |
| OOS reused | V35 | +119.05% | -27.26% | 67.65% | 34 | 3.40 |
| OOS reused | ML filter | +10.23% | -27.02% | 66.67% | 12 | 0.89 |
| OOS reused | ML hybrid | +43.86% | -48.25% | 50.00% | 78 | 1.75 |
| Full | V35 | +7067.61% | -27.26% | 77.27% | 110 | 4.51 |
| Full | ML filter | +539.68% | -33.65% | 78.00% | 50 | 2.96 |
| Full | ML hybrid | +6629.68% | -48.25% | 59.58% | 287 | 3.52 |

逐笔对照见 [hype_ema_tb_v35_variant_trades.csv](../artifacts/v35-lightgbm-signal-scoring/hype_ema_tb_v35_variant_trades.csv)。

## 标准近期分片

| 窗口 | V35 收益 / DD / 平仓数 | ML filter 收益 / DD / 平仓数 | ML hybrid 收益 / DD / 平仓数 |
|---|---:|---:|---:|
| 1d | +0.12% / -2.88% / 1 | 0.00% / 0.00% / 0 | +0.12% / -2.88% / 1 |
| 7d | -15.28% / -22.94% / 2 | -11.47% / -15.08% / 1 | -14.97% / -22.94% / 3 |
| 1m | -16.51% / -23.96% / 6 | -10.21% / -17.53% / 3 | -29.45% / -33.83% / 8 |
| 3m | +119.05% / -27.26% / 34 | +10.23% / -27.02% / 12 | +43.86% / -48.25% / 78 |
| 6m | +1438.20% / -27.26% / 67 | +151.04% / -33.65% / 31 | +733.43% / -48.25% / 152 |
| 1y | +6571.19% / -27.26% / 103 | +462.52% / -33.65% / 48 | +3397.35% / -48.25% / 268 |
| full | +7067.61% / -27.26% / 110 | +539.68% / -33.65% / 50 | +6629.68% / -48.25% / 287 |

## 为什么失败

1. V35 已经是强规则筛选器。原规则通过事件很少：Train 只有 382 个规则通过 bar、其中实际开仓仅 38 笔；真正独立的成交样本不足以支撑 173 维模型。
2. `state_blocked` 信号高度重叠。连续多个 15m bar 往往描述同一段趋势，虽通过 episode 权重降低重复影响，仍不能把它们当成完全独立样本。
3. 分数发生明显 regime 漂移。校准段的高分过滤看似有效，冻结后在 Validation 直接转负；这不是换一个阈值就能修好的小偏差。
4. 规则拒绝事件属于更宽的分布。用模型补救后交易数从 110 增至 287，但 full 最大回撤扩大到 `-48.25%`，说明 LightGBM 没有学出足以替代 V35 ADX/量能门槛的稳定边界。
5. 全样本收益不能用于证明模型有效。`ml_hybrid` full 仍有 `+6629.68%`，但这是 V35 趋势机制的底层优势；冻结后的 Validation、最近三个月和回撤都证明 overlay 本身是负贡献。

## 决策

- 保持 `HYPE-EMA-TB-V35` 原信号、仓位与退出状态机不变。
- 不把当前 LightGBM score 接入线上开仓，不做分数加仓，也不允许高分规则拒绝事件绕过 V35 门槛。
- 如果未来继续 ML 方向，应先积累更多真实 V35 决策事件，并采用按完整 trend episode / trade opportunity 聚合的低维模型；在新数据到来前继续围绕本窗口调模型，只会增加过拟合。

## 复现

```bash
uv run python research/hype/15m-ema-trend-breakout/scripts/research_hype_ema_tb_v35_lightgbm_signal_scoring.py
```

复现脚本见 [research_hype_ema_tb_v35_lightgbm_signal_scoring.py](../scripts/research_hype_ema_tb_v35_lightgbm_signal_scoring.py)。
